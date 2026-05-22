#!/usr/bin/env python3
"""`/questline` CLI dispatcher.

Run as `python3 cli.py <subcommand> [args...]`. Subcommands:

  show              full sprite + stats for the active pet (default)
  list              list every pet you own
  switch <n>        make pet #n the one earning XP from now on
  new               hatch a brand-new random pet (becomes active)
  rename <name>     rename the active pet (or `rename <n> <name>`)
  color [<name>]    list/set the active pet's color (only unlocked colors)
  bag               list your hat inventory
  equip <n>         toggle hat #n on the active pet
  rules             print the full gameplay rules
  data              raw JSON dump of the active pet
  species           every species sprite side-by-side
  preview           every species in the live world view
  hats              every species wearing every hat (verify fit)

Each command prints colored ASCII to stdout. `show` and `new` also
append a `---DATA---` JSON blob that downstream tooling (e.g. Claude
Code) can parse to generate flavor text.
"""

import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core
import adventure
from data import (
    SPECIES, SPECIES_TIERS, STATS, STAT_LABELS, RARITY_STARS, HATS,
    ACHIEVEMENTS, xp_to_next,
)


# --- Helpers ---------------------------------------------------------------

def _pet_data(sv, pet):
    """Structured pet snapshot - emitted as JSON after `show`/`new` so a
    downstream agent can describe the pet without re-parsing the colored
    ASCII output."""
    ts = core.total_stats(pet)
    hat = core.get_equipped(sv, pet, "hat")
    adv = adventure._state(pet)
    return {
        "name":         pet["name"],
        "species":      pet["species"],
        "rarity":       pet["rarity"],
        "shiny":        pet["shiny"],
        "level":        pet["level"],
        "color":        core.color_for_pet(pet),
        "stats":        ts,
        "top_stat":     max(ts, key=ts.get),
        "low_stat":     min(ts, key=ts.get),
        "total_tokens": pet["total_tokens"],
        "wins":         adv.get("kills", 0),
        "losses":       adv.get("losses", 0),
        "equipped_hat": hat["type"] if hat else None,
        "pet_count":    len(sv["pets"]),
        "first_hatch":  (len(sv["pets"]) == 1
                         and pet["level"] == 1
                         and pet["total_tokens"] == 0),
        "hatched_at":   pet["hatched_at"],
    }


def _stat_block(pet):
    """Indented `STAT  [###---] 42` lines, one per stat."""
    ts = core.total_stats(pet)
    for s in STATS:
        print("  %-10s %s  %d" % (STAT_LABELS[s], core.stat_bar(ts[s]), ts[s]))


def _hat_rows(hat_type):
    """Get the row list for a hat type, tolerating legacy string-format
    entries (older saves might reference hat types stored as a single str)."""
    rows = HATS.get(hat_type)
    if rows is None:
        return None
    return [rows] if isinstance(rows, str) else rows


def _active_for_cli(sv):
    """The pet a /questline subcommand should operate on: the per-terminal
    pinned pet for this session, or the global default if unpinned."""
    sess = sv.get("current_session")
    if sess:
        return core.active_pet_for_session(sv, sess)
    return core.active_pet(sv)


def _starter_template(eye="o"):
    """A fully-populated 'fake' pet dict useful for preview/hats commands
    that need a pet shape but don't want to disturb the user's real save."""
    return {
        "id": "preview", "name": "Preview", "rarity": "Common", "shiny": False,
        "eyes": eye,
        "base_stats":   {s: 50 for s in STATS},
        "earned_stats": {s: 0  for s in STATS},
        "level": 1, "xp": 0, "total_tokens": 0,
        "equipped_hat": None,
        "wins": 0, "losses": 0, "hatched_at": "preview",
    }


# --- Subcommands -----------------------------------------------------------

def cmd_show(sv, args):
    """Full sprite + stats + XP bar + equipped gear for the pet active
    in the current terminal (or the global default if this terminal
    hasn't been pinned)."""
    sess = sv.get("current_session")
    pet  = core.active_pet_for_session(sv, sess) if sess else core.active_pet(sv)
    lc   = core.color_for_pet(pet)
    shiny = "  *SHINY*" if pet["shiny"] else ""
    sleeping = "  zZz" if core.is_sleeping(pet) else ""
    print()
    print("  " + core.c("%s %s  \"%s\"%s%s" % (
        RARITY_STARS[pet["rarity"]], pet["species"].upper(),
        pet["name"], shiny, sleeping), lc))
    print("  " + core.c("Lv %d" % pet["level"], lc)
          + core.c("  -  %s  -  %s tier" % (pet["rarity"], lc), "white"))
    print("  " + core.c("-" * 42, lc))
    print()
    print(core.render_sprite(sv, pet))
    print()
    _stat_block(pet)
    print()
    need = xp_to_next(pet["level"])
    print("  %-10s %s  %s / %s" % (
        "XP", core.xp_bar(pet),
        core.fmt_tokens(pet["xp"]), core.fmt_tokens(need)))
    adv = adventure._state(pet)
    print("  %-10s %s lifetime  -  W/L %d-%d" % (
        "", core.fmt_tokens(pet["total_tokens"]),
        adv.get("kills", 0), adv.get("losses", 0)))
    hat = core.get_equipped(sv, pet, "hat")
    if hat:
        print("  gear: hat " + core.crarity(hat["type"], hat["rarity"]))
    if len(sv["pets"]) > 1:
        print("  " + core.c("(%d pets - /questline list)" % len(sv["pets"]), "white"))
    print()
    print("---DATA---")
    print(json.dumps(_pet_data(sv, pet)))


def cmd_list(sv, args):
    """One row per pet. Markers show what's active where:
       >  = pinned to THIS terminal (the one /questline was run from)
       *  = global default (used by any terminal that hasn't pinned)"""
    pets = list(sv["pets"].values())
    sess = sv.get("current_session")
    here_id   = sv.get("session_pets", {}).get(sess) if sess else None
    global_id = sv.get("active")
    print()
    print("  " + core.c("YOUR PETS (%d)" % len(pets), "white"))
    print()
    for i, p in enumerate(pets, 1):
        lc = core.color_for_pet(p)
        if p["id"] == here_id:
            marker = core.c(">", lc)
        elif p["id"] == global_id and here_id is None:
            marker = core.c(">", lc)
        elif p["id"] == global_id:
            marker = core.c("*", "white")
        else:
            marker = " "
        print("  [%d] %s %-12s %-9s %-7s %-10s %s" % (
            i, marker, core.name_tag(p), p["species"],
            core.c("Lv%d" % p["level"], lc), p["rarity"],
            RARITY_STARS[p["rarity"]]))
    print()
    print("  " + core.c("> = active in this terminal   * = global default", "white"))
    print("  " + core.c("/questline switch <n>   -   /questline new   -   /questline bag", "white"))
    print()


def cmd_switch(sv, args):
    """Change which pet earns XP.

    Forms:
      /questline switch <n>              pin pet #n to THIS terminal only
      /questline switch <n> --global     pin pet #n as the default for every
                                     terminal that hasn't been pinned

    Per-terminal pinning lets you grind two pets simultaneously - terminal A
    can be leveling Biscuit while terminal B is leveling Eight. Each render
    of a terminal credits its own session tokens to whichever pet that
    terminal has pinned (or the global default if it hasn't pinned one)."""
    pets = list(sv["pets"].values())
    is_global = "--global" in args
    nargs = [a for a in args if a != "--global"]
    if not nargs or not nargs[0].isdigit():
        print("  usage: /questline switch <n> [--global]   (see /questline list)")
        return
    n = int(nargs[0])
    if n < 1 or n > len(pets):
        print("  no pet #%d - you have %d." % (n, len(pets)))
        return
    p = pets[n - 1]
    sess = sv.get("current_session")

    if is_global or not sess:
        # Old behavior: update the global default for every unpinned terminal.
        old = core.active_pet(sv)
        sv["active"] = p["id"]
        target_desc = "every unpinned terminal"
    else:
        # Pin just this terminal.
        old_pid = sv.get("session_pets", {}).get(sess) or sv.get("active")
        old = sv["pets"].get(old_pid)
        core.pin_session_pet(sv, sess, p["id"])
        target_desc = "this terminal"

    core.save(sv)
    print()
    if old and old["id"] != p["id"]:
        print("  %s: %s -> %s" % (target_desc,
                                  core.name_tag(old), core.name_tag(p)))
    else:
        print("  %s: %s" % (target_desc, core.name_tag(p)))
    print("  " + core.c("token XP now flows to %s." % p["name"], "white"))
    print()
    print(core.render_sprite(sv, p))
    print()


def cmd_new(sv, args):
    """Hatch a fresh random pet. The new pet becomes the active pet in
    THIS terminal (and the global default if no other pet has been pinned
    globally yet, e.g. it's your first hatch)."""
    p = core.add_random_pet(sv)
    sess = sv.get("current_session")
    if sess:
        core.pin_session_pet(sv, sess, p["id"])
    # Also set as global default if there isn't one yet (first hatch case).
    if not sv.get("active") or sv["active"] not in sv["pets"]:
        sv["active"] = p["id"]
    core.save(sv)
    lc = core.color_for_pet(p)
    shiny = "  *SHINY*" if p["shiny"] else ""
    print()
    print("  " + core.c("* a new pet hatched! *", "white"))
    print()
    print(core.render_sprite(sv, p))
    print()
    print("  " + core.c("%s %s  \"%s\"%s" % (
        RARITY_STARS[p["rarity"]], p["species"].upper(),
        p["name"], shiny), lc))
    print("  " + core.c("Lv 1  -  %s" % p["rarity"], "white"))
    print()
    _stat_block(p)
    print()
    print("  " + core.c(
        "%s is now active - XP flows here. /questline switch to change back."
        % p["name"], "white"))
    print()
    print("---DATA---")
    print(json.dumps(_pet_data(sv, p)))


def cmd_bag(sv, args):
    """List the hat inventory with rarity, glyph, and which pet (if any)
    each hat is currently equipped on."""
    inv = core.inv_list(sv)
    print()
    print("  " + core.c("INVENTORY (%d)" % len(inv), "white"))
    if not inv:
        print()
        print("  empty - hats drop when pets level up or win fights.")
        print()
        return

    # Map iid -> name of the pet wearing it (for the "equipped on..." tag).
    equipped = {p["equipped_hat"]: p["name"]
                for p in sv["pets"].values()
                if p.get("equipped_hat")}

    print()
    print("  " + core.c("HATS", "white"))
    for i, it in enumerate(inv, 1):
        rows = _hat_rows(it["type"])
        if rows is None:
            continue  # skip retired hat types (legacy save entries)
        glyph = rows[-1].strip()  # bottom row reads as the hat's main shape
        tag = (("  > equipped on %s" % equipped[it["iid"]])
               if it["iid"] in equipped else "")
        print("  [%d] %-9s %-5s %-10s %s%s" % (
            i,
            core.crarity(it["type"], it["rarity"]),
            core.crarity(glyph, it["rarity"]),
            it["rarity"],
            RARITY_STARS[it["rarity"]],
            core.c(tag, "white")))
    print()
    print("  " + core.c("/questline equip <n>   (toggles it on your active pet)", "white"))
    print()


def cmd_equip(sv, args):
    """Toggle a hat on the active pet. Equipping a different hat replaces
    the one currently equipped."""
    inv = core.inv_list(sv)
    if not args or not args[0].isdigit():
        print("  usage: /questline equip <n>   (see /questline bag)")
        return
    n = int(args[0])
    if n < 1 or n > len(inv):
        print("  no hat #%d - you have %d." % (n, len(inv)))
        return
    it  = inv[n - 1]
    pet = _active_for_cli(sv)
    print()
    if pet.get("equipped_hat") == it["iid"]:
        # Same hat is already on - toggle off.
        pet["equipped_hat"] = None
        core.save(sv)
        print("  %s unequipped its %s." % (pet["name"], it["type"]))
    else:
        pet["equipped_hat"] = it["iid"]
        core.save(sv)
        print("  %s equipped %s %s." % (
            pet["name"],
            core.crarity(it["type"], it["rarity"]),
            RARITY_STARS[it["rarity"]]))
        print()
        print(core.render_sprite(sv, pet))
    print()


def cmd_data(sv, args):
    """Pretty-print the JSON snapshot of the active pet."""
    print(json.dumps(_pet_data(sv, _active_for_cli(sv)), indent=2))


def cmd_achievements(sv, args):
    """List every achievement, marking which ones the user has unlocked
    (with unlock date) and which are still locked."""
    unlocked = sv.get("achievements", {})
    streak   = sv.get("streak_days", 0)
    print()
    print("  " + core.c("ACHIEVEMENTS  (%d/%d unlocked)" % (
        len(unlocked), len(ACHIEVEMENTS)), "white"))
    if streak >= 2:
        print("  " + core.c("daily streak: %d days" % streak, "gold"))
    print("  " + core.c("-" * 50, "white"))
    for aid, (name, desc, _pred) in ACHIEVEMENTS.items():
        if aid in unlocked:
            mark = core.c("✓", "gold")
            date = core.c("(%s)" % unlocked[aid], "white")
            line = "%s %-18s %s  %s" % (mark, core.c(name, "gold"), date, desc)
        else:
            mark = core.c("·", "white")
            line = "%s %-18s             %s" % (
                mark, core.c(name, "white"), core.c(desc, "white"))
        print("  " + line)
    print()


def cmd_help(sv, args):
    """Print the list of every /questline subcommand with a short description.
    Points users at /questline rules for the gameplay rules."""
    print()
    print("  " + core.c("QUESTLINE COMMANDS", "white"))
    print("  " + core.c("-" * 42, "white"))
    print()
    rows = [
        ("show",                "full sprite + stats for the active pet (default)"),
        ("list",                "list every pet you own (>=active here, *=global default)"),
        ("switch <n>",          "pin pet #n to THIS terminal (add --global to set default)"),
        ("new",                 "hatch a brand-new random pet (auto-pinned here)"),
        ("rename <name>",       "rename the active pet ('rename <n> <name>' for pet #n)"),
        ("color [<name>]",      "list/set the active pet's color (unlocked tiers only)"),
        ("bag",                 "list your hat inventory"),
        ("equip <n>",           "toggle hat #n on the active pet"),
        ("rules",               "print the full gameplay rules (XP, drops, combat, ...)"),
        ("achievements",        "list every milestone (unlocked + locked) + streak"),
        ("data",                "raw JSON dump of the active pet"),
        ("species",             "show every species sprite side-by-side"),
        ("preview",             "render every species in the live status-line world"),
        ("hats",                "render every species wearing every hat (verify fit)"),
        ("help",                "print this command list"),
    ]
    for name, desc in rows:
        print("  " + core.c("/questline " + name, "cyan") + " " * max(1, 20 - len(name)) + desc)
    print()
    print("  " + core.c("for gameplay rules: /questline rules", "white"))
    print()


def cmd_rules(sv, args):
    """Print the gameplay rules - how XP, leveling, drops, combat, and
    per-terminal pet pinning work. Useful as a refresher or for showing
    new users what the questline system actually does."""
    rules = [
        ("XP",
         "Every Claude Code message credits its tokens (input + output +",
         "cache-creation) as XP to whichever pet is active in that terminal.",
         "Cache-read tokens don't count (too cheap and huge - would warp the curve)."),
        ("LEVELING",
         "Quadratic curve. At heavy usage (~30M tokens/day):",
         "  L20  ~24M tokens    (~18 hours)",
         "  L50  ~348M tokens   (~12 days)",
         "  L100 ~2.73B tokens  (~3 months - max level / prestige)",
         "Levels keep climbing past 100 but the XP curve gets brutal."),
        ("COLOR TIERS",
         "Your pet's sprite color upgrades at level milestones:",
         "  L1-5    white      L51-75   magenta",
         "  L6-15   green      L76-99   silver",
         "  L16-30  cyan       L100+    GOLD  (prestige)",
         "  L31-50  blue",
         "Use /questline color to pick any color you've unlocked (cosmetic only)."),
        ("HATS",
         "Drop sources:",
         "  - 2% chance on every level-up",
         "  - 0.8% chance on every fight win",
         "  - guaranteed Rare+ hat from every Christmas tree you walk past",
         "Rarity scales with pet level: Mythic peaks at 5% at L100."),
        ("RARITY TIERS",
         "Common (white)   Uncommon (green)   Rare (cyan)",
         "Epic (blue)      Legendary (magenta) Mythic (gold)",
         "Rarity colors match the level colors - a L100 gold pet pulling",
         "a Mythic gold hat is the chase."),
        ("COMBAT",
         "Wild monsters spawn every ~33 walked cols. They approach, fight,",
         "and resolve in a few ticks. Win chance is biased by debugging +",
         "chaos stats. Wins award XP (and maybe a drop); losses give 1/5 XP."),
        ("MULTI-PET",
         "Hatch new pets with /questline new. Each pet has its own L1->L100",
         "progression. /questline switch <n> changes the active pet IN THIS",
         "TERMINAL - different terminals can grind different pets in",
         "parallel. Add --global to switch the default for every terminal."),
        ("CHRISTMAS TREE",
         "Ultra-rare (~1 in 20 000 world cols). Gold star, red ornaments,",
         "red present box. Walk through it and get a guaranteed Rare+ hat.",
         "Each tree's gift is deterministic - it'll always give the same hat."),
        ("SLEEP STATE",
         "A pet that hasn't earned XP in 24+ hours falls asleep -",
         "shown as `zZz` next to its name in the status line and /questline show.",
         "Sleeping is purely cosmetic. The moment new tokens credit to that",
         "pet (from any terminal), the marker disappears and the pet wakes."),
        ("SEASONAL EVENTS",
         "The world picks up real-world holiday flair automatically:",
         "  Dec 31 - Jan 7  - new year confetti (IN THE SKY)",
         "  Feb 10-16       - valentine's hearts on the ground",
         "  Mar 17          - st. patrick's clovers",
         "  Jul 4           - independence day fireworks (IN THE SKY)",
         "  October         - halloween pumpkins",
         "  December        - christmas tree spawn rate jumps 100x"),
    ]
    print()
    print("  " + core.c("QUESTLINE RULES", "white"))
    print("  " + core.c("-" * 42, "white"))
    for section in rules:
        head, *lines = section
        print()
        print("  " + core.c(head, "cyan"))
        for ln in lines:
            print("    " + ln)
    print()
    print("  " + core.c("/questline show   /questline list   /questline bag   /questline hats", "white"))
    print()


def cmd_color(sv, args):
    """Change the active pet's color.

    Forms:
      /questline color              - show unlocked colors + current pick
      /questline color <name>       - set the color (must be unlocked)
      /questline color auto         - clear the override (use natural level color)

    Colors are unlocked by reaching the level band that grants them. You
    can pick any color you've already unlocked, including dropping back
    down to a lower-tier color. Color choice is purely cosmetic - it
    doesn't affect stats, drops, or anything else."""
    pet = _active_for_cli(sv)
    unlocked = core.unlocked_colors(pet["level"])
    natural  = core.color_for_level(pet["level"])
    current  = pet.get("color_choice") or natural

    if not args:
        # Show palette + current pick
        print()
        print("  " + core.c("COLOR for %s (Lv %d)" % (pet["name"], pet["level"]),
                            core.color_for_pet(pet)))
        print()
        for col in unlocked:
            marker = ">" if col == current else " "
            tag = " (natural)" if col == natural else ""
            print("  %s %s%s" % (marker, core.c(col, col), tag))
        print()
        print("  " + core.c("/questline color <name>   /questline color auto", "white"))
        print()
        return

    target = args[0].lower()
    if target in ("auto", "clear", "reset", "default", "none"):
        pet["color_choice"] = None
        core.save(sv)
        print()
        print("  %s back to its natural color (%s)." % (
            core.name_tag(pet), core.c(natural, natural)))
        print()
        return

    if target not in unlocked:
        print()
        print("  %s hasn't unlocked %s yet." % (pet["name"], target))
        print("  unlocked: " + ", ".join(core.c(c, c) for c in unlocked))
        print()
        return

    pet["color_choice"] = target
    core.save(sv)
    print()
    print("  %s now renders in %s." % (
        core.name_tag(pet), core.c(target, target)))
    print()


# Allow letters, digits, space, '-', '_', and a few punctuation chars that
# can appear in cute pet names. Anything else (incl. ANSI escapes, control
# chars, shell metachars) is stripped on rename so a malicious save edit
# or paste can't corrupt the status line render.
import re as _re
_NAME_OK = _re.compile(r"[^A-Za-z0-9 _.'\-]")
_NAME_MAX_LEN = 20


def _sanitize_name(raw):
    """Strip disallowed chars, collapse whitespace, cap length. Returns the
    cleaned name (may be empty if everything was filtered)."""
    cleaned = _NAME_OK.sub("", raw).strip()
    cleaned = _re.sub(r"\s+", " ", cleaned)
    return cleaned[:_NAME_MAX_LEN]


def cmd_rename(sv, args):
    """Rename a pet.

    Forms:
      /questline rename <new name>           - renames the ACTIVE pet
      /questline rename <n> <new name>       - renames pet #n (see /questline list)

    Names are cleaned: letters, digits, space, `_`, `-`, `.`, `'` only;
    other characters are stripped. Length capped at 20."""
    pets = list(sv["pets"].values())
    if not args:
        print("  usage: /questline rename <new name>")
        print("         /questline rename <n> <new name>")
        return

    # Optional leading pet-number selector
    target = _active_for_cli(sv)
    name_parts = args
    if args[0].isdigit():
        n = int(args[0])
        if n < 1 or n > len(pets):
            print("  no pet #%d - you have %d." % (n, len(pets)))
            return
        target = pets[n - 1]
        name_parts = args[1:]
        if not name_parts:
            print("  usage: /questline rename %d <new name>" % n)
            return

    raw = " ".join(name_parts)
    new_name = _sanitize_name(raw)
    if not new_name:
        print("  name must contain at least one letter, digit, or allowed punctuation.")
        return

    old_name = target["name"]
    target["name"] = new_name
    core.save(sv)
    print()
    print("  %s -> %s" % (core.c(old_name, "white"),
                          core.name_tag(target)))
    print()


# --- Designer / debug commands --------------------------------------------
# `species`, `preview`, and `hats` are tools for inspecting the sprite
# catalog - useful when adding species or tuning hat positioning.

def cmd_species(sv, args):
    """Render every species sprite in a grid (3 per row, bottom-aligned)
    so the user can sanity-check that every silhouette looks right."""
    eye = "o"
    cols_per_row = 3
    gap = "     "
    names = list(SPECIES.keys())
    print()
    print("  " + core.c("ALL %d PETS (eye='o', no hat)" % len(names), "white"))
    print()
    for i in range(0, len(names), cols_per_row):
        batch = names[i:i + cols_per_row]
        sprites = [[ln.replace("{e}", eye) for ln in SPECIES[n]["art"]]
                   for n in batch]
        widths  = [max(len(r) for r in s) for s in sprites]
        max_h   = max(len(s) for s in sprites)

        # Labels
        labels = [n.upper().center(widths[k]) for k, n in enumerate(batch)]
        print("  " + gap.join(labels))

        # Sprite rows (pad shorter sprites with leading blank rows so they
        # all touch the shared ground line at the bottom).
        for r in range(max_h):
            parts = []
            for k, s in enumerate(sprites):
                pad = max_h - len(s)
                parts.append(" " * widths[k] if r < pad else s[r - pad])
            print("  " + gap.join(parts))

        # Ground line + theme stats label
        print("  " + gap.join("_" * widths[k] for k in range(len(batch))))
        themes = ["+".join(SPECIES[n]["theme"]).center(widths[k])
                  for k, n in enumerate(batch)]
        print("  " + core.c(gap.join(themes), "white"))
        print()


def cmd_preview(sv, args):
    """Render every species INSIDE the live status-line world view, so
    the user can see how each one would look as their active pet."""
    import adventure
    core.USE_COLOR = sys.stdout.isatty()

    template = _starter_template()
    species_to_tier = {s: tier
                       for tier, species in SPECIES_TIERS.items()
                       for s in species}

    print()
    for name in SPECIES:
        # Per-pet adventure state, a few steps in so the walk is visible.
        pet = dict(template, species=name, name=name.capitalize(),
                   adventure={"buddy_col": 5})
        # Disposable save dict so the preview never touches real state.
        fake_sv = {"pets": {"preview": pet}, "active": "preview",
                   "inventory": []}
        world = adventure.render_world(fake_sv, pet, width=80)
        tier  = species_to_tier.get(name, "(legacy)")
        print("  " + core.c("%-9s  %s" % (name.upper(), tier), "white"))
        print(world)
        print()


def cmd_hats(sv, args):
    """Render every species wearing every hat in a side-by-side grid so
    hat placement / fit can be verified per species."""
    eye = "o"
    hat_names = list(HATS.keys())
    panel_pad = 2

    print()
    print("  " + core.c(
        "ALL PETS x ALL HATS - verify hat sits on the head", "white"))
    print()

    for sp_name, sp in SPECIES.items():
        sprite   = [ln.replace("{e}", eye) for ln in sp["art"]]
        sprite_h = len(sprite)
        sprite_w = max(len(ln) for ln in sprite)

        # Find the actual head row (chicken's row 0 is a placeholder).
        head_center  = None
        head_row_idx = 0
        for ridx in range(min(len(sprite), 3)):
            chars = [i for i, c in enumerate(sprite[ridx]) if c != " "]
            if chars:
                head_center = (chars[0] + chars[-1]) / 2
                head_row_idx = ridx
                break
        if head_center is None:
            head_center = sprite_w / 2

        print("  " + core.c("%s (%dx%d, head@col %d row %d)" % (
            sp_name.upper(), sprite_w, sprite_h,
            int(head_center), head_row_idx), "white"))
        print()

        # All hats in this section need the same vertical layout so sprite
        # rows align across the row of panels. Tallest hat sets max_upper.
        max_upper = max(len(HATS[h]) for h in hat_names) - 1

        panels = []
        for hat_type in hat_names:
            rows  = _hat_rows(hat_type) or [""]
            hat_w = max(len(r) for r in rows)
            # Half-up rounding so even-char heads (col center at .5) don't
            # systematically push the hat one col left.
            hat_col = max(0, int(head_center - hat_w / 2 + 0.5))
            panel_w = max(sprite_w, hat_col + hat_w)

            # Bottom row of the hat OVERLAPS the head row - build a merged
            # head/hat row so the panel matches what shows in the live world.
            merged_head = list(sprite[0].ljust(panel_w))
            for j, ch in enumerate(rows[-1]):
                cc = hat_col + j
                if 0 <= cc < panel_w:
                    merged_head[cc] = ch if ch != " " else " "

            # Upper hat rows (everything above the merged head row), padded
            # at the top to match the tallest hat in this section.
            upper = []
            for r in rows[:-1]:
                line = " " * hat_col + r
                line += " " * (panel_w - len(line))
                upper.append(line)
            while len(upper) < max_upper:
                upper.insert(0, " " * panel_w)

            sprite_lines = ["".join(merged_head)] + [
                ln + " " * (panel_w - len(ln)) for ln in sprite[1:]
            ]
            label = hat_type[:panel_w].center(panel_w)
            panels.append([label] + upper + sprite_lines)

        # Print panels in rows of 5 (2 rows of 5 = all 10 hats per species).
        per_row = 5
        for start in range(0, len(panels), per_row):
            batch = panels[start:start + per_row]
            for r in range(len(batch[0])):
                print("  " + (" " * panel_pad).join(p[r] for p in batch))
            print()
        print()


# --- Dispatch + entry point -----------------------------------------------

DISPATCH = {
    "show":    cmd_show,
    "list":    cmd_list,
    "switch":  cmd_switch,
    "new":     cmd_new,
    "rename":  cmd_rename,
    "color":   cmd_color,
    "bag":     cmd_bag,
    "equip":   cmd_equip,
    "rules":   cmd_rules,
    "achievements": cmd_achievements,
    "achv":    cmd_achievements,
    "help":    cmd_help,
    "?":       cmd_help,
    "--help":  cmd_help,
    "-h":      cmd_help,
    "data":    cmd_data,
    "species": cmd_species,
    "preview": cmd_preview,
    "hats":    cmd_hats,
}


def main():
    # Strip ANSI when piped (so `python3 cli.py show | less` is readable).
    core.USE_COLOR = sys.stdout.isatty()
    # One lock around the whole command so a /questline command cannot race
    # a status-line render in another terminal (both load -> mutate -> save).
    with core.save_lock():
        sv = core.load()
        core.ensure_first_pet(sv)
        core.save(sv)
        args = sys.argv[1:]
        cmd  = args[0].lower() if args else "show"
        DISPATCH.get(cmd, cmd_show)(sv, args[1:])


if __name__ == "__main__":
    main()
