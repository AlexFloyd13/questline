#!/usr/bin/env python3
"""/buddy subcommand dispatcher: show, list, switch, new, bag, equip, data.
Renders the mechanical visuals; emits a ---DATA--- JSON blob for Claude to add
personality (speech bubbles, talk)."""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
from data import SPECIES, STATS, STAT_LABELS, RARITY_STARS, HATS, xp_to_next


def _pet_data(sv, pet):
    ts = core.total_stats(pet)
    top = max(ts, key=ts.get)
    low = min(ts, key=ts.get)
    hat = core.get_equipped(sv, pet, "hat")
    return {
        "name": pet["name"], "species": pet["species"], "rarity": pet["rarity"],
        "shiny": pet["shiny"], "level": pet["level"],
        "color": core.color_for_level(pet["level"]),
        "stats": ts, "top_stat": top, "low_stat": low,
        "total_tokens": pet["total_tokens"],
        "wins": pet.get("wins", 0), "losses": pet.get("losses", 0),
        "equipped_hat": hat["type"] if hat else None,
        "pet_count": len(sv["pets"]),
        "first_hatch": len(sv["pets"]) == 1 and pet["level"] == 1 and pet["total_tokens"] == 0,
        "hatched_at": pet["hatched_at"],
    }


def _stat_block(pet):
    ts = core.total_stats(pet)
    for s in STATS:
        print("  %-10s %s  %d" % (STAT_LABELS[s], core.stat_bar(ts[s]), ts[s]))


def cmd_show(sv, args):
    pet = core.active_pet(sv)
    lc = core.color_for_level(pet["level"])
    shiny = "  *SHINY*" if pet["shiny"] else ""
    print()
    print("  " + core.c("%s %s  \"%s\"%s" % (
        RARITY_STARS[pet["rarity"]], pet["species"].upper(), pet["name"], shiny), lc))
    print("  " + core.c("Lv %d" % pet["level"], lc)
          + core.c("  -  %s  -  %s tier" % (pet["rarity"], lc), "white"))
    print("  " + core.c("-" * 42, lc))
    print()
    print(core.render_sprite(sv, pet))
    print()
    _stat_block(pet)
    print()
    need = xp_to_next(pet["level"])
    print("  %-10s %s  %s / %s" % ("XP", core.xp_bar(pet),
                                   core.fmt_tokens(pet["xp"]), core.fmt_tokens(need)))
    print("  %-10s %s lifetime  -  W/L %d-%d" % (
        "", core.fmt_tokens(pet["total_tokens"]),
        pet.get("wins", 0), pet.get("losses", 0)))
    hat = core.get_equipped(sv, pet, "hat")
    if hat:
        print("  gear: hat " + core.crarity(hat["type"], hat["rarity"]))
    if len(sv["pets"]) > 1:
        print("  " + core.c("(%d pets - /buddy list)" % len(sv["pets"]), "white"))
    print()
    print("---DATA---")
    print(json.dumps(_pet_data(sv, pet)))


def cmd_list(sv, args):
    pets = list(sv["pets"].values())
    print()
    print("  " + core.c("YOUR PETS (%d)" % len(pets), "white"))
    print()
    for i, p in enumerate(pets, 1):
        act = core.c(">", core.color_for_level(p["level"])) if p["id"] == sv["active"] else " "
        lc = core.color_for_level(p["level"])
        print("  [%d] %s %-12s %-9s %-7s %-10s %s" % (
            i, act, core.name_tag(p), p["species"],
            core.c("Lv%d" % p["level"], lc), p["rarity"], RARITY_STARS[p["rarity"]]))
    print()
    print("  " + core.c("/buddy switch <n>   -   /buddy new   -   /buddy bag", "white"))
    print()


def cmd_switch(sv, args):
    pets = list(sv["pets"].values())
    if not args or not args[0].isdigit():
        print("  usage: /buddy switch <n>   (see /buddy list)")
        return
    n = int(args[0])
    if n < 1 or n > len(pets):
        print("  no pet #%d - you have %d." % (n, len(pets)))
        return
    p = pets[n - 1]
    old = core.active_pet(sv)
    sv["active"] = p["id"]
    core.save(sv)
    print()
    if old and old["id"] != p["id"]:
        print("  active: %s -> %s" % (core.name_tag(old), core.name_tag(p)))
    else:
        print("  active: %s" % core.name_tag(p))
    print("  " + core.c("token XP now flows to %s." % p["name"], "white"))
    print()
    print(core.render_sprite(sv, p))
    print()


def cmd_new(sv, args):
    p = core.add_random_pet(sv)
    sv["active"] = p["id"]
    core.save(sv)
    lc = core.color_for_level(p["level"])
    shiny = "  *SHINY*" if p["shiny"] else ""
    print()
    print("  " + core.c("* a new buddy hatched! *", "white"))
    print()
    print(core.render_sprite(sv, p))
    print()
    print("  " + core.c("%s %s  \"%s\"%s" % (
        RARITY_STARS[p["rarity"]], p["species"].upper(), p["name"], shiny), lc))
    print("  " + core.c("Lv 1  -  %s" % p["rarity"], "white"))
    print()
    _stat_block(p)
    print()
    print("  " + core.c("%s is now active - XP flows here. /buddy switch to change back."
                        % p["name"], "white"))
    print()
    print("---DATA---")
    print(json.dumps(_pet_data(sv, p)))


def cmd_bag(sv, args):
    inv = core.inv_list(sv)
    print()
    print("  " + core.c("INVENTORY (%d)" % len(inv), "white"))
    if not inv:
        print()
        print("  empty - hats drop when pets level up or win fights.")
        print()
        return
    equipped = {}
    for p in sv["pets"].values():
        if p.get("equipped_hat"):
            equipped[p["equipped_hat"]] = p["name"]
    print()
    print("  " + core.c("HATS", "white"))
    for i, it in enumerate(inv, 1):
        hat_rows = HATS.get(it["type"])
        if hat_rows is None:
            continue  # skip retired hat types (e.g., old grad_cap drops)
        if isinstance(hat_rows, str):
            hat_rows = [hat_rows]
        glyph = hat_rows[-1].strip()  # bottom row is the "main" hat shape
        tag = ("  > equipped on %s" % equipped[it["iid"]]) if it["iid"] in equipped else ""
        print("  [%d] %-9s %-5s %-10s %s%s" % (
            i, core.crarity(it["type"], it["rarity"]),
            core.crarity(glyph, it["rarity"]), it["rarity"],
            RARITY_STARS[it["rarity"]], core.c(tag, "white")))
    print()
    print("  " + core.c("/buddy equip <n>   (toggles it on your active pet)", "white"))
    print()


def cmd_equip(sv, args):
    inv = core.inv_list(sv)
    if not args or not args[0].isdigit():
        print("  usage: /buddy equip <n>   (see /buddy bag)")
        return
    n = int(args[0])
    if n < 1 or n > len(inv):
        print("  no hat #%d - you have %d." % (n, len(inv)))
        return
    it = inv[n - 1]
    pet = core.active_pet(sv)
    print()
    if pet.get("equipped_hat") == it["iid"]:
        pet["equipped_hat"] = None
        core.save(sv)
        print("  %s unequipped its %s." % (pet["name"], it["type"]))
    else:
        pet["equipped_hat"] = it["iid"]
        core.save(sv)
        print("  %s equipped %s %s." % (
            pet["name"], core.crarity(it["type"], it["rarity"]), RARITY_STARS[it["rarity"]]))
        print()
        print(core.render_sprite(sv, pet))
    print()


def cmd_data(sv, args):
    print(json.dumps(_pet_data(sv, core.active_pet(sv)), indent=2))


def cmd_species(sv, args):
    """Show every available species so the user can approve each design.
    Sprites have variable widths and heights; we align them at the BOTTOM
    so each species reads as standing on a shared ground line."""
    eye = "o"
    cols_per_row = 3  # 3 sprites per row gives more breathing room
    gap = "     "
    names = list(SPECIES.keys())
    print()
    print("  " + core.c("ALL %d BUDDIES (eye='o', no hat)" % len(names), "white"))
    print()
    for i in range(0, len(names), cols_per_row):
        batch = names[i:i + cols_per_row]
        sprites = [[ln.replace("{e}", eye) for ln in SPECIES[n]["art"]] for n in batch]
        widths = [max(len(r) for r in s) for s in sprites]
        max_h = max(len(s) for s in sprites)
        # label row, centered on each sprite's width
        labels = [n.upper().center(widths[k]) for k, n in enumerate(batch)]
        print("  " + gap.join(labels))
        # render each row, padding shorter sprites at top so they bottom-align
        for r in range(max_h):
            parts = []
            for k, s in enumerate(sprites):
                pad = max_h - len(s)
                if r < pad:
                    parts.append(" " * widths[k])
                else:
                    parts.append(s[r - pad])
            print("  " + gap.join(parts))
        # ground line
        print("  " + gap.join(["_" * widths[k] for k in range(len(batch))]))
        # theme
        themes = ["+".join(SPECIES[n]["theme"]).center(widths[k])
                  for k, n in enumerate(batch)]
        print("  " + core.c(gap.join(themes), "white"))
        print()


def cmd_preview(sv, args):
    """Render every species INSIDE the actual status-line world view, so the
    user can see exactly how each one would look in their live status bar."""
    import adventure
    core.USE_COLOR = sys.stdout.isatty()
    # build a temp pet dict shaped like a real one
    template = {
        "id": "preview", "name": "Preview", "rarity": "Common", "shiny": False,
        "eyes": "o", "base_stats": {s: 50 for s in STATS},
        "earned_stats": {s: 0 for s in STATS},
        "level": 1, "xp": 0, "total_tokens": 0,
        "equipped_hat": None,
        "wins": 0, "losses": 0, "hatched_at": "preview",
    }
    # find rarity of each species
    species_to_tier = {}
    from data import SPECIES_TIERS
    for tier, species in SPECIES_TIERS.items():
        for s in species:
            species_to_tier[s] = tier
    print()
    for name in SPECIES:
        pet = dict(template, species=name, name=name.capitalize())
        # use a clean fake save so the world is empty (just buddy + ground)
        fake_sv = {"pets": {"preview": pet}, "active": "preview",
                   "inventory": [], "adventure": {"buddy_col": 5}}
        world = adventure.render_world(fake_sv, pet, width=80)
        tier = species_to_tier.get(name, "(legacy)")
        print("  " + core.c("%-9s  %s" % (name.upper(), tier), "white"))
        print(world)
        print()


def cmd_hats(sv, args):
    """Render every species wearing every hat so the user can verify fit.
    Each species gets a section with the species name on top, then 10 mini
    panels (one per hat) showing 'hat-name' label + sprite + hat overlay."""
    eye = "o"
    template = {
        "id": "preview", "name": "Preview", "rarity": "Common", "shiny": False,
        "eyes": eye, "base_stats": {s: 50 for s in STATS},
        "earned_stats": {s: 0 for s in STATS},
        "level": 1, "xp": 0, "total_tokens": 0,
        "equipped_hat": None,
        "wins": 0, "losses": 0, "hatched_at": "preview",
    }
    hat_names = list(HATS.keys())
    panel_pad = 2  # spaces between panels
    print()
    print("  " + core.c("ALL BUDDIES x ALL HATS — verify hat sits on the head",
                        "white"))
    print()
    for sp_name, sp in SPECIES.items():
        sprite = [ln.replace("{e}", eye) for ln in sp["art"]]
        sprite_h = len(sprite)
        sprite_w = max(len(ln) for ln in sprite)
        # head center for hat positioning — fall through empty rows
        head_center = None
        head_row_idx = 0
        for ridx in range(min(len(sprite), 3)):
            chars = [i for i, c in enumerate(sprite[ridx]) if c != " "]
            if chars:
                head_center = (chars[0] + chars[-1]) / 2
                head_row_idx = ridx
                break
        if head_center is None:
            head_center = sprite_w / 2

        head_row_chars = [i for i, c in enumerate(sprite[head_row_idx]) if c != " "]

        print("  " + core.c("%s (%dx%d, head@col %d row %d)" % (
            sp_name.upper(), sprite_w, sprite_h,
            int(head_center), head_row_idx), "white"))
        print()
        # Build a panel per hat: hat row, then sprite rows. Each panel is
        # max(sprite_w, hat_visible_w + offset) wide.
        # All hats in this section need the same total panel height so the
        # sprite rows align across panels. Tallest hat has the most upper rows.
        max_upper = max(len(HATS[h]) for h in hat_names) - 1
        panels = []
        for hat_type in hat_names:
            hat_rows = HATS[hat_type]
            if isinstance(hat_rows, str):
                hat_rows = [hat_rows]
            hat_w = max(len(r) for r in hat_rows)
            # Center the hat on the head's TRUE center (fractional ok).
            head_center_f = head_center if head_row_chars else sprite_w / 2
            # int(x + 0.5) — half-up rounding (Python's round() is banker's).
            hat_col = max(0, int(head_center_f - hat_w / 2 + 0.5))
            panel_w = max(sprite_w, hat_col + hat_w)

            # Bottom hat row OVERLAPS sprite row 0 (the head). Build a merged
            # head/hat row: start with sprite row 0 padded, then for every col
            # in the hat's footprint replace it with the hat char (non-space)
            # or a space (so head chars don't peek through hat gaps).
            merged_head = list(sprite[0].ljust(panel_w))
            bot = hat_rows[-1]
            for j, ch in enumerate(bot):
                cc = hat_col + j
                if 0 <= cc < panel_w:
                    merged_head[cc] = ch if ch != " " else " "
            merged_head_str = "".join(merged_head)

            # Upper hat rows render above the sprite as before; pad with
            # empty lines on top so shorter hats still line up vertically
            # with the tallest hat in this section.
            upper_lines = []
            for r in hat_rows[:-1]:
                line = " " * hat_col + r
                line += " " * (panel_w - len(line))
                upper_lines.append(line)
            while len(upper_lines) < max_upper:
                upper_lines.insert(0, " " * panel_w)

            sprite_lines = [merged_head_str] + [
                ln + " " * (panel_w - len(ln)) for ln in sprite[1:]
            ]
            label = hat_type[:panel_w].center(panel_w)
            panels.append([label] + upper_lines + sprite_lines)

        # Render panels in rows of 5 (so 2 rows show 10 hats)
        per_row = 5
        for batch_start in range(0, len(panels), per_row):
            batch = panels[batch_start:batch_start + per_row]
            rows = len(batch[0])
            for r in range(rows):
                line_parts = [p[r] for p in batch]
                print("  " + (" " * panel_pad).join(line_parts))
            print()
        print()


DISPATCH = {
    "show": cmd_show, "list": cmd_list, "switch": cmd_switch,
    "new": cmd_new, "bag": cmd_bag, "equip": cmd_equip, "data": cmd_data,
    "species": cmd_species, "preview": cmd_preview, "hats": cmd_hats,
}


def main():
    core.USE_COLOR = sys.stdout.isatty()
    sv = core.load()
    core.ensure_first_pet(sv)
    core.save(sv)
    args = sys.argv[1:]
    cmd = args[0].lower() if args else "show"
    DISPATCH.get(cmd, cmd_show)(sv, args[1:])


if __name__ == "__main__":
    main()
