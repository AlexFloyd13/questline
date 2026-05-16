"""Core buddy logic: save model, pet generation, leveling, drops, rendering.

This module is the shared library that both `statusline.py` (the per-render
status-line entry point) and `cli.py` (the /buddy subcommand dispatcher)
import from. It owns the save file format, the RNG primitives, the
leveling math, and the helpers that turn raw save state into colored
ASCII output.
"""

import json, os, random
from pathlib import Path
from datetime import date

from data import (
    STATS, SALT, SPECIES, SPECIES_TIERS, PET_RARITY_TABLE,
    COLORS, RESET, RARITY_COLOR, LEVEL_COLOR_BANDS,
    xp_to_next, DROP_CHANCE_ON_LEVELUP, ITEM_RARITY_TABLE, HATS,
    ALL_DROPS, EYE_STYLES, NAMES,
)

# Where the save file lives. Always inside the user's Claude config home
# so it survives reinstalls and is gitignored when this repo is cloned.
SAVE_PATH = Path.home() / ".claude" / "buddy" / "save.json"

# Claude Code stores the user's local config (incl. their userID, which we
# use as the seed for the starter pet) here. Read once at first-pet time.
CLAUDE_JSON = Path.home() / ".claude.json"


def today():
    """ISO date string, used as 'hatched_at' on new pets."""
    return str(date.today())


# --- Hashing / PRNG --------------------------------------------------------
# We need a deterministic, portable hash + RNG so that the SAME user gets
# the SAME starter pet across reinstalls. Python's hash() is randomized
# per-process and random.Random's algorithm isn't guaranteed across
# versions — so we ship our own FNV-1a + Mulberry32.

def fnv1a_32(s):
    """32-bit FNV-1a hash of a string. Deterministic, portable, fast."""
    h = 0x811c9dc5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def mulberry32(seed):
    """Tiny seedable PRNG. Returns a callable that yields floats in [0, 1).
    Picked because it's stable across language ports — the same seed gives
    the same sequence everywhere."""
    state = [seed & 0xFFFFFFFF]

    def rand():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        t = state[0]
        t = (t ^ (t >> 15)) & 0xFFFFFFFF
        t = (t * (state[0] | 1)) & 0xFFFFFFFF
        t = (t ^ (t + (((t ^ (t >> 7)) & 0xFFFFFFFF)
                        * ((state[0] | 61) & 0xFFFFFFFF)) & 0xFFFFFFFF)
             ) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rand


def random_rng():
    """Non-deterministic Mulberry32 seeded from os.urandom — used for
    'hatch me a fresh random pet' where we don't want reproducibility."""
    return mulberry32(int.from_bytes(os.urandom(4), "big"))


def get_user_id():
    """Read the Claude Code userID from ~/.claude.json. Falls back to
    'anon' if the file is missing or malformed — the starter pet is then
    deterministic-per-machine instead of deterministic-per-user."""
    try:
        return json.loads(CLAUDE_JSON.read_text()).get("userID", "anon")
    except Exception:
        return "anon"


# --- Save load / save ------------------------------------------------------

def _fresh():
    """A brand-new empty save dict. Used when no save file exists OR when
    the existing file is corrupt beyond repair."""
    return {
        "version": 2,
        "active": None,           # id of the pet currently earning XP
        "next_id": 1,             # incremented for each new pet
        "next_iid": 1,            # incremented for each new inventory entry
        "pets": {},               # id -> pet dict
        "inventory": [],          # list of {iid, slot, type, rarity}
        "watermarks": {},         # session_id -> {mtime, size, tokens}
        "created_at": today(),
    }


def load():
    """Read and validate save.json. Returns a fresh save if the file is
    missing, malformed, or has wrong-type top-level fields. Never raises."""
    if SAVE_PATH.exists():
        try:
            d = json.loads(SAVE_PATH.read_text())
            if isinstance(d, dict) and d.get("version") == 2:
                # Defensive type normalization — a hand-edited save with
                # wrong-type fields would otherwise crash downstream renders.
                if not isinstance(d.get("pets"), dict):
                    d["pets"] = {}
                if not isinstance(d.get("inventory"), list):
                    d["inventory"] = []
                if not isinstance(d.get("watermarks"), dict):
                    d["watermarks"] = {}
                d.setdefault("next_id", 1)
                d.setdefault("next_iid", 1)
                d.setdefault("active", None)
                return d
        except Exception:
            pass
    return _fresh()


def save(d):
    """Atomically write the save dict to disk. The tmp+rename dance prevents
    a partial save from corrupting the file if we crash mid-write."""
    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SAVE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    tmp.replace(SAVE_PATH)


# --- Pet generation --------------------------------------------------------

def _roll_attrs(rng):
    """Roll rarity, species, shiny flag, eye style, base stats, and name
    for a brand-new pet. `rng()` returns floats in [0, 1)."""
    # Roll rarity tier
    roll = rng()
    rarity = "Common"
    for name, thr in PET_RARITY_TABLE:
        if roll < thr:
            rarity = name
            break
    # If the rolled tier is empty (no species defined for it), downgrade
    # until we find a non-empty pool. Keeps the system resilient if you
    # delete the only species in a tier.
    _order = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]
    while not SPECIES_TIERS[rarity]:
        idx = _order.index(rarity)
        if idx + 1 >= len(_order):
            break
        rarity = _order[idx + 1]

    pool = SPECIES_TIERS[rarity]
    species = pool[int(rng() * len(pool))]
    shiny = rng() < 0.01                          # 1% chance of shiny
    eyes = EYE_STYLES[int(rng() * len(EYE_STYLES))]
    base = {s: 15 + int(rng() * 66) for s in STATS}   # base stats 15..80
    name = NAMES[species][int(rng() * len(NAMES[species]))]
    return rarity, species, shiny, eyes, base, name


def gen_pet(sv, rng):
    """Build a brand-new pet dict (Lvl 1, 0 XP) and increment next_id.
    Caller is responsible for adding it to sv['pets']."""
    rarity, species, shiny, eyes, base, name = _roll_attrs(rng)
    pid = "p%d" % sv["next_id"]
    sv["next_id"] += 1
    return {
        "id": pid, "name": name, "species": species, "rarity": rarity,
        "shiny": shiny, "eyes": eyes,
        "base_stats": base,
        "earned_stats": {s: 0 for s in STATS},
        "level": 1, "xp": 0, "total_tokens": 0,
        "equipped_hat": None,
        "color_choice": None,    # /buddy color override (None = auto by level)
        "wins": 0, "losses": 0,
        "hatched_at": today(),
    }


def ensure_first_pet(sv):
    """If the user has no pets yet, hatch the deterministic starter pet
    (seeded from their Claude userID + SALT). Otherwise, just make sure
    sv['active'] points at a real pet. Returns True if it hatched."""
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
    """Hatch a new pet with non-deterministic attributes."""
    pet = gen_pet(sv, random_rng())
    sv["pets"][pet["id"]] = pet
    return pet


def active_pet(sv):
    """The default active pet (used when there's no per-session override).
    Returns None if sv['active'] is stale."""
    return sv["pets"].get(sv.get("active"))


def active_pet_for_session(sv, session_id):
    """Return the pet currently earning XP in THIS terminal session.

    Each terminal can pin its own active pet via `/buddy switch <n>` —
    so terminal A can be leveling Biscuit while terminal B grinds Eight.
    The pin lives in sv['session_pets'][session_id]; if missing, falls
    back to the global default sv['active']."""
    pets = sv.setdefault("pets", {})
    if not pets:
        return None
    sp  = sv.get("session_pets", {})
    pid = sp.get(session_id) or sv.get("active")
    if pid not in pets:
        # Stale pin (pet was deleted?) — fall back to whatever's available
        # and update the global default so future renders don't bounce.
        pid = next(iter(pets))
        sv["active"] = pid
    return pets[pid]


def pin_session_pet(sv, session_id, pet_id):
    """Pin a pet to a specific terminal session. Caps the pinned dict at
    30 entries (oldest insertion-order entries get pruned) so the save
    doesn't grow unbounded with stale session IDs."""
    sp = sv.setdefault("session_pets", {})
    # Re-insert so it moves to the end (newest) of the insertion order.
    sp.pop(session_id, None)
    sp[session_id] = pet_id
    if len(sp) > 30:
        for old in list(sp.keys())[:-30]:
            del sp[old]


# --- Stats / leveling ------------------------------------------------------

def total_stats(pet):
    """Effective stats = base (rolled at hatch) + earned (from level-ups)."""
    return {s: pet["base_stats"][s] + pet["earned_stats"][s] for s in STATS}


def color_for_level(level):
    """The natural color for a pet's level band — what it renders in by
    default (no manual override)."""
    for thr, col in LEVEL_COLOR_BANDS:
        if level <= thr:
            return col
    return "gold"


def unlocked_colors(level):
    """Every color tier the pet has reached. Lowest-tier first.

    Lvl 1   -> ['white']
    Lvl 10  -> ['white', 'green']
    Lvl 40  -> ['white', 'green', 'cyan', 'blue']
    Lvl 80  -> ['white', 'green', 'cyan', 'blue', 'magenta', 'silver']
    Lvl 100 -> all seven (silver and gold)

    A pet may downgrade to any color it has unlocked via the
    /buddy color subcommand, but the choice is cosmetic only."""
    unlocked = []
    for thr, col in LEVEL_COLOR_BANDS:
        unlocked.append(col)
        if level <= thr:
            break
    return unlocked


def color_for_pet(pet):
    """The color this pet should render in right now. Honors pet['color_choice']
    if it's set and the pet has actually unlocked that color; otherwise
    falls back to the natural level-band color."""
    natural = color_for_level(pet["level"])
    choice  = pet.get("color_choice")
    if choice and choice in unlocked_colors(pet["level"]):
        return choice
    return natural


def grow_stats(pet, rng):
    """On level-up, hand out 5 stat points: 3 to a random themed stat
    (favored for the species) and 2 to any random stat. Mutates the pet
    in place. Returns the gains dict for the level-up event."""
    theme = SPECIES[pet["species"]]["theme"]
    gains = {s: 0 for s in STATS}
    for _ in range(3):
        gains[rng.choice(theme)] += 1
    for _ in range(2):
        gains[rng.choice(STATS)] += 1
    for s, g in gains.items():
        pet["earned_stats"][s] += g
    return gains


def make_drop(sv, rng, level=1):
    """Generate one random hat drop. Rarity is rolled with a small
    level-scaled boost so higher-level pets get rarer hats more often,
    but Mythic stays a chase — even at L100, only ~1 in 5 drops is
    Mythic. The boost effectively subtracts from the roll, pushing it
    toward the lower (rarer) thresholds in ITEM_RARITY_TABLE.

    Mythic stays a chase at every level — even a maxed pet pulls it only
    ~5% of the time, and it's far rarer below max:
      L1   - 0.5% Mythic, 2.5% Legendary, 50% Common (vanilla)
      L25  - ~1.6% Mythic
      L50  - ~2.7% Mythic
      L75  - ~3.8% Mythic
      L100 - ~5.0% Mythic (the cap; never higher)

    Hat type is rolled separately from ALL_DROPS so any hat can drop at
    any rarity. Mutates sv['next_iid']."""
    # 0.00045 boost per level above 1, capped at 0.045 so L100 lands at
    # exactly 5% Mythic. Past L100 the boost stays at the cap.
    boost = min(0.045, max(0, (level - 1) * 0.00045))
    roll = rng.random() - boost
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
    """Add XP to a pet. Cascades through any level-ups (themed stat gains
    + drop rolls) until the pet's xp falls below xp_to_next. Returns a
    list of events the caller can use for UI feedback / logging."""
    events = []
    if amount <= 0:
        return events
    pet["xp"] += amount
    pet["total_tokens"] += amount
    while pet["xp"] >= xp_to_next(pet["level"]):
        pet["xp"] -= xp_to_next(pet["level"])
        pet["level"] += 1
        # Per-level RNG seeded from pet id + level — deterministic so a
        # given pet always gains the same stats at the same level.
        rng = random.Random("%s-L%d" % (pet["id"], pet["level"]))
        gains = grow_stats(pet, rng)
        events.append({
            "type": "levelup", "level": pet["level"],
            "gains": gains, "color": color_for_level(pet["level"]),
        })
        if rng.random() < DROP_CHANCE_ON_LEVELUP:
            drop = make_drop(sv, rng, level=pet["level"])
            sv["inventory"].append(drop)
            events.append({"type": "drop", "drop": drop})
    return events


# --- Inventory -------------------------------------------------------------

def get_equipped(sv, pet, slot):
    """The inventory entry currently equipped in `slot` on this pet, or
    None. Only "hat" is a real slot — held items existed in an earlier
    draft and were removed."""
    if slot != "hat":
        return None
    iid = pet.get("equipped_hat")
    if not iid:
        return None
    return next((it for it in sv["inventory"] if it["iid"] == iid), None)


def inv_list(sv):
    """Inventory entries (hats only). Insertion order = oldest first."""
    return [it for it in sv["inventory"] if it["slot"] == "hat"]


# --- Rendering helpers -----------------------------------------------------
# ANSI color is appropriate for the status-line surface but not for plain
# chat output. cli.py flips USE_COLOR off when stdout isn't a TTY;
# statusline.py keeps it on.

USE_COLOR = True


def c(text, color):
    """Wrap `text` in the ANSI escapes for `color`. No-op if USE_COLOR is
    off or if `color` isn't in the palette."""
    if not USE_COLOR:
        return str(text)
    return "%s%s%s" % (COLORS.get(color, ""), text, RESET)


def crarity(text, rarity):
    """Wrap `text` in the color associated with this rarity tier."""
    return c(text, RARITY_COLOR.get(rarity, "white"))


def stat_bar(val, width=10):
    """A `[####------]` bar where `val` (0-100) controls fill fraction."""
    filled = max(0, min(width, val // 10))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def xp_bar(pet, width=12):
    """A `[####------]` bar showing this pet's progress to the next level."""
    need = xp_to_next(pet["level"])
    frac = 0 if need <= 0 else min(1.0, pet["xp"] / need)
    filled = int(frac * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def fmt_tokens(n):
    """Compact token count: 1234 -> '1.2k', 1500000 -> '1.5M'."""
    n = int(n)
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1_000:
        return "%.1fk" % (n / 1_000)
    return str(n)


def item_label(it):
    """Colored 'name (Rarity)' for an inventory entry."""
    return "%s %s" % (
        crarity(it["type"], it["rarity"]),
        c("(%s)" % it["rarity"], RARITY_COLOR[it["rarity"]]),
    )


def render_sprite(sv, pet):
    """Multi-line ASCII sprite for the CLI (NOT the status line — that's
    in adventure.render_world). Hat rows are stacked above the sprite for
    legibility; in the world view they overlap the head row instead."""
    sp = SPECIES[pet["species"]]
    lvl_color = color_for_pet(pet)
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
    """One-line compact face, e.g. for the /buddy list summary."""
    sp = SPECIES[pet["species"]]
    return c(sp["mini"].replace("{e}", pet["eyes"]), color_for_pet(pet))


def name_tag(pet):
    """Pet name in the pet's color, wrapped in `*...*` if shiny."""
    nm = pet["name"]
    if pet.get("shiny"):
        nm = "*" + nm + "*"
    return c(nm, color_for_pet(pet))
