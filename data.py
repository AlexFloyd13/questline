"""Static data for the buddy system.

Everything that doesn't change at runtime lives here:
  - stat names, species pools, rarity tables
  - ANSI color codes
  - the leveling curve (xp_to_next)
  - the hat catalog and drop tables
  - per-species sprite art (in the SPECIES dict at the bottom)

If you want to add a new species, the steps are:
  1. add an entry to SPECIES with art, mini-face, and theme stats
  2. add the species name to SPECIES_TIERS (which rarity tier it spawns in)
  3. add a list of cute name candidates to NAMES
  4. if the art is third-party, add an attribution line to ART_CREDITS
"""

# --- Stats -----------------------------------------------------------------
# Each pet has five stats. Two of them (the species "theme") gain faster
# during level-up. Stats are cosmetic — they don't affect combat much.

STATS = ["debugging", "patience", "chaos", "wisdom", "snark"]

STAT_LABELS = {
    "debugging": "DEBUGGING",
    "patience":  "PATIENCE",
    "chaos":     "CHAOS",
    "wisdom":    "WISDOM",
    "snark":     "SNARK",
}


# --- Pet generation seed ---------------------------------------------------
# SALT mixes into the deterministic hash that picks each user's FIRST pet's
# species, stats, eyes, and name (so the starter pet is reproducible per-user
# across reinstalls). It is NOT a secret — change it only if you want to
# wipe everyone's starter-pet identity on upgrade. Combat outcomes, drops,
# and encounters are all rolled with their own seeds and don't touch SALT.

SALT = "friend-2026-401"


# --- Rarity ----------------------------------------------------------------
# Rolled at pet generation (low roll = rare). Each tier maps to a pool of
# species in SPECIES_TIERS below.

PET_RARITY_TABLE = [
    ("Legendary", 0.01),
    ("Epic",      0.05),
    ("Rare",      0.15),
    ("Uncommon",  0.40),
    ("Common",    1.00),
]

SPECIES_TIERS = {
    "Common":    ["duck", "cat", "rabbit", "owl", "mushroom", "ghost",
                  "penguin", "bird"],
    "Uncommon":  ["pig", "snail", "turtle", "crab", "fish"],
    "Rare":      ["robot", "dog", "octopus"],
    "Epic":      ["chonk", "cow"],
    "Legendary": ["chicken"],
}

RARITY_STARS = {
    "Common": "*", "Uncommon": "**", "Rare": "***",
    "Epic":  "****", "Legendary": "*****", "Mythic": "******",
}

RARITY_COLOR = {
    "Common": "white", "Uncommon": "green", "Rare": "cyan",
    "Epic":   "blue",  "Legendary": "magenta", "Mythic": "gold",
}


# --- ANSI color palette ----------------------------------------------------
# 16-color ANSI for the basics; 256-color for the foliage greens since they
# need finer shading. Anything not in this dict renders uncolored.

COLORS = {
    "white":         "\033[97m",
    "green":         "\033[92m",
    "cyan":          "\033[96m",
    "blue":          "\033[94m",
    "magenta":       "\033[95m",
    "silver":        "\033[38;5;250m",   # L76-99 — precursor to gold
    "gold":          "\033[38;5;220m",   # L100+ — only the true max-level pets
    "brown":         "\033[38;5;130m",   # tree trunks
    "dark_green":    "\033[38;5;22m",    # ground line
    "pine_green":    "\033[38;5;28m",    # darkest tree foliage
    "forest_green":  "\033[38;5;34m",    # standard tree foliage
    "lime_green":    "\033[38;5;76m",    # bright young foliage
    "sage_green":    "\033[38;5;108m",   # soft greyish-green
    "yellow":        "\033[33m",
    "red":           "\033[91m",         # flowers, apples, christmas
}

RESET = "\033[0m"

# As your pet levels up, its sprite color climbs this ladder. The first
# entry whose threshold is >= the pet's level wins.
# Gold (L100+) is the prestige tier — reaching it is the goal of the
# whole grind. Silver (L76-99) is the "almost there" precursor.
LEVEL_COLOR_BANDS = [
    (5,     "white"),
    (15,    "green"),
    (30,    "cyan"),
    (50,    "blue"),
    (75,    "magenta"),
    (99,    "silver"),
    (10**9, "gold"),
]


# --- Leveling --------------------------------------------------------------
# `xp_to_next(level)` returns the XP required to go from `level` to
# `level+1`. XP is just your raw Claude token usage from the transcript:
# every assistant message contributes its input + output + cache-creation
# tokens to the active pet.
#
# Curve is calibrated against max-tier Claude Max-20 usage (~200M tokens
# over 3 months). Cumulative milestones:
#
#   L20  ~4.5M tokens   (~2 days at max)    -- early game, levels fly
#   L50  ~37M tokens    (~17 days)          -- mid game
#   L75  ~97M tokens    (~6 weeks)          -- expert
#   L100 ~200M tokens   (~3 months)         -- MAX LEVEL, end game
#
# You can spread XP across multiple pets via `/buddy switch <n>` — each pet
# has its own L1->L100 grind from scratch.

def xp_to_next(level):
    return 20000 * level + 300 * level * level


# Which fields in Claude's transcript JSON count toward XP.
# (cache_read is excluded — it's huge and effectively free, would warp the curve.)
XP_TOKEN_FIELDS = ["input_tokens", "output_tokens", "cache_creation_input_tokens"]


# --- Drops -----------------------------------------------------------------
# Drop chance is rolled at level-up and after winning a fight. The rarity
# of what drops is rolled independently against ITEM_RARITY_TABLE.

DROP_CHANCE_ON_LEVELUP = 0.20    # rolled on every level-up
DROP_CHANCE_ON_WIN     = 0.06    # rolled on every fight win

# Cumulative thresholds, low roll = rare. Base values are the L1 "vanilla"
# distribution. Level scaling in core.make_drop subtracts a small per-level
# boost from the roll, so higher-level pets see rarer bands more often.
# Calibrated so Mythic tops out at ~5% at L100 (and stays much rarer below).
ITEM_RARITY_TABLE = [
    ("Mythic",    0.005),   # 0.5% at L1, 5% at L100
    ("Legendary", 0.030),   # 2.5% at L1, 7% at L100
    ("Epic",      0.110),   # 8% at L1, 12.5% at L100
    ("Rare",      0.250),   # 14% at L1, 18.5% at L100
    ("Uncommon",  0.500),   # 25% at L1, 25% at L100
    ("Common",    1.000),   # 50% at L1, 32% at L100
]


# --- Hats ------------------------------------------------------------------
# Each hat is a list of rows. The BOTTOM row sits ON the buddy's head row
# (sprite row 0), overlapping any head chars there; additional rows stack
# upward into the previously-empty sky above the buddy.
#
# Hats are the only equipment slot. Held items existed in an earlier draft
# but were removed — they fought the buddy silhouette for screen space.

HATS = {
    "beanie":    [" () ",     "(===)"],                  # knit cap + pom
    "flower":    [" * ",      " | "],                    # bloom + stem
    "top_hat":   [" |#| ",    "[___]"],                  # tall hat + wide brim
    "wizard":    [" /\\ ",    "//\\\\",     "[___]"],    # pointed hat + band
    "cowboy":    [" []  ",    "[===]"],                  # boxy crown stetson
    "party":     ["  *  ",    " /^\\ ",     "/o^o\\"],   # birthday cone
    "propeller": ["  +  ",    "  |  ",      "<###>"],    # spinner beanie
    "crown":     [" v v ",    "vWvWv"],                  # jeweled crown
    "halo":      [" ~~~ ",    "( O )"],                  # glowing halo
}

# All possible drops (currently hats only — items were removed).
ALL_DROPS = [("hat", h) for h in HATS]


# --- Eye styles ------------------------------------------------------------
# Each pet rolls one of these as its eye character. Sprites use `{e}` as the
# placeholder so `cat` (`| {e}_{e} |`) becomes `| o_o |` for an "o"-eyed cat.

EYE_STYLES = ["o", "O", "^", "*", "~", "x", "u", "v", "@", "."]


# --- Cute name pools -------------------------------------------------------
# Keyed by species. The starter pet picks deterministically from these;
# subsequent pets roll randomly.

NAMES = {
    "duck":     ["Quackers", "Waddles", "Puddles", "Mallard", "Ducky"],
    "cat":      ["Void", "Glitch", "Shadow", "Mittens", "Bytez"],
    "rabbit":   ["Bun", "Hopscotch", "Clover", "Cotton", "Nibbles"],
    "owl":      ["Hoot", "Nox", "Sage", "Archimedes", "Orion"],
    "penguin":  ["Tux", "Pebble", "Waddle", "Chilly", "Flippers"],
    "turtle":   ["Turbo", "Sheldon", "Mossy", "Patience", "Drifter"],
    "snail":    ["Zippy", "Spiral", "Shelly", "Slick", "Goo"],
    "octopus":  ["Inky", "Eight", "Squish", "Tangle", "Bloop"],
    "ghost":    ["Boo", "Specter", "Wisp", "Null", "Casper"],
    "robot":    ["Unit-7", "Bleep", "Glitch", "Servo", "Bit"],
    "mushroom": ["Spore", "Fungi", "Morel", "Cap", "Myco"],
    "chonk":    ["BigBoi", "Thicc", "Unit", "Absolute", "Chonky"],
    "crab":     ["Pinch", "Sidewise", "Scuttle", "Snapper", "Clackers"],
    "fish":     ["Bubbles", "Finn", "Sushi", "Splash", "Gilligan"],
    "dog":      ["Rover", "Biscuit", "Scruff", "Wags", "Bandit"],
    "cow":      ["Moo", "Bessie", "Daisy", "Spots", "Buttercup"],
    "pig":      ["Wilbur", "Hamlet", "Porkchop", "Truffle", "Snorts"],
    "bird":     ["Tweet", "Whistle", "Pip", "Skybit", "Featherly"],
    "chicken":  ["Cluck", "Henrietta", "Drumstick", "Beaks", "Coop"],
}


# --- Art attribution for OSS ----------------------------------------------
# When a sprite is adapted from a third-party design, credit goes here so
# the original artist is preserved even if the in-render signature was
# stripped for layout reasons. Add an entry whenever you add a new sprite
# that isn't your own original work.

ART_CREDITS = {
    "fish":    "Max (user-provided design)",
    "pig":     "Unknown — user-provided design",
    "bird":    "mrf (signature stripped from render, credited here)",
    "chicken": "Unknown — user-provided design",
    "cat":     "asciiart.eu (canonical 3-row cat face)",
    "dog":     "Joan G. Stark (jgs) — classic sitting-dog ASCII "
               "(signature stripped from render)",
    "cow":     "Tony Monroe / cowsay default.cow — "
               "https://en.wikipedia.org/wiki/Cowsay",
}


# --- Species sprites -------------------------------------------------------
# Each species is keyed by name and has:
#   theme : two stats that gain faster on level-up
#   mini  : compact one-line face for the /buddy switch summary
#   art   : list of strings, one per sprite row. {e} is replaced by the
#           pet's eye character at render time.
#
# Within a species, every row in `art` MUST be the same width — otherwise
# the silhouette goes ragged on the left or right edge. The first row
# (row 0) is treated as the "head" row by the hat renderer; if it's all
# spaces, the renderer falls through to row 1 (used by the chicken so the
# hat lands above the actual head instead of overwriting it).

SPECIES = {
    # 3 rows x 7 cols — side-profile duck with body + beak
    "duck": {
        "theme": ["patience", "wisdom"],
        "mini":  "({e}_>",
        "art": [
            "  __   ",
            "__({e}_)>",
            " \\___/ ",
        ],
    },

    # 3 rows x 7 cols — proven asciiart.eu cat face design
    "cat": {
        "theme": ["snark", "chaos"],
        "mini":  "({e}_{e})",
        "art": [
            "|\\---/|",
            "| {e}_{e} |",
            " \\_^_/ ",
        ],
    },

    # 3 rows x 7 cols — long bunny ears + paws
    "rabbit": {
        "theme": ["patience", "debugging"],
        "mini":  "({e}.{e})",
        "art": [
            " (\\(\\  ",
            " ({e}.{e}) ",
            "(\")_(\")",
        ],
    },

    # 4 rows x 5 cols — ear tufts + Y-beak + talons
    "owl": {
        "theme": ["wisdom", "debugging"],
        "mini":  "({e}Y{e})",
        "art": [
            ",___,",
            "({e}Y{e})",
            "/( )\\",
            " ^_^ ",
        ],
    },

    # 4 rows x 11 cols — toadstool with rounded cap (parens, not slashes)
    "mushroom": {
        "theme": ["wisdom", "chaos"],
        "mini":  "(@_@)",
        "art": [
            "   _____   ",
            "  (,_,_,)  ",
            " (_______) ",
            "    |{e}|    ",
        ],
    },

    # 3 rows x 5 cols — hollow eyes + wavy tail
    "ghost": {
        "theme": ["chaos", "wisdom"],
        "mini":  "({e} {e})",
        "art": [
            ",---,",
            "({e} {e})",
            ")~v~(",
        ],
    },

    # 5 rows x 7 cols — slimmer octopus with curling tentacles
    "octopus": {
        "theme": ["wisdom", "debugging"],
        "mini":  "({e}.{e})",
        "art": [
            "  ___  ",
            " /   \\ ",
            " ({e}.{e}) ",
            " \\___/ ",
            " )()() ",
        ],
    },

    # 4 rows x 11 cols — antenna stalks, spiral shell, body extending right
    "snail": {
        "theme": ["patience", "wisdom"],
        "mini":  "@({e})",
        "art": [
            "    ,_,    ",
            "  __(@)__  ",
            " /@@@@@\\__ ",
            "(________{e}>",
        ],
    },

    # 4 rows x 11 cols — domed shell, segmented body with eyes, four legs
    "turtle": {
        "theme": ["patience", "wisdom"],
        "mini":  "({e}.{e})",
        "art": [
            "   ,___,   ",
            "  /,___,\\  ",
            " ({e}|---|{e}) ",
            "  ^^   ^^  ",
        ],
    },

    # 3 rows x 9 cols — wide shell, claws extending sideways, legs below
    "crab": {
        "theme": ["chaos", "patience"],
        "mini":  "<({e}_{e})>",
        "art": [
            "  _____  ",
            "<({e}___{e})>",
            " //\\_//\\ ",
        ],
    },

    # 5 rows x 7 cols — head with beak, body, flippers, feet
    # Source: https://www.asciiart.eu/animals/birds-land
    "penguin": {
        "theme": ["debugging", "patience"],
        "mini":  "({e}<",
        "art": [
            "   _   ",
            "  ({e}<  ",
            " /|||\\ ",
            " ||||| ",
            "  d b  ",
        ],
    },

    # 4 rows x 7 cols — symmetric fish (Max, user-provided)
    "fish": {
        "theme": ["wisdom", "patience"],
        "mini":  "({e}_)<",
        "art": [
            "   _   ",
            "  /_|  ",
            " ({e}_)<|",
            "  \\_|  ",
        ],
    },

    # 4 rows x 11 cols — sitting dog (Joan G. Stark; signature stripped
    # from render, credit in ART_CREDITS).
    "dog": {
        "theme": ["patience", "chaos"],
        "mini":  "(__()",
        "art": [
            "       __  ",
            "  (___()'`;",
            "  /,    /` ",
            "  \\\"---\\\\  ",
        ],
    },

    # 5 rows x 12 cols — the classic cowsay cow (trimmed to 5 rows).
    # Source: https://github.com/piuccio/cowsay (default.cow)
    "cow": {
        "theme": ["patience", "wisdom"],
        "mini":  "({e}{e})",
        "art": [
            "  ^__^      ",
            "  ({e}{e})\\____ ",
            "  (__)\\    \\",
            "      ||--w|",
            "      ||  ||",
        ],
    },

    # 4 rows x 5 cols — antenna, screen face, boxy body, feet
    "robot": {
        "theme": ["debugging", "patience"],
        "mini":  "[{e}.{e}]",
        "art": [
            " [+] ",
            "[{e}.{e}]",
            "|[#]|",
            " d b ",
        ],
    },

    # 4 rows x 7 cols — very round, fully closed loop
    "chonk": {
        "theme": ["patience", "snark"],
        "mini":  "({e} {e})",
        "art": [
            ".-----.",
            "( {e}_{e} )",
            "(     )",
            "'-----'",
        ],
    },

    # 4 rows x 11 cols — pig with curly tail (user-provided design)
    "pig": {
        "theme": ["patience", "chaos"],
        "mini":  "({e}{e})",
        "art": [
            "   _____   ",
            "^..^     \\9",
            "({e}{e})_____/ ",
            "   WW  WW  ",
        ],
    },

    # 4 rows x 7 cols — bird side profile (mrf design; signature stripped).
    "bird": {
        "theme": ["chaos", "wisdom"],
        "mini":  ">{e} )",
        "art": [
            "   ,_  ",
            "  >{e} ) ",
            "  ( ( \\",
            "   ''|\\",
        ],
    },

    # 5 rows x 6 cols — chicken with wing flap. Row 0 is an empty
    # placeholder (was a `\` feather; removed) so hats land on row 0
    # without overwriting the actual head at row 1.
    "chicken": {
        "theme": ["chaos", "debugging"],
        "mini":  "({e}>",
        "art": [
            "      ",
            "  ({e}> ",
            "\\_//) ",
            " \\_/_)",
            "  _|_ ",
        ],
    },
}
