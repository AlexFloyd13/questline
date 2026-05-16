"""Ambient top-down adventure for the status line.

The active buddy walks rightward through a procedurally-generated world; the
camera follows so the buddy stays near the left side of the visible area. When
a wild creature spawns ahead, the two slowly walk toward each other (approach
phase); when adjacent, they fight in place with visible attack animations
between them (fighting phase). Win/loss awards XP and may drop a rare item."""
import random, time
import core
from data import SPECIES, COLORS, RESET


WORLD_ROWS = 7           # 1 hat + up-to-6-row buddy with bottom row MERGED into ground
STEP_SECONDS = 6         # one walk step per ~6s real time
MAX_STEPS_PER_RENDER = 8 # cap so long pauses don't teleport you
SPAWN_DISTANCE = 24      # monster spawns this far ahead of buddy
BATTLE_GAP = 14          # monster_col - buddy_col when fighting starts
COMBAT_TURNS = 4         # 1=buddy atk, 2=enemy atk, 3=clash, 4=resolve+clear

# Fixed-width buddy panel on the left of the status line. Layout (left -> right):
#   col 0                       : the back-wall '|' (visual anchor)
#   cols BUDDY_OFFSET ..        : the buddy sprite (left-justified relative to wall)
#   col BUDDY_PANEL_WIDTH-1     : last col still inside the panel
#   col BUDDY_PANEL_WIDTH ..    : the scrolling landscape (independent of sprite_w)
# Max sprite width is 16 (cow). 3-col offset + 16-wide sprite + 2-col margin = 21.
BUDDY_WALL_COL = 0
BUDDY_OFFSET = 3            # buddy sits this many cols in front of the wall
BUDDY_PANEL_WIDTH = 21
BUDDY_TIP_COL = BUDDY_PANEL_WIDTH - 1

# Multi-char ASCII features stamped at deterministic world positions.
# Chrome-dino-runner vibe: clean horizon, occasional clutter.
# Sky features are 1 row only (row 0) so they never collide with the buddy.
# Ground features are 1-2 rows only (rows 3-4) so the buddy's head row stays clean.
SKY_FEATURES = []  # sky stays empty so the buddy's hat space is never crowded
# Tree builders. Two body shapes:
#   _small_tree(): the classic 2-wide /\ pine — 4 rows tall, fits anywhere.
#   _big_tree(): 8-wide pyramidal canopy with || trunk perfectly centered.
# Both end with the trunk row stamping ONLY ||  — the surrounding cols are
# spaces so the dark-green ground texture continues underneath the canopy
# instead of getting overwritten with a brown bar.
def _small_tree(rate, leaf_color):
    return {
        "rate": rate, "color": leaf_color,
        "row_colors": [leaf_color, leaf_color, leaf_color, "brown"],
        "art": ["/\\", "/\\", "/\\", "||"],
    }


def _big_tree(rate, leaf_color, tree_w=7, extra_rows=0):
    """Build an odd-width pyramidal tree.

    `tree_w` must be odd. The peak ^ and the ^ down the middle of every
    crown row land on the dead-center column. Each step down adds one more
    / on the left and one more \\ on the right, so a 9-wide tree shows up
    to //// and \\\\\\\\ on the widest row.

      tree_w=7  -> standard pyramid, 5 rows total
      tree_w=9  -> wider, 6 rows total
      tree_w=11 -> widest, 7 rows total (max that fits in WORLD_ROWS)
    `extra_rows` repeats the widest crown row N more times for taller trees.

    Trunk is `||` (2-wide) straddling the center: left pipe sits AT the
    center column under the peak. For width=7 the trunk lands at cols 3-4,
    for width=9 cols 4-5, for width=11 cols 5-6.
    """
    assert tree_w % 2 == 1, "tree_w must be odd"
    half = tree_w // 2
    crown = [" " * half + "^" + " " * half]  # peak: single ^ at dead center
    for i in range(1, half + 1):
        pad = " " * (half - i)
        crown.append(pad + "/" * i + "^" + "\\" * i + pad)
    crown += [crown[-1]] * extra_rows
    # || trunk: left pipe at the center col, right pipe one past it.
    trunk = " " * half + "||" + " " * (half - 1)
    return {
        "rate": rate, "color": leaf_color,
        "row_colors": [leaf_color] * len(crown) + ["brown"],
        "art": crown + [trunk],
    }


def _christmas_tree(rate):
    """Ultra-rare Christmas tree. 9-wide pyramid:
      - red * star at the peak (col 4, dead center)
      - red O ornaments through the crown
      - brown || trunk CENTERED beneath the star (cols 3-4, right pipe under
        the star; sits in the middle of the tree's footprint)
      - red [*] present box OFF TO THE SIDE on the ground row (cols 6-8),
        separated from the trunk by a space gap so the trunk is clearly the
        center of the tree and the present is a distinct object beside it
    Bottom row layout (cols 0-8):  '   || [*]'
    """
    art = [
        "    *    ",   # red star at the peak
        "   /^\\   ",
        "  //O\\\\  ",
        " ///^\\\\\\ ",
        "////O\\\\\\\\",
        "   || [*]",   # || trunk centered, gap, red [*] present off to side
    ]
    return {
        "rate": rate, "color": "forest_green",
        "row_colors": ["forest_green"] * 5 + ["brown"],
        "char_colors": {"*": "red", "O": "red",
                        "[": "red", "]": "red"},
        "art": art,
    }


GROUND_FEATURES = [
    # small classic /\ pines — 4 rows tall, 2 cols wide. Three color shades
    # so a forest of small trees looks varied instead of mass-produced.
    _small_tree(0.013, "pine_green"),
    _small_tree(0.012, "forest_green"),
    _small_tree(0.010, "lime_green"),
    # standard pyramidal trees — 5 rows tall, 8 cols wide. ^ on top, /// \\\
    # on the sides, ||  centered trunk on its own row (ground shows through).
    _big_tree(0.009, "forest_green"),
    _big_tree(0.009, "green"),
    # big variant — taller canopy (7 rows = max that fits in WORLD_ROWS).
    # Low rate + own placement pass = an occasional landmark, not the default.
    _big_tree(0.0005, "sage_green", extra_rows=2),       # 7-row big (7-wide)
    _big_tree(0.0005, "pine_green", extra_rows=2),       # 7-row big (darker)
    # wider sizes — even chunkier landmarks, rarer.
    _big_tree(0.0004, "forest_green", tree_w=9),         # 6-row, 9-wide
    _big_tree(0.0002, "lime_green", tree_w=11),          # 7-row, 11-wide (max)
    # ULTRA RARE christmas tree: gold star, red ornaments, red present box.
    _christmas_tree(0.00005),                            # ~1 in 20,000 cols
    # bushes — 2 rows, 5 cols wide.
    #   (***)   <- canopy
    #    \*/   <- base, inside the canopy footprint
    {"rate": 0.022, "color": "lime_green", "art": ["(***)", " \\*/ "]},
    # grass — single-row tufts
    {"rate": 0.018, "color": "forest_green", "art": [",,,"]},
    {"rate": 0.014, "color": "lime_green", "art": ["vvv"]},
    # flowers — 2-row, 3 cols wide. bloom + stem in the same 3-col strip.
    {"rate": 0.018, "color": "green",
     "char_colors": {"@": "red"},
     "art": ["\\@/", "*|*"]},
]

# Wild creatures. Magenta = "danger" hue. Marked with a "!" alert above when they
# spawn so they're easy to spot against the landscape.
ENEMIES = {
    "rat":    {"hp_mult": 0.7, "xp": 200, "color": "magenta",
               "art": [" ,___,", "(>.<)", " V V "]},
    "bat":    {"hp_mult": 0.8, "xp": 250, "color": "magenta",
               "art": [" /\\_/\\", "( -.- )", " \\v_v/"]},
    "slime":  {"hp_mult": 1.0, "xp": 320, "color": "magenta",
               "art": ["  ___  ", " /X X\\", "(  v  )", " \\___/"]},
    "bun":    {"hp_mult": 0.6, "xp": 180, "color": "magenta",
               "art": ["(\\_/)", "(>.<)", '(")(")']},
    "blob":   {"hp_mult": 1.1, "xp": 400, "color": "magenta",
               "art": ["  ___ ", " /XXX\\", "(o   o)", " ~~~~ "]},
    "spider": {"hp_mult": 0.9, "xp": 280, "color": "magenta",
               "art": [" /\\___/\\", "(/X.X\\)", "//|V|\\\\", " V V V "]},
    "ghost":  {"hp_mult": 1.2, "xp": 500, "color": "magenta",
               "art": [" .===.", "( X X )", "(  v  )", " ~vvv~"]},
    "bandit": {"hp_mult": 1.3, "xp": 600, "color": "magenta",
               "art": ["[#####]", " (>.<)", " /|X|\\", " d   b"]},
}
ENEMY_KEYS = list(ENEMIES)


# --- world generation (deterministic per absolute world position) ---
def _ground_at(pos):
    """Subtle texture on the horizon line. Only chars that sit at the descender
    so the line stays flat (no `.` — that renders higher and looks like a stray
    dot floating above the ground)."""
    rng = random.Random(pos * 53 + 5)
    r = rng.random()
    if r < 0.06: return ","
    return "_"


def _pick_feature(pos, features, seed_salt):
    """Roll for a feature placement at this world position. Returns the
    feature dict or None. Stable per position."""
    rng = random.Random(pos * 7919 + seed_salt)
    r = rng.random()
    acc = 0.0
    for f in features:
        acc += f["rate"]
        if r < acc:
            return f
    return None


def encounter_seed(pos):
    """Stable: does this world position trigger an encounter?"""
    if pos <= 0:
        return None
    rng = random.Random(pos * 31337 + 11)
    if rng.random() < 0.030:  # ~1 per ~33 steps
        return ENEMY_KEYS[int(rng.random() * len(ENEMY_KEYS))]
    return None


def _is_xmas_tree_at(pos):
    """Deterministic: does a Christmas tree spawn at this world position?
    Uses the same _pick_feature roll the renderer uses for the big-tree pass,
    so it always agrees with what's drawn on screen."""
    if pos < 0:
        return False
    big_trees_list = [f for f in GROUND_FEATURES if len(f["art"]) >= 6]
    xmas = next((f for f in big_trees_list
                 if "[" in "".join(f["art"])), None)
    if xmas is None:
        return False
    return _pick_feature(pos, big_trees_list, 89) is xmas


def _xmas_gift(sv, pos):
    """Open the present at this Christmas tree if not already opened.
    Returns a drop dict (added to inventory) or None. The gift is always
    a hat, biased toward higher rarities since these trees are ultra-rare.
    Position-seeded so re-walking past gives the same gift (idempotent)."""
    from data import HATS
    st = _state(sv)
    collected = st.setdefault("xmas_collected", [])
    if pos in collected:
        return None
    collected.append(pos)
    # keep the list bounded — only last 50 collections need to be remembered
    if len(collected) > 50:
        del collected[:-50]
    rng = random.Random(pos * 9999 + 7)
    r = rng.random()
    # rare-or-better roll, weighted toward Epic/Legendary
    if r < 0.05:
        rarity = "Mythic"
    elif r < 0.25:
        rarity = "Legendary"
    elif r < 0.60:
        rarity = "Epic"
    else:
        rarity = "Rare"
    hat_type = sorted(HATS.keys())[int(rng.random() * len(HATS))]
    drop = {"iid": "x%d" % pos, "slot": "hat",
            "type": hat_type, "rarity": rarity}
    sv["inventory"].append(drop)
    return drop


# --- save-state helpers ---
def _state(sv):
    st = sv.setdefault("adventure", {})
    # migrate from v1 single-strip layout
    if "buddy_col" not in st:
        st["buddy_col"] = st.pop("position", 0)
    st.setdefault("last_tick", time.time())
    st.setdefault("encounter", None)
    st.setdefault("log", [])
    st.setdefault("steps", 0)
    st.setdefault("kills", 0)
    st.setdefault("losses", 0)
    # migrate any pre-phase encounter — just nuke it
    enc = st.get("encounter")
    if enc and "phase" not in enc:
        st["encounter"] = None
    return st


def _make_encounter(enemy_key, buddy_col):
    return {
        "key": enemy_key,
        "phase": "approach",
        "monster_col": buddy_col + SPAWN_DISTANCE,
        "turn": 0,
        "outcome": None,  # filled when fight resolves (for clash render + log)
    }


# --- combat ---
def _combat_turn(sv, pet, st):
    """One tick during the fighting phase.
    turn 1: buddy attacks visual
    turn 2: monster attacks visual
    turn 3: compute outcome + render clash
    turn 4: clear encounter, log result"""
    enc = st["encounter"]
    enc["turn"] += 1
    events = []

    if enc["turn"] in (1, 2):
        return [{"type": "attack", "attacker":
                 "buddy" if enc["turn"] == 1 else "monster"}]

    if enc["turn"] == 3:
        ts = core.total_stats(pet)
        rng = random.Random()
        win_chance = min(0.92, max(0.30,
                                   0.55 + (ts["debugging"] + ts["chaos"]) / 700.0))
        won = rng.random() < win_chance
        e_info = ENEMIES[enc["key"]]
        if won:
            xp = e_info["xp"]
            core.apply_xp(sv, pet, xp)
            st["kills"] = st.get("kills", 0) + 1
            drop = None
            if rng.random() < 0.06:
                drop = core.make_drop(sv, rng)
                sv["inventory"].append(drop)
            enc["outcome"] = "win"
            msg = "won vs %s +%dxp" % (enc["key"], xp)
            if drop:
                msg += " +%s %s" % (drop["rarity"], drop["type"])
            events.append({"type": "win", "xp": xp, "drop": drop})
        else:
            xp = e_info["xp"] // 5
            core.apply_xp(sv, pet, xp)
            st["losses"] = st.get("losses", 0) + 1
            enc["outcome"] = "loss"
            msg = "lost to %s +%dxp" % (enc["key"], xp)
            events.append({"type": "loss", "xp": xp})
        log = st.setdefault("log", [])
        log.append(msg)
        if len(log) > 3:
            del log[: len(log) - 3]
        return events

    # turn 4: clear and let the buddy resume walking
    st["encounter"] = None
    return []


def advance(sv, pet):
    """Walk the buddy forward, run encounter approach/fight sequencing."""
    st = _state(sv)
    now = time.time()
    elapsed = max(0, now - st.get("last_tick", now))
    st["last_tick"] = now
    natural = min(MAX_STEPS_PER_RENDER, int(elapsed / STEP_SECONDS))
    # always tick at least once if an encounter is in progress (keeps the
    # animation moving even between turns the user takes)
    steps = max(1, natural) if st.get("encounter") else natural
    events = []
    for _ in range(steps):
        enc = st.get("encounter")
        if enc and enc["phase"] == "approach":
            if enc["monster_col"] - st["buddy_col"] > BATTLE_GAP:
                st["buddy_col"] += 1
                enc["monster_col"] -= 1
            else:
                enc["phase"] = "fighting"
                enc["turn"] = 0
            continue
        if enc and enc["phase"] == "fighting":
            events.extend(_combat_turn(sv, pet, st))
            continue
        # no encounter: walk right + roll for spawn
        st["buddy_col"] += 1
        st["steps"] = st.get("steps", 0) + 1
        # Christmas tree gift: if the buddy walked onto a Christmas tree's
        # world position, claim its hat. Always a Rare+ hat.
        if _is_xmas_tree_at(st["buddy_col"]):
            gift = _xmas_gift(sv, st["buddy_col"])
            if gift:
                log = st.setdefault("log", [])
                log.append("xmas gift +%s %s" % (gift["rarity"], gift["type"]))
                if len(log) > 3:
                    del log[: len(log) - 3]
                events.append({"type": "xmas_gift", "drop": gift})
        ek = encounter_seed(st["buddy_col"])
        if ek:
            st["encounter"] = _make_encounter(ek, st["buddy_col"])
            events.append({"type": "encounter", "enemy": ek})
            break
    return events


# --- rendering ---
def _stamp(grid, art, col, row, color, width, char_colors=None):
    """Stamp a multi-line sprite onto the grid. Spaces in art pass through.
    char_colors lets a feature override the color of specific glyphs (e.g.
    oak's `@` apples render red even though the surrounding crown is green)."""
    for i, line in enumerate(art):
        r = row + i
        if not (0 <= r < WORLD_ROWS):
            continue
        for j, ch in enumerate(line):
            c = col + j
            if 0 <= c < width and ch != " ":
                col_for_char = char_colors[ch] if (char_colors and ch in char_colors) else color
                grid[r][c] = (ch, col_for_char)


def render_world(sv, pet, width=140):
    """Two-region renderer: a fixed-width buddy panel on the left, scrolling
    landscape on the right. The two regions never share columns, so swapping
    buddies (or changing sprite width) leaves landscape feature placement
    completely unchanged."""
    st = _state(sv)
    bc = st["buddy_col"]
    st.pop("cam_lock", None)  # clean up old state

    sp = SPECIES[pet["species"]]
    sprite = [ln.replace("{e}", pet["eyes"]) for ln in sp["art"]]
    sprite_h = len(sprite)
    sprite_w = max((len(ln) for ln in sprite), default=0)
    lc = core.color_for_level(pet["level"])
    sprite_top = max(0, WORLD_ROWS - sprite_h)

    # Buddy sits BUDDY_OFFSET cols in front of the wall at col 0. The landscape
    # only starts at col BUDDY_PANEL_WIDTH, so sprite width changes never shift
    # the trees / trunks / grass columns.
    buddy_screen = BUDDY_OFFSET
    cam = bc

    # world_pos(c) = cam + (c - BUDDY_TIP_COL)
    #   c == BUDDY_TIP_COL  -> wp == cam              (the col the buddy occupies)
    #   c == BUDDY_PANEL_WIDTH -> wp == cam + 1       (first landscape col)
    def wp_at(c):
        return cam + (c - BUDDY_TIP_COL)

    # blank grid; ground row textured BROWN across the WHOLE width so the
    # horizon flows continuously past the buddy panel into the landscape.
    grid = [[(" ", None) for _ in range(width)] for _ in range(WORLD_ROWS)]
    for c in range(width):
        grid[WORLD_ROWS - 1][c] = (_ground_at(wp_at(c)), "dark_green")

    # ground features (trees, bushes, grass, flowers) — placed ONLY in the
    # landscape region (cols >= BUDDY_PANEL_WIDTH). The buddy panel never
    # carries feature art, so feature columns are decoupled from sprite_w.
    enemy_protect = None
    enc_preview = st.get("encounter")
    if enc_preview:
        e_art_preview = ENEMIES.get(enc_preview["key"], {}).get("art", [])
        e_w_preview = max((len(ln) for ln in e_art_preview), default=0)
        e_screen_preview = BUDDY_TIP_COL + (enc_preview["monster_col"] - cam)
        enemy_protect = (e_screen_preview - 2, e_screen_preview + e_w_preview + 2)

    # Two-pass placement so big trees (full-height landmarks) aren't crowded
    # out by smaller features that happen to roll at earlier cols.
    # >=6 rows catches every tall variant: 7-row big pyramid, 6-row 9-wide,
    # 7-row 11-wide, and 6-row christmas tree.
    big_trees = [f for f in GROUND_FEATURES if len(f["art"]) >= 6]
    small_feats = [f for f in GROUND_FEATURES if len(f["art"]) < 6]
    occupied = [False] * width  # tracks cols already claimed by big trees

    def _place(feat, c):
        feat_w = max(len(ln) for ln in feat["art"])
        if enemy_protect and c + feat_w >= enemy_protect[0] and c <= enemy_protect[1]:
            return 0
        h = len(feat["art"])
        top = WORLD_ROWS - h
        row_colors = feat.get("row_colors")
        char_colors = feat.get("char_colors")
        if row_colors:
            for i, line in enumerate(feat["art"]):
                rc = row_colors[i] if i < len(row_colors) else feat["color"]
                _stamp(grid, [line], c, top + i, rc, width, char_colors)
        else:
            _stamp(grid, feat["art"], c, top, feat["color"], width, char_colors)
        return feat_w

    # Pass 1: big trees only — own min-spacing so they don't cluster, but
    # they get first crack at the canopy before smaller features fill in.
    last_big_end = -100
    for c in range(BUDDY_PANEL_WIDTH, width):
        if c < last_big_end + 6:  # bigger gap between big trees
            continue
        feat = _pick_feature(wp_at(c), big_trees, 89)  # own seed salt
        if not feat:
            continue
        feat_w = _place(feat, c)
        if feat_w > 0:
            last_big_end = c + feat_w
            for k in range(c, min(width, c + feat_w)):
                occupied[k] = True

    # Pass 2: small features fill in the rest, skipping cols owned by big trees.
    last_feat_end = -100
    for c in range(BUDDY_PANEL_WIDTH, width):
        if c < last_feat_end + 2:
            continue
        if occupied[c]:
            continue
        feat = _pick_feature(wp_at(c), small_feats, 53)
        if not feat:
            continue
        feat_w = max(len(ln) for ln in feat["art"])
        # Don't overlap a big tree to the right
        if any(occupied[k] for k in range(c, min(width, c + feat_w))):
            continue
        placed_w = _place(feat, c)
        if placed_w > 0:
            last_feat_end = c + placed_w

    # buddy sprite — left-justified at col 0
    _stamp(grid, sprite, buddy_screen, sprite_top, lc, width)

    # vertical back-wall at col 0 — sits BEHIND the buddy and runs the full
    # height of the world panel so the leftmost col is never empty (otherwise
    # trim / leading-whitespace handling can shift rows relative to each other).
    for r in range(WORLD_ROWS):
        if grid[r][BUDDY_WALL_COL][0] == " ":
            grid[r][BUDDY_WALL_COL] = ("|", "dark_green")

    # hat (if equipped) — multi-row, the BOTTOM row sits ON the head row
    # (sprite row 0, overlapping any head chars), additional rows stack
    # upward into the previously-empty sky above the buddy. Centered on the
    # true visual center of the head, rounded so even-char-count head ranges
    # (like `__` at cols 7-8, center 7.5) don't accumulate a half-col offset.
    from data import HATS, RARITY_COLOR
    hat = core.get_equipped(sv, pet, "hat")
    if hat:
        hat_lines = HATS.get(hat["type"], [""])
        if isinstance(hat_lines, str):
            hat_lines = [hat_lines]
        hat_color = RARITY_COLOR.get(hat["rarity"], "white")
        hat_h = len(hat_lines)
        hat_w = max((len(ln) for ln in hat_lines), default=0)
        # Bottom row of hat lands on sprite row 0; rest stacks up.
        hat_top = sprite_top - hat_h + 1
        # Find the head row to center the hat on. Try row 0 first; if empty
        # (chicken's placeholder row), fall through to row 1, etc., so the
        # hat lines up with the actual head chars wherever they live.
        head_center = None
        for ridx in range(min(len(sprite), 3)):
            head_row_chars = [i for i, c in enumerate(sprite[ridx]) if c != " "]
            if head_row_chars:
                head_center = (head_row_chars[0] + head_row_chars[-1]) / 2
                break
        if head_center is not None:
            # int(x + 0.5) instead of round() — Python's round uses banker's
            # rounding so round(0.5)==0, which would shift the hat one col
            # left for heads whose center lands on .5.
            hat_col = buddy_screen + int(head_center - hat_w / 2 + 0.5)
        else:
            hat_col = buddy_screen + max(0, (sprite_w - hat_w) // 2)
        # Bottom hat row overlaps the head row — wipe ALL cols in its
        # footprint (even where the hat has spaces) so the head chars
        # underneath don't peek through the hat's interior gaps.
        for i, line in enumerate(hat_lines):
            r = hat_top + i
            if not (0 <= r < WORLD_ROWS):
                continue
            is_bottom = (i == hat_h - 1)
            for j, ch in enumerate(line):
                cc = hat_col + j
                if not (0 <= cc < width):
                    continue
                if ch != " ":
                    grid[r][cc] = (ch, hat_color)
                elif is_bottom:
                    # space in the bottom row -> clear the cell so head
                    # chars under the hat don't show through
                    grid[r][cc] = (" ", None)

    # enemy + attack visual — uses the same world->screen mapping as features
    enc = st.get("encounter")
    if enc:
        info = ENEMIES.get(enc["key"], {})
        e_art = info.get("art", ["???"])
        e_color = info.get("color", "white")
        e_screen = BUDDY_TIP_COL + (enc["monster_col"] - cam)
        e_top = max(0, WORLD_ROWS - len(e_art))  # anchor enemy bottom to ground
        _stamp(grid, e_art, e_screen, e_top, e_color, width)

        # alert "!" above the enemy so it pops out of the landscape
        alert_row = e_top - 1
        if alert_row >= 0:
            alert_col = e_screen + len(e_art[0]) // 2
            if 0 <= alert_col < width:
                grid[alert_row][alert_col] = ("!", "magenta")

        # Combat attack/clash visuals removed — they were stamped into the
        # canopy rows (upper_row / lower_row) and overwrote tree art, breaking
        # the visual alignment. Combat is still narrated in the info row
        # ("X strikes!", "Y counters!", "CLASH!").

    # render with ANSI segment batching
    rows = []
    for r in range(WORLD_ROWS):
        out, cur = "", None
        for ch, col in grid[r]:
            if col != cur:
                if cur is not None:
                    out += RESET
                if col:
                    out += COLORS.get(col, "")
                cur = col
            out += ch
        if cur is not None:
            out += RESET
        rows.append(out)
    # trim any all-whitespace rows from the top so the buddy/hat anchor at top
    # with no empty gap floating above
    import re
    _ansi = re.compile(r"\x1b\[[0-9;]*m")
    while rows and _ansi.sub("", rows[0]).strip() == "":
        rows.pop(0)
    return "\n".join(rows)
