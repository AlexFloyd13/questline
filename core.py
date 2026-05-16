"""Core buddy logic: save model, generation, leveling, drops, rendering."""
import json, os, random
from pathlib import Path
from datetime import date

from data import (
    STATS, STAT_LABELS, SALT, SPECIES, SPECIES_TIERS, PET_RARITY_TABLE,
    RARITY_STARS, COLORS, RESET, BOLD, DIM, RARITY_COLOR, LEVEL_COLOR_BANDS,
    xp_to_next, DROP_CHANCE_ON_LEVELUP, ITEM_RARITY_TABLE, HATS,
    ALL_DROPS, EYE_STYLES, NAMES,
)

SAVE_PATH = Path.home() / ".claude" / "buddy" / "save.json"
CLAUDE_JSON = Path.home() / ".claude.json"


def today():
    return str(date.today())


# --- hashing / PRNG (FNV-1a + Mulberry32, matches original buddy) ---
def fnv1a_32(s):
    h = 0x811c9dc5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def mulberry32(seed):
    state = [seed & 0xFFFFFFFF]

    def rand():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        t = state[0]
        t = (t ^ (t >> 15)) & 0xFFFFFFFF
        t = (t * (state[0] | 1)) & 0xFFFFFFFF
        t = (t ^ (t + (((t ^ (t >> 7)) & 0xFFFFFFFF) * ((state[0] | 61) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rand


def random_rng():
    return mulberry32(int.from_bytes(os.urandom(4), "big"))


def get_user_id():
    try:
        return json.loads(CLAUDE_JSON.read_text()).get("userID", "anon")
    except Exception:
        return "anon"


# --- save load/save ---
def _fresh():
    return {
        "version": 2, "active": None, "next_id": 1, "next_iid": 1,
        "pets": {}, "inventory": [],
        "watermarks": {},  # session_id -> {mtime, size, tokens}
        "created_at": today(),
    }


def load():
    if SAVE_PATH.exists():
        try:
            d = json.loads(SAVE_PATH.read_text())
            if isinstance(d, dict) and d.get("version") == 2:
                d.setdefault("pets", {})
                d.setdefault("inventory", [])
                d.setdefault("watermarks", {})
                return d
        except Exception:
            pass
    return _fresh()


def save(d):
    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SAVE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    tmp.replace(SAVE_PATH)


# --- generation ---
def _roll_attrs(rng):
    roll = rng()
    rarity = "Common"
    for name, thr in PET_RARITY_TABLE:
        if roll < thr:
            rarity = name
            break
    # if the rolled tier is empty, downgrade until we find a non-empty pool
    _order = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]
    while not SPECIES_TIERS[rarity]:
        idx = _order.index(rarity)
        if idx + 1 >= len(_order):
            break
        rarity = _order[idx + 1]
    pool = SPECIES_TIERS[rarity]
    species = pool[int(rng() * len(pool))]
    shiny = rng() < 0.01
    eyes = EYE_STYLES[int(rng() * len(EYE_STYLES))]
    base = {s: 15 + int(rng() * 66) for s in STATS}  # 15-80
    name = NAMES[species][int(rng() * len(NAMES[species]))]
    return rarity, species, shiny, eyes, base, name


def gen_pet(sv, rng):
    rarity, species, shiny, eyes, base, name = _roll_attrs(rng)
    pid = "p%d" % sv["next_id"]
    sv["next_id"] += 1
    return {
        "id": pid, "name": name, "species": species, "rarity": rarity,
        "shiny": shiny, "eyes": eyes,
        "base_stats": base, "earned_stats": {s: 0 for s in STATS},
        "level": 1, "xp": 0, "total_tokens": 0,
        "equipped_hat": None,
        "wins": 0, "losses": 0, "hatched_at": today(),
    }


def ensure_first_pet(sv):
    """Create the very first pet (seeded from userID) if collection is empty."""
    if sv["pets"]:
        if sv.get("active") not in sv["pets"]:
            sv["active"] = next(iter(sv["pets"]))
        return False
    rng = mulberry32(fnv1a_32(get_user_id() + SALT))
    pet = gen_pet(sv, rng)
    sv["pets"][pet["id"]] = pet
    sv["active"] = pet["id"]
    return True


def add_random_pet(sv):
    pet = gen_pet(sv, random_rng())
    sv["pets"][pet["id"]] = pet
    return pet


def active_pet(sv):
    return sv["pets"].get(sv.get("active"))


# --- stats / leveling ---
def total_stats(pet):
    return {s: pet["base_stats"][s] + pet["earned_stats"][s] for s in STATS}


def color_for_level(level):
    for thr, col in LEVEL_COLOR_BANDS:
        if level <= thr:
            return col
    return "gold"


def grow_stats(pet, rng):
    theme = SPECIES[pet["species"]]["theme"]
    gains = {s: 0 for s in STATS}
    for _ in range(3):
        gains[rng.choice(theme)] += 1
    for _ in range(2):
        gains[rng.choice(STATS)] += 1
    for s, g in gains.items():
        pet["earned_stats"][s] += g
    return gains


def make_drop(sv, rng):
    roll = rng.random()
    rarity = "Common"
    for name, thr in ITEM_RARITY_TABLE:
        if roll < thr:
            rarity = name
            break
    slot, typ = rng.choice(ALL_DROPS)
    iid = "i%d" % sv["next_iid"]
    sv["next_iid"] += 1
    return {"iid": iid, "slot": slot, "type": typ, "rarity": rarity}


def apply_xp(sv, pet, amount):
    """Add XP, process level-ups (themed growth + drop rolls). Returns events."""
    events = []
    if amount <= 0:
        return events
    pet["xp"] += amount
    pet["total_tokens"] += amount
    while pet["xp"] >= xp_to_next(pet["level"]):
        pet["xp"] -= xp_to_next(pet["level"])
        pet["level"] += 1
        rng = random.Random("%s-L%d" % (pet["id"], pet["level"]))
        gains = grow_stats(pet, rng)
        events.append({
            "type": "levelup", "level": pet["level"],
            "gains": gains, "color": color_for_level(pet["level"]),
        })
        if rng.random() < DROP_CHANCE_ON_LEVELUP:
            drop = make_drop(sv, rng)
            sv["inventory"].append(drop)
            events.append({"type": "drop", "drop": drop})
    return events


# --- inventory ---
def get_equipped(sv, pet, slot):
    # Only "hat" is a real equipment slot now; items were removed.
    if slot != "hat":
        return None
    iid = pet.get("equipped_hat")
    if not iid:
        return None
    for it in sv["inventory"]:
        if it["iid"] == iid:
            return it
    return None


def inv_list(sv):
    """Inventory is hats-only now (newest first by insertion order)."""
    return [it for it in sv["inventory"] if it["slot"] == "hat"]


# --- rendering ---
# ANSI color is rendered on the status-line surface but not in chat output,
# so cli.py disables it when piped; statusline.py keeps it on.
USE_COLOR = True


def c(text, color):
    if not USE_COLOR:
        return str(text)
    return "%s%s%s" % (COLORS.get(color, ""), text, RESET)


def crarity(text, rarity):
    return c(text, RARITY_COLOR.get(rarity, "white"))


def stat_bar(val, width=10):
    filled = max(0, min(width, val // 10))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def xp_bar(pet, width=12):
    need = xp_to_next(pet["level"])
    frac = 0 if need <= 0 else min(1.0, pet["xp"] / need)
    filled = int(frac * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def fmt_tokens(n):
    n = int(n)
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1_000:
        return "%.1fk" % (n / 1_000)
    return str(n)


def item_label(it):
    """Colored 'name (Rarity)' for an inventory entry."""
    return "%s %s" % (crarity(it["type"], it["rarity"]),
                      c("(%s)" % it["rarity"], RARITY_COLOR[it["rarity"]]))


def render_sprite(sv, pet):
    """Multi-line ASCII sprite: hat rows stacked above the head row, art in
    level color. Hats are multi-row (list of strings); the bottom row of the
    hat sits ON the buddy's head row in the world view, but for this CLI
    block-render we keep the hat strictly above the head for legibility."""
    sp = SPECIES[pet["species"]]
    lvl_color = color_for_level(pet["level"])
    art = [ln.replace("{e}", pet["eyes"]) for ln in sp["art"]]
    hat = get_equipped(sv, pet, "hat")
    lines = []
    if hat:
        hat_rows = HATS[hat["type"]]
        if isinstance(hat_rows, str):
            hat_rows = [hat_rows]
        for row in hat_rows:
            lines.append("     " + crarity(row, hat["rarity"]))
    for ln in art:
        lines.append(c("   " + ln, lvl_color))
    return "\n".join(lines)


def mini_face(pet):
    sp = SPECIES[pet["species"]]
    return c(sp["mini"].replace("{e}", pet["eyes"]), color_for_level(pet["level"]))


def name_tag(pet):
    nm = pet["name"]
    if pet.get("shiny"):
        nm = "*" + nm + "*"
    return c(nm, color_for_level(pet["level"]))
