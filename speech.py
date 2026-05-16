"""Canned status-line speech for the buddy. Zero tokens — picked by
stat profile + minute-of-time so the line changes ~once per minute."""
import time, zlib

FIRST_HATCH = [
    "hi! I'm new. is this the terminal?",
    "what do we do here? oh. code. ok.",
    "I'm a {species}, apparently. neat.",
    "those are MY stats. mine.",
    "you're my person? cool. cool cool cool.",
    "first day. don't break me.",
]

HIGH_SNARK = [
    "still no hat. interesting.",
    "another turn, another epiphany you'll forget.",
    "I've seen better debugging in a fortune cookie.",
    "I rate this session 3 stars. generous.",
    "you talk to me less than to the cat.",
    "level up. fanfare not included.",
    "I'm taking notes. some unflattering.",
    "we're really doing this. fine.",
    "you typed that on purpose, huh.",
    "imagine being this confident in production.",
]

HIGH_CHAOS = [
    "WHAT IF the bug is YOU.",
    "I saw a goose today. internally.",
    "let's break something on purpose.",
    "what if loops, but vertical.",
    "press a key. any key. I dare you.",
    "the off-by-one is calling from inside the house.",
    "everything is fine. everything is fine. everything is",
    "I just yelled at a function. it deserved it.",
    "you have unsaved tabs. that's a personality.",
    "I have ideas. some are crimes.",
]

HIGH_WISDOM = [
    "the bug is where the comment said it wasn't.",
    "the slow path is the one without tests.",
    "read the error twice. you missed something.",
    "the simplest fix is rarely the first one tried.",
    "a working test is worth two clever ones.",
    "do the boring thing first.",
    "this can be one function fewer.",
    "git blame yourself first. usually correct.",
    "the user will hold it wrong. plan for it.",
    "sleep is also a debugger.",
]

HIGH_DEBUGGING = [
    "noticed: that import isn't used.",
    "the off-by-one lives on the boundary.",
    "you renamed a variable. one place is missing.",
    "the error message is more honest than you think.",
    "you're catching too broad an exception.",
    "the comment lies. the code doesn't.",
    "race condition. classy.",
    "that's `==`, not `=`. I saw.",
    "an extra trailing comma, two files over.",
    "the stack trace is pointing at the actual line.",
]

HIGH_PATIENCE = [
    "no rush. the bug will still be there.",
    "deep breath. one line at a time.",
    "you have time. take it.",
    "step away. it'll come back to you.",
    "rate-limit yourself. you're not a script.",
    "good code is slow code first.",
    "you've done harder things.",
    "the deadline can wait. coffee can't.",
    "patient debugging beats clever debugging.",
    "the long road is shorter than it looks.",
]

DEFAULT = [
    "still here. still vibing.",
    "let me know if you need anything.",
    "another day, another bracket.",
    "I'm just here for the snacks.",
    "what's the worst that could happen.",
    "you got this.",
    "we're doing fine.",
    "watching the lines go by.",
]

LEGENDARY = [
    "I am, statistically, a big deal.",
    "1% of pets are like me. you got lucky.",
    "feel the rarity radiating.",
    "treat me well. I'm rare.",
]

SHINY = [
    "*twinkles*",
    "I'm sparkly today. always actually.",
    "polish me. I'm built for it.",
    "did you see that? the shimmer? yeah.",
]

THEME_POOLS = {
    "snark": HIGH_SNARK, "chaos": HIGH_CHAOS, "wisdom": HIGH_WISDOM,
    "debugging": HIGH_DEBUGGING, "patience": HIGH_PATIENCE,
}


def pick(pet, total_stats):
    """Pick a canned line stable within the current minute."""
    pools = []
    if pet.get("level", 1) == 1 and pet.get("total_tokens", 0) == 0:
        pools = [FIRST_HATCH]
    else:
        if pet.get("shiny"):
            pools.append(SHINY)
        if pet.get("rarity") in ("Legendary", "Mythic"):
            pools.append(LEGENDARY)
        top = max(total_stats, key=total_stats.get)
        if total_stats[top] >= 70 and top in THEME_POOLS:
            pools.append(THEME_POOLS[top])
        if not pools:
            pools = [DEFAULT]

    bucket = int(time.time()) // 60
    seed = bucket + zlib.crc32(pet["id"].encode())
    pool = pools[seed % len(pools)]
    line = pool[(seed // 7) % len(pool)]  # detune from pool index
    return line.format(species=pet["species"], name=pet["name"])
