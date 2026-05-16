"""Ambient top-down adventure for the buddy status line.

The active pet walks rightward through a procedurally-generated landscape:
the camera follows so the pet stays at a fixed left-side column, and the
world (trees, bushes, grass, flowers) scrolls past. Wild monsters
occasionally spawn from the right, approach the pet, and resolve a quick
fight that awards XP and may drop a hat.

The status line is two regions:

  | <-- the back-wall, an anchor column that's always painted
  |
  |    <pet sprite>     <-- the buddy panel (fixed width, never scrolls)
  |
  | __pet feet__  ^^_/^^\\__,,___||___...   <-- the scrolling landscape

This module owns the world generation, combat sequencing, and rendering.
"""

import random, re, time

import core
from data import SPECIES, COLORS, RESET


# --- Layout constants ------------------------------------------------------
WORLD_ROWS = 7              # vertical height of the world in characters
STEP_SECONDS = 6            # one walk step per ~6 seconds real time
MAX_STEPS_PER_RENDER = 8    # cap so a long Claude Code idle doesn't teleport
SPAWN_DISTANCE = 24         # monster spawns this many world-cols ahead
BATTLE_GAP = 14             # monster_col - buddy_col when fighting starts

# Buddy panel layout (cols 0 -> BUDDY_PANEL_WIDTH-1):
#   col 0           : the back-wall '|' (visual anchor, always painted)
#   col BUDDY_OFFSET..: the pet sprite (3 cols in front of the wall)
#   col BUDDY_PANEL_WIDTH-1 : last col inside the panel
#   col BUDDY_PANEL_WIDTH+ : the scrolling landscape
#
# The panel width is fixed regardless of the pet's sprite width — that
# decouples landscape feature placement from sprite_w so switching pets
# leaves the trees / trunks / grass in the same screen columns. Max
# sprite width is 16 (cow), so 21 cols fits any pet + 3-col front
# offset + 2-col rear margin.
BUDDY_WALL_COL    = 0
BUDDY_OFFSET      = 3
BUDDY_PANEL_WIDTH = 21
BUDDY_TIP_COL     = BUDDY_PANEL_WIDTH - 1


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# --- Landscape feature builders --------------------------------------------
# Two body shapes:
#   _small_tree() : the classic 2-wide /\ pine, 4 rows tall, fits anywhere.
#   _big_tree()   : odd-width pyramidal canopy with || trunk centered.
# Both end with a trunk row that stamps ONLY || — surrounding cols are
# spaces so the dark-green ground texture flows under the canopy instead
# of being overwritten by a brown bar.

def _small_tree(rate, leaf_color):
    """A 2-wide x 4-row pine: three rows of `/\\` crown + an `||` trunk."""
    return {
        "rate": rate, "color": leaf_color,
        "row_colors": [leaf_color, leaf_color, leaf_color, "brown"],
        "art": ["/\\", "/\\", "/\\", "||"],
    }


def _big_tree(rate, leaf_color, tree_w=7, extra_rows=0):
    """An odd-width pyramidal tree.

    `tree_w` must be odd. The peak `^` and the `^` down the middle of
    every crown row land on the dead-center column. Each step down adds
    one more `/` on the left and one more `\\` on the right, so a 9-wide
    tree shows up to `////` and `\\\\\\\\` on its widest row.

      tree_w=7   -> 5 rows total (the default canopy tree)
      tree_w=9   -> 6 rows total (wider)
      tree_w=11  -> 7 rows total (widest that fits in WORLD_ROWS)
    `extra_rows` repeats the widest crown row N more times for taller trees.

    Trunk is `||` (2-wide) straddling the center: left pipe sits AT the
    center column under the peak.
    """
    assert tree_w % 2 == 1, "tree_w must be odd"
    half = tree_w // 2
    crown = [" " * half + "^" + " " * half]
    for i in range(1, half + 1):
        pad = " " * (half - i)
        crown.append(pad + "/" * i + "^" + "\\" * i + pad)
    crown += [crown[-1]] * extra_rows
    trunk = " " * half + "||" + " " * (half - 1)
    return {
        "rate": rate, "color": leaf_color,
        "row_colors": [leaf_color] * len(crown) + ["brown"],
        "art": crown + [trunk],
    }


def _christmas_tree(rate):
    """Ultra-rare Christmas tree (9 wide, 6 rows). Gold star at the peak,
    red ornaments through the crown, brown `||` trunk centered, red `[*]`
    present box off to the right side. Walking past one of these gives
    the pet a guaranteed Rare+ hat (handled in advance()).
    """
    art = [
        "    *    ",   # star at the peak (red)
        "   /^\\   ",
        "  //O\\\\  ",  # red O = ornament
        " ///^\\\\\\ ",
        "////O\\\\\\\\",
        "   || [*]",   # || trunk centered, gap, red [*] present off to side
    ]
    return {
        "rate": rate, "color": "forest_green",
        "row_colors": ["forest_green"] * 5 + ["brown"],
        "char_colors": {"*": "red", "O": "red", "[": "red", "]": "red"},
        "art": art,
    }


# --- Ground feature catalog ------------------------------------------------
# Spawn rates tuned for a forest that looks lived-in without being crowded.
# Rates are independent — each world position rolls a single feature pick
# against the cumulative sum.

GROUND_FEATURES = [
    # Small classic /\ pines — 2 wide, 4 rows, three color shades so a
    # forest of them looks varied instead of mass-produced.
    _small_tree(0.013, "pine_green"),
    _small_tree(0.012, "forest_green"),
    _small_tree(0.010, "lime_green"),

    # Standard pyramidal trees — 7 wide, 5 rows. Two color variants.
    _big_tree(0.009, "forest_green"),
    _big_tree(0.009, "green"),

    # Big variant — 7-row canopy that fills the world height. Rare; ends
    # up as an occasional landmark on the horizon.
    _big_tree(0.0005, "sage_green", extra_rows=2),
    _big_tree(0.0005, "pine_green", extra_rows=2),

    # Wider sizes — chunkier landmarks, even rarer.
    _big_tree(0.0004, "forest_green", tree_w=9),
    _big_tree(0.0002, "lime_green",   tree_w=11),

    # Ultra-rare Christmas tree (~1 in 20 000 world cols).
    _christmas_tree(0.00005),

    # Bushes — 2 rows, 5 cols wide.
    {"rate": 0.022, "color": "lime_green",
     "art": ["(***)", " \\*/ "]},

    # Grass tufts — single-row.
    {"rate": 0.018, "color": "forest_green", "art": [",,,"]},
    {"rate": 0.014, "color": "lime_green",   "art": ["vvv"]},

    # Flowers — 2 rows: red @ bloom over a green | stem.
    {"rate": 0.018, "color": "green",
     "char_colors": {"@": "red"},
     "art": ["\\@/", "*|*"]},
]


# --- Enemies ---------------------------------------------------------------
# Magenta = "danger" hue. A "!" alert renders directly above each enemy
# when it spawns so the eye picks it out against the landscape.

ENEMIES = {
    "rat":    {"xp": 200, "color": "magenta",
               "art": [" ,___,",  "(>.<)",   " V V "]},
    "bat":    {"xp": 250, "color": "magenta",
               "art": [" /\\_/\\", "( -.- )", " \\v_v/"]},
    "slime":  {"xp": 320, "color": "magenta",
               "art": ["  ___  ", " /X X\\", "(  v  )", " \\___/"]},
    "bun":    {"xp": 180, "color": "magenta",
               "art": ["(\\_/)",   "(>.<)",   '(")(")']},
    "blob":   {"xp": 400, "color": "magenta",
               "art": ["  ___ ", " /XXX\\", "(o   o)", " ~~~~ "]},
    "spider": {"xp": 280, "color": "magenta",
               "art": [" /\\___/\\", "(/X.X\\)", "//|V|\\\\", " V V V "]},
    "ghost":  {"xp": 500, "color": "magenta",
               "art": [" .===.",  "( X X )", "(  v  )", " ~vvv~"]},
    "bandit": {"xp": 600, "color": "magenta",
               "art": ["[#####]", " (>.<)",  " /|X|\\", " d   b"]},
}
ENEMY_KEYS = list(ENEMIES)


# --- Deterministic world generation ----------------------------------------
# Every random decision keyed on world position uses its own Random()
# seeded from `pos * <prime> + <salt>`, so the world is fully deterministic
# and you can revisit the same column to see the same trees.

def _ground_at(pos):
    """One ground-row character at this world position. Mostly `_`, with
    occasional `,` for subtle texture. Both chars sit at the descender so
    the horizon line stays visually flat."""
    rng = random.Random(pos * 53 + 5)
    return "," if rng.random() < 0.06 else "_"


def _pick_feature(pos, features, seed_salt):
    """Roll for a feature at this world position. Returns the feature dict
    or None. Salt + position uniquely seed the roll, so the same position
    rolls the same feature every render."""
    rng = random.Random(pos * 7919 + seed_salt)
    r = rng.random()
    acc = 0.0
    for f in features:
        acc += f["rate"]
        if r < acc:
            return f
    return None


def encounter_seed(pos):
    """Does an enemy spawn when the pet reaches this world position?
    Returns the enemy key or None. ~1 spawn per 33 walked cols on average."""
    if pos <= 0:
        return None
    rng = random.Random(pos * 31337 + 11)
    if rng.random() < 0.030:
        return ENEMY_KEYS[int(rng.random() * len(ENEMY_KEYS))]
    return None


# --- Christmas tree gift system -------------------------------------------
# Christmas trees are placed by _pick_feature() like any other big tree.
# When the pet walks INTO a Christmas tree's column, we hand it a free
# guaranteed-rare hat. Idempotent per position: re-walking doesn't dupe.

# Pre-compute the big-tree subset + christmas-tree handle once at import.
# (Doing this on every render walked the GROUND_FEATURES list twice per
# step — small but adds up since statusline.py runs every render.)
_BIG_TREES   = [f for f in GROUND_FEATURES if len(f["art"]) >= 6]
_XMAS_TREE   = next((f for f in _BIG_TREES if "[" in "".join(f["art"])), None)
_XMAS_LIMIT  = 50  # max world positions to remember as "already collected"


def _is_xmas_tree_at(pos):
    """True iff a Christmas tree spawns at this world position. Uses the
    SAME _pick_feature roll the renderer's big-tree pass uses, so it
    always agrees with what's drawn on screen."""
    if pos < 0 or _XMAS_TREE is None:
        return False
    return _pick_feature(pos, _BIG_TREES, 89) is _XMAS_TREE


def _xmas_gift(sv, pos):
    """Open the present at this Christmas tree if not already opened.
    Returns the dropped hat dict (also appended to inventory), or None
    if this position was already collected. Position-seeded so the same
    tree always gives the same hat."""
    from data import HATS
    st = _state(sv)
    collected = st.setdefault("xmas_collected", [])
    if pos in collected:
        return None
    collected.append(pos)
    # Bounded history — even at extreme play, 50 trees is plenty.
    if len(collected) > _XMAS_LIMIT:
        del collected[:-_XMAS_LIMIT]
    rng = random.Random(pos * 9999 + 7)
    # Rare-or-better roll, weighted toward Epic/Legendary.
    r = rng.random()
    if   r < 0.05: rarity = "Mythic"
    elif r < 0.25: rarity = "Legendary"
    elif r < 0.60: rarity = "Epic"
    else:          rarity = "Rare"
    hat_type = sorted(HATS.keys())[int(rng.random() * len(HATS))]
    drop = {"iid": "x%d" % pos, "slot": "hat",
            "type": hat_type, "rarity": rarity}
    sv["inventory"].append(drop)
    return drop


# --- Save-state helpers ----------------------------------------------------

def _state(sv):
    """Get-or-init the 'adventure' sub-dict of the save. Idempotent."""
    st = sv.setdefault("adventure", {})
    st.setdefault("buddy_col", 0)
    st.setdefault("last_tick", time.time())
    st.setdefault("encounter", None)
    st.setdefault("log", [])
    st.setdefault("steps", 0)
    st.setdefault("kills", 0)
    st.setdefault("losses", 0)
    return st


def _make_encounter(enemy_key, buddy_col):
    """Build a fresh encounter dict in 'approach' phase."""
    return {
        "key": enemy_key,
        "phase": "approach",
        "monster_col": buddy_col + SPAWN_DISTANCE,
        "turn": 0,
        "outcome": None,
    }


def _log(st, line):
    """Append to the rolling combat log, keeping at most the last 3 entries."""
    log = st.setdefault("log", [])
    log.append(line)
    del log[:-3]


# --- Combat ---------------------------------------------------------------
# A fight runs over 4 ticks during the 'fighting' phase:
#   turn 1 : pet attacks (animation only)
#   turn 2 : enemy counters (animation only)
#   turn 3 : compute outcome, apply XP + possible drop
#   turn 4 : clear the encounter, pet resumes walking

def _combat_turn(sv, pet, st):
    """Advance one tick of the current fight. Returns a list of events
    the caller can use for UI feedback."""
    enc = st["encounter"]
    enc["turn"] += 1

    # Turns 1-2: pure visual ticks (we used to render attack glyphs here,
    # but they overlapped tree art badly — narration in the info row now).
    if enc["turn"] in (1, 2):
        return [{"type": "attack",
                 "attacker": "buddy" if enc["turn"] == 1 else "monster"}]

    # Turn 3: roll the outcome and apply XP.
    if enc["turn"] == 3:
        ts = core.total_stats(pet)
        rng = random.Random()
        # Win chance is bounded [0.30, 0.92], biased by the pet's
        # debugging+chaos stats. Mediocre pets still win sometimes.
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
            _log(st, msg)
            return [{"type": "win", "xp": xp, "drop": drop}]
        else:
            xp = e_info["xp"] // 5   # consolation XP for losing
            core.apply_xp(sv, pet, xp)
            st["losses"] = st.get("losses", 0) + 1
            enc["outcome"] = "loss"
            _log(st, "lost to %s +%dxp" % (enc["key"], xp))
            return [{"type": "loss", "xp": xp}]

    # Turn 4: clear and walk on.
    st["encounter"] = None
    return []


def advance(sv, pet):
    """Tick the world forward based on real elapsed time since the last
    render. Walks the pet right, runs encounter approach/fight sequencing,
    and claims Christmas tree gifts as the pet walks past them. Returns
    a list of events for the caller (typically the status line) to surface."""
    st = _state(sv)
    now = time.time()
    elapsed = max(0, now - st.get("last_tick", now))
    st["last_tick"] = now

    natural = min(MAX_STEPS_PER_RENDER, int(elapsed / STEP_SECONDS))
    # Always tick at least once during an active encounter so combat
    # animates even between renders that come faster than STEP_SECONDS.
    steps = max(1, natural) if st.get("encounter") else natural

    events = []
    for _ in range(steps):
        enc = st.get("encounter")
        if enc and enc["phase"] == "approach":
            # Pet walks right, monster walks left, meet in the middle.
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

        # No encounter — walk right one col + check for Christmas tree + roll for spawn.
        st["buddy_col"] += 1
        st["steps"] = st.get("steps", 0) + 1

        if _is_xmas_tree_at(st["buddy_col"]):
            gift = _xmas_gift(sv, st["buddy_col"])
            if gift:
                _log(st, "xmas gift +%s %s" % (gift["rarity"], gift["type"]))
                events.append({"type": "xmas_gift", "drop": gift})

        ek = encounter_seed(st["buddy_col"])
        if ek:
            st["encounter"] = _make_encounter(ek, st["buddy_col"])
            events.append({"type": "encounter", "enemy": ek})
            break

    return events


# --- Rendering ------------------------------------------------------------

def _stamp(grid, art, col, row, color, width, char_colors=None):
    """Paint a multi-line sprite onto the grid. Spaces in `art` pass through
    (don't overwrite what's already there). `char_colors` lets a feature
    override the color of specific glyphs — e.g. the Christmas tree's red
    ornaments on top of its green crown."""
    for i, line in enumerate(art):
        r = row + i
        if not (0 <= r < WORLD_ROWS):
            continue
        for j, ch in enumerate(line):
            c = col + j
            if 0 <= c < width and ch != " ":
                col_for_char = (char_colors[ch]
                                if (char_colors and ch in char_colors)
                                else color)
                grid[r][c] = (ch, col_for_char)


def _enemy_protect_zone(st, cam):
    """Cols around the (preview-)enemy that landscape features must avoid,
    so the enemy doesn't get covered by a tree on spawn."""
    enc = st.get("encounter")
    if not enc:
        return None
    e_art = ENEMIES.get(enc["key"], {}).get("art", [])
    e_w   = max((len(ln) for ln in e_art), default=0)
    e_screen = BUDDY_TIP_COL + (enc["monster_col"] - cam)
    return (e_screen - 2, e_screen + e_w + 2)


def _hat_top_left(sprite, sprite_w, hat_w, buddy_screen):
    """Where the top-left of a hat should land for the given pet sprite.
    Falls through empty top rows (chicken-style placeholder) to find the
    real head row so the hat sits ON the head, not in the air above it."""
    head_center = None
    for ridx in range(min(len(sprite), 3)):
        chars = [i for i, c in enumerate(sprite[ridx]) if c != " "]
        if chars:
            head_center = (chars[0] + chars[-1]) / 2
            break
    if head_center is None:
        return buddy_screen + max(0, (sprite_w - hat_w) // 2)
    # int(x + 0.5) for half-up rounding — Python's round() uses banker's
    # rounding so round(0.5)==0 would shift hats one col left.
    return buddy_screen + int(head_center - hat_w / 2 + 0.5)


def _stamp_hat(grid, sprite, sprite_top, sprite_w, buddy_screen, hat, width):
    """Paint a multi-row hat above the pet. The bottom row sits ON sprite
    row 0 (the head) — wipes spaces too so head chars don't peek through
    the hat's interior gaps."""
    from data import HATS, RARITY_COLOR
    hat_lines = HATS.get(hat["type"], [""])
    if isinstance(hat_lines, str):
        hat_lines = [hat_lines]
    hat_color = RARITY_COLOR.get(hat["rarity"], "white")
    hat_h = len(hat_lines)
    hat_w = max((len(ln) for ln in hat_lines), default=0)
    hat_top = sprite_top - hat_h + 1
    hat_col = _hat_top_left(sprite, sprite_w, hat_w, buddy_screen)
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
                # Bottom row clears head cells under the hat even where the
                # hat has spaces, so e.g. `( O )` doesn't show the head's
                # `__` peeking through the gaps between the parens and O.
                grid[r][cc] = (" ", None)


def _place_features(grid, cam, width, enemy_protect):
    """Run the two-pass feature placement: big trees first, then small
    features fill in around them. Big trees go first so they aren't
    crowded out by an earlier small-feature roll."""

    def wp_at(c):
        # World position visible at screen col c.
        # At c == BUDDY_TIP_COL the col under the buddy is at world pos `cam`.
        return cam + (c - BUDDY_TIP_COL)

    def _place(feat, c):
        """Stamp a feature at screen col c. Returns its width or 0 if it
        was blocked by the enemy protect zone."""
        feat_w = max(len(ln) for ln in feat["art"])
        if enemy_protect and c + feat_w >= enemy_protect[0] and c <= enemy_protect[1]:
            return 0
        h   = len(feat["art"])
        top = WORLD_ROWS - h
        row_colors  = feat.get("row_colors")
        char_colors = feat.get("char_colors")
        if row_colors:
            for i, line in enumerate(feat["art"]):
                rc = row_colors[i] if i < len(row_colors) else feat["color"]
                _stamp(grid, [line], c, top + i, rc, width, char_colors)
        else:
            _stamp(grid, feat["art"], c, top, feat["color"], width, char_colors)
        return feat_w

    big_trees   = _BIG_TREES
    small_feats = [f for f in GROUND_FEATURES if len(f["art"]) < 6]
    occupied    = [False] * width

    # Pass 1: big trees with 6-col min spacing so they don't cluster.
    last_big_end = -100
    for c in range(BUDDY_PANEL_WIDTH, width):
        if c < last_big_end + 6:
            continue
        feat = _pick_feature(wp_at(c), big_trees, seed_salt=89)
        if not feat:
            continue
        feat_w = _place(feat, c)
        if feat_w > 0:
            last_big_end = c + feat_w
            for k in range(c, min(width, c + feat_w)):
                occupied[k] = True

    # Pass 2: small features fill remaining gaps. Skip cols owned by big trees.
    last_feat_end = -100
    for c in range(BUDDY_PANEL_WIDTH, width):
        if c < last_feat_end + 2 or occupied[c]:
            continue
        feat = _pick_feature(wp_at(c), small_feats, seed_salt=53)
        if not feat:
            continue
        feat_w = max(len(ln) for ln in feat["art"])
        if any(occupied[k] for k in range(c, min(width, c + feat_w))):
            continue
        placed_w = _place(feat, c)
        if placed_w > 0:
            last_feat_end = c + placed_w


def _render_grid(grid):
    """Convert the grid of (char, color) tuples into ANSI-colored row strings,
    batching adjacent same-color cells into a single color span."""
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
    return rows


def render_world(sv, pet, width=140):
    """Render the full world for one frame: ground line, landscape features,
    pet sprite, back-wall anchor, hat, and (if present) enemy + alert."""
    st = _state(sv)
    cam = st["buddy_col"]

    sp = SPECIES[pet["species"]]
    sprite = [ln.replace("{e}", pet["eyes"]) for ln in sp["art"]]
    sprite_h = len(sprite)
    sprite_w = max((len(ln) for ln in sprite), default=0)
    lvl_color = core.color_for_level(pet["level"])
    sprite_top = max(0, WORLD_ROWS - sprite_h)
    buddy_screen = BUDDY_OFFSET

    # Blank grid + ground line. The horizon is dark green across the WHOLE
    # width so it flows continuously past the buddy panel into the landscape.
    grid = [[(" ", None) for _ in range(width)] for _ in range(WORLD_ROWS)]
    for c in range(width):
        wp = cam + (c - BUDDY_TIP_COL)
        grid[WORLD_ROWS - 1][c] = (_ground_at(wp), "dark_green")

    # Landscape (trees, bushes, grass, flowers).
    _place_features(grid, cam, width, _enemy_protect_zone(st, cam))

    # Pet sprite (overstamps anything it lands on inside the panel).
    _stamp(grid, sprite, buddy_screen, sprite_top, lvl_color, width)

    # Vertical back-wall at col 0 — runs the full height of the panel so
    # the leftmost col is never empty (otherwise a terminal's leading-
    # whitespace handling could shift rows relative to each other).
    for r in range(WORLD_ROWS):
        if grid[r][BUDDY_WALL_COL][0] == " ":
            grid[r][BUDDY_WALL_COL] = ("|", "dark_green")

    # Hat (multi-row, sits ON the head row).
    hat = core.get_equipped(sv, pet, "hat")
    if hat:
        _stamp_hat(grid, sprite, sprite_top, sprite_w, buddy_screen, hat, width)

    # Enemy + "!" alert (only during an active encounter).
    enc = st.get("encounter")
    if enc:
        info = ENEMIES.get(enc["key"], {})
        e_art   = info.get("art", ["???"])
        e_color = info.get("color", "white")
        e_screen = BUDDY_TIP_COL + (enc["monster_col"] - cam)
        e_top    = max(0, WORLD_ROWS - len(e_art))
        _stamp(grid, e_art, e_screen, e_top, e_color, width)
        alert_row = e_top - 1
        if alert_row >= 0:
            alert_col = e_screen + len(e_art[0]) // 2
            if 0 <= alert_col < width:
                grid[alert_row][alert_col] = ("!", "magenta")

    # Render grid -> ANSI strings, then trim purely-empty rows from the
    # top so a short pet doesn't hover below a stack of blank rows.
    rows = _render_grid(grid)
    while rows and _ANSI_RE.sub("", rows[0]).strip() == "":
        rows.pop(0)
    return "\n".join(rows)
