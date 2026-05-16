"""Static data for the Claude Code buddy system: species, art, items, tables."""

STATS = ["debugging", "patience", "chaos", "wisdom", "snark"]
STAT_LABELS = {
    "debugging": "DEBUGGING",
    "patience": "PATIENCE",
    "chaos": "CHAOS",
    "wisdom": "WISDOM",
    "snark": "SNARK",
}

# --- generation seed ---
# SALT mixes into the deterministic hash that picks each user's FIRST pet's
# species, stats, and name (so it's reproducible per-user across reinstalls).
# It's not a secret — change it only if you want to wipe everyone's "starter
# pet" identity on upgrade. Combat / drops / encounters do NOT use this seed.
SALT = "friend-2026-401"

# --- pet rarity (innate, rolled at generation) -> species pool ---
# Dropped: goose, penguin, axolotl, blob, cactus, capybara (designs were weak).
# 12 species remain. Empty tiers (none currently) fall back in core._roll_attrs.
SPECIES_TIERS = {
    "Common":    ["duck", "cat", "rabbit", "owl", "mushroom", "ghost", "penguin", "bird"],
    "Uncommon":  ["pig", "snail", "turtle", "crab", "fish"],
    "Rare":      ["robot", "dog"],
    "Epic":      ["chonk", "cow"],
    "Legendary": ["chicken"],
}

# Art credits for open-source attribution. Add new species here when
# adapting third-party ASCII art so credit is preserved on release.
ART_CREDITS = {
    "fish":    "Max (user-provided design)",
    "pig":     "Unknown — user-provided design",
    "bird":    "mrf (signature stripped from render, credited here)",
    "chicken": "Unknown — user-provided design",
    "cat":     "asciiart.eu (canonical 3-row cat face)",
    "dog":     "Joan G. Stark (jgs) — classic sitting-dog ASCII (signature stripped from render)",
    "cow":     "Tony Monroe / cowsay default.cow — https://en.wikipedia.org/wiki/Cowsay",
    "frog":    "Joan G. Stark — https://www.asciiart.eu/animals/frogs (no longer in roster)",
}
# cumulative thresholds, low roll = rare
PET_RARITY_TABLE = [
    ("Legendary", 0.01),
    ("Epic",      0.05),
    ("Rare",      0.15),
    ("Uncommon",  0.40),
    ("Common",    1.00),
]
RARITY_STARS = {
    "Common": "*", "Uncommon": "**", "Rare": "***",
    "Epic": "****", "Legendary": "*****", "Mythic": "******",
}

# --- unified 6-tier color system (ANSI) ---
COLORS = {
    "white":       "\033[97m",
    "green":       "\033[92m",
    "cyan":        "\033[96m",
    "blue":        "\033[94m",
    "magenta":     "\033[95m",
    "gold":        "\033[38;5;220m",
    "brown":       "\033[38;5;130m",  # tree trunks
    "dark_green":  "\033[38;5;22m",   # ground line
    "pine_green":  "\033[38;5;28m",   # darkest tree foliage
    "forest_green":"\033[38;5;34m",   # standard tree foliage
    "lime_green":  "\033[38;5;76m",   # bright young foliage
    "sage_green":  "\033[38;5;108m",  # soft greyish-green
    "yellow":      "\033[33m",         # bushes
    "red":         "\033[91m",         # flowers
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RARITY_COLOR = {
    "Common": "white", "Uncommon": "green", "Rare": "cyan",
    "Epic": "blue", "Legendary": "magenta", "Mythic": "gold",
}

# level -> color ladder (this is what "leveling changes colors" means)
LEVEL_COLOR_BANDS = [
    (5, "white"),
    (15, "green"),
    (30, "cyan"),
    (50, "blue"),
    (75, "magenta"),
    (10**9, "gold"),
]

# --- leveling: tokens are XP, escalating curve ---
# xp needed to go from `level` to `level+1`. Calibrated so a single pet
# reaches L100 ("max level") in ~3 months of MAX Claude Max-20 usage
# (~200M tokens). With multiple pets, you can spread XP across the team by
# /buddy switch <n> — each pet has its own L1->L100 grind.
# Distribution:
#   L20  cumulative   4.5M  (~2 days of max usage)   <- early game, fast
#   L50  cumulative  38M    (~17 days)               <- mid game
#   L75  cumulative  98M    (~6 weeks)               <- expert
#   L100 cumulative 200M    (~3 months, MAX LEVEL)   <- end game
def xp_to_next(level):
    return 20000 * level + 300 * level * level

# which transcript usage fields count as XP (cache_read excluded - too cheap/huge)
XP_TOKEN_FIELDS = ["input_tokens", "output_tokens", "cache_creation_input_tokens"]

# --- drops ---
DROP_CHANCE_ON_LEVELUP = 0.20
DROP_CHANCE_ON_WIN = 0.35
# item/hat rarity is rolled independently of type (any item, any rarity)
ITEM_RARITY_TABLE = [
    ("Mythic",    0.005),
    ("Legendary", 0.030),
    ("Epic",      0.110),
    ("Rare",      0.250),
    ("Uncommon",  0.500),
    ("Common",    1.000),
]

# --- hats (worn, sit ON the head) ---
# Each hat is a list of rows. The BOTTOM row of the hat lands on the buddy's
# head row (sprite row 0), overlapping any head chars there; additional rows
# stack upward into the previously-empty sky above the buddy.
# Held items were removed — they fought with the buddy silhouette for screen
# real estate.
HATS = {
    "beanie":    [" () ", "(===)"],                      # 2-row knit cap + pom
    "flower":    [" * ", " | "],                         # 2-row bloom + stem
    "top_hat":   [" |#| ", "[___]"],                     # 2-row tall hat + wide brim
    "wizard":    [" /\\ ", "//\\\\", "[___]"],           # 3-row pointed hat + band
    "cowboy":    [" []  ", "[===]"],                     # 2-row stetson — boxy top
    "party":     ["  *  ", " /^\\ ", "/o^o\\"],          # 3-row birthday cone
    "propeller": ["  +  ", "  |  ", "<###>"],            # 3-row propeller beanie
    "crown":     [" v v ", "vWvWv"],                     # 2-row jeweled crown
    "halo":      [" ~~~ ", "( O )"],                     # 2-row glowing halo
}
ALL_DROPS = [("hat", h) for h in HATS]

EYE_STYLES = ["o", "O", "^", "*", "~", "x", "u", "v", "@", "."]

NAMES = {
    "duck":     ["Quackers", "Waddles", "Puddles", "Mallard", "Ducky"],
    "goose":    ["Honk", "Untitled", "Gary", "Gregor", "Goosey"],
    "cat":      ["Void", "Glitch", "Shadow", "Mittens", "Bytez"],
    "rabbit":   ["Bun", "Hopscotch", "Clover", "Cotton", "Nibbles"],
    "owl":      ["Hoot", "Nox", "Sage", "Archimedes", "Orion"],
    "penguin":  ["Tux", "Pebble", "Waddle", "Chilly", "Flippers"],
    "turtle":   ["Turbo", "Sheldon", "Mossy", "Patience", "Drifter"],
    "snail":    ["Zippy", "Spiral", "Shelly", "Slick", "Goo"],
    "dragon":   ["Ember", "Cinder", "Noodle", "Blaze", "Sparks"],
    "octopus":  ["Inky", "Eight", "Squish", "Tangle", "Bloop"],
    "axolotl":  ["Axel", "Lotl", "Bubbles", "Gills", "Smiley"],
    "ghost":    ["Boo", "Specter", "Wisp", "Null", "Casper"],
    "robot":    ["Unit-7", "Bleep", "Glitch", "Servo", "Bit"],
    "blob":     ["Gloop", "Blobby", "Ooze", "Jelly", "Squish"],
    "cactus":   ["Spike", "Prick", "Sandy", "Thorny", "Bloom"],
    "mushroom": ["Spore", "Fungi", "Morel", "Cap", "Myco"],
    "chonk":    ["BigBoi", "Thicc", "Unit", "Absolute", "Chonky"],
    "capybara": ["Capy", "Vibes", "Zen", "Barra", "Serenity"],
    "crab": ["Pinch", "Sidewise", "Scuttle", "Snapper", "Clackers"],
    "fish": ["Bubbles", "Finn", "Sushi", "Splash", "Gilligan"],
    "dog": ["Rover", "Biscuit", "Scruff", "Wags", "Bandit"],
    "cow": ["Moo", "Bessie", "Daisy", "Spots", "Buttercup"],
    "penguin": ["Tux", "Waddle", "Pebble", "Chilly", "Flippers"],
    "pig": ["Wilbur", "Hamlet", "Porkchop", "Truffle", "Snorts"],
    "bird": ["Tweet", "Whistle", "Pip", "Skybit", "Featherly"],
    "chicken": ["Cluck", "Henrietta", "Drumstick", "Beaks", "Coop"],
}

# Each species: theme = 2 favored stats for growth; mini = compact status-line
# face ({e} = eyes); art = list of lines ({e} = eyes); hand_row = art index the
# held item attaches to.
SPECIES = {
    # Variable dimensions per species — turtle is wider than tall, cat has
    # pointy ears, etc. Within a species every row is the same width so the
    # left/right silhouette is straight.

    # 3 rows × 7 cols — side-profile duck with body + beak
    "duck": {
        "theme": ["patience", "wisdom"],
        "mini": "({e}_>",
        "hand_row": 1,
        "art": [
            "  __   ",
            "__({e}_)>",
            " \\___/ ",
        ],
    },

    # 3 rows × 7 cols — proven asciiart.eu cat face design
    "cat": {
        "theme": ["snark", "chaos"],
        "mini": "({e}_{e})",
        "hand_row": 1,
        "art": [
            "|\\---/|",
            "| {e}_{e} |",
            " \\_^_/ ",
        ],
    },

    # 3 rows × 7 cols — long bunny ears + paws
    "rabbit": {
        "theme": ["patience", "debugging"],
        "mini": "({e}.{e})",
        "hand_row": 1,
        "art": [
            " (\\(\\  ",
            " ({e}.{e}) ",
            "(\")_(\")",
        ],
    },

    # 4 rows × 5 cols — ear tufts + Y-beak + talons
    "owl": {
        "theme": ["wisdom", "debugging"],
        "mini": "({e}Y{e})",
        "hand_row": 1,
        "art": [
            ",___,",
            "({e}Y{e})",
            "/( )\\",
            " ^_^ ",
        ],
    },

    # 4 rows × 11 cols — toadstool with ROUNDED cap (parens instead of slashes)
    "mushroom": {
        "theme": ["wisdom", "chaos"],
        "mini": "(@_@)",
        "hand_row": 2,
        "art": [
            "   _____   ",
            "  (,_,_,)  ",
            " (_______) ",
            "    |{e}|    ",
        ],
    },

    # 3 rows × 5 cols — hollow eyes + wavy tail
    "ghost": {
        "theme": ["chaos", "wisdom"],
        "mini": "({e} {e})",
        "hand_row": 1,
        "art": [
            ",---,",
            "({e} {e})",
            ")~v~(",
        ],
    },

    # 5 rows × 7 cols — slimmer octopus with curling tentacles
    "octopus": {
        "theme": ["wisdom", "debugging"],
        "mini": "({e}.{e})",
        "hand_row": 2,
        "art": [
            "  ___  ",
            " /   \\ ",
            " ({e}.{e}) ",
            " \\___/ ",
            " )()() ",
        ],
    },

    # 4 rows × 11 cols — snail with antenna stalks, spiral shell, body extending right
    "snail": {
        "theme": ["patience", "wisdom"],
        "mini": "@({e})",
        "hand_row": 1,
        "art": [
            "    ,_,    ",
            "  __(@)__  ",
            " /@@@@@\\__ ",
            "(________{e}>",
        ],
    },

    # 4 rows × 11 cols — turtle: domed shell, segmented body with face/eyes, 4 legs
    "turtle": {
        "theme": ["patience", "wisdom"],
        "mini": "({e}.{e})",
        "hand_row": 2,
        "art": [
            "   ,___,   ",
            "  /,___,\\  ",
            " ({e}|---|{e}) ",
            "  ^^   ^^  ",
        ],
    },

    # 3 rows × 9 cols — CRAB: wide shell, claws extending sideways, legs below
    "crab": {
        "theme": ["chaos", "patience"],
        "mini": "<({e}_{e})>",
        "hand_row": 1,
        "art": [
            "  _____  ",
            "<({e}___{e})>",
            " //\\_//\\ ",
        ],
    },

    # 5 rows × 7 cols — penguin: head with beak, body, flippers, feet
    # Source: https://www.asciiart.eu/animals/birds-land (penguin variants)
    "penguin": {
        "theme": ["debugging", "patience"],
        "mini": "({e}<",
        "hand_row": 1,
        "art": [
            "   _   ",
            "  ({e}<  ",
            " /|||\\ ",
            " ||||| ",
            "  d b  ",
        ],
    },

    # 4 rows × 7 cols — symmetric fish (Max, user-provided design)
    "fish": {
        "theme": ["wisdom", "patience"],
        "mini": "({e}_)<",
        "hand_row": 2,
        "art": [
            "   _   ",
            "  /_|  ",
            " ({e}_)<|",
            "  \\_|  ",
        ],
    },

    # 4 rows × 11 cols — sitting dog (Joan G. Stark / jgs design, signature
    # stripped from render; credited in ART_CREDITS for open-source release)
    "dog": {
        "theme": ["patience", "chaos"],
        "mini": "(__()",
        "hand_row": 1,
        "art": [
            "       __  ",
            "  (___()'`;",
            "  /,    /` ",
            "  \\\"---\\\\  ",
        ],
    },

    # 5 rows × 12 cols — the classic cowsay cow (verbatim, trimmed to 5 rows)
    # Source: https://github.com/piuccio/cowsay (default.cow) /
    #         https://en.wikipedia.org/wiki/Cowsay
    "cow": {
        "theme": ["patience", "wisdom"],
        "mini": "({e}{e})",
        "hand_row": 1,
        "art": [
            "  ^__^      ",
            "  ({e}{e})\\____ ",
            "  (__)\\    \\",
            "      ||--w|",
            "      ||  ||",
        ],
    },

    # 4 rows × 5 cols — antenna, screen face, boxy body, feet
    "robot": {
        "theme": ["debugging", "patience"],
        "mini": "[{e}.{e}]",
        "hand_row": 1,
        "art": [
            " [+] ",
            "[{e}.{e}]",
            "|[#]|",
            " d b ",
        ],
    },

    # 4 rows × 7 cols — VERY round, fully closed loop
    "chonk": {
        "theme": ["patience", "snark"],
        "mini": "({e} {e})",
        "hand_row": 1,
        "art": [
            ".-----.",
            "( {e}_{e} )",
            "(     )",
            "'-----'",
        ],
    },

    # 4 rows × 11 cols — pig with curly tail (user-provided design)
    "pig": {
        "theme": ["patience", "chaos"],
        "mini": "({e}{e})",
        "hand_row": 1,
        "art": [
            "   _____   ",
            "^..^     \\9",
            "({e}{e})_____/ ",
            "   WW  WW  ",
        ],
    },

    # 4 rows × 7 cols — bird side profile (mrf design, signature stripped;
    # credited in ART_CREDITS for open-source release)
    "bird": {
        "theme": ["chaos", "wisdom"],
        "mini": ">{e} )",
        "hand_row": 1,
        "art": [
            "   ,_  ",
            "  >{e} ) ",
            "  ( ( \\",
            "   ''|\\",
        ],
    },

    # 5 rows × 6 cols — chicken with wing flap. Row 0 is empty placeholder
    # (was a \ feather, removed) so hats land on row 0 instead of overwriting
    # the actual head row (row 1).
    "chicken": {
        "theme": ["chaos", "debugging"],
        "mini": "({e}>",
        "hand_row": 1,
        "art": [
            "      ",
            "  ({e}> ",
            "\\_//) ",
            " \\_/_)",
            "  _|_ ",
        ],
    },
}
