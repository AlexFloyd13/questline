# Contributing to questline

Thanks for the interest! questline is a tiny project with a small surface area. Most contributions land cleanly if you read this first.

## Local setup

```bash
git clone https://github.com/AlexFloyd13/questline ~/path/to/questline
cd ~/path/to/questline
python3 -m unittest tests.smoke    # runs in <1s, no deps
```

Symlink your checkout into Claude Code's expected path while you develop:

```bash
ln -s "$(pwd)" ~/.claude/questline
```

Now every change to your checkout shows up in your live status line on the next render.

## Running the smoke tests

```bash
python3 -m unittest tests.smoke -v
```

The suite covers render robustness (brand-new user, missing or malicious
transcript paths, corrupted and empty saves, a 40-column terminal, a
10-billion-column walk), `core.load()`'s defensive normalization, the
path-traversal guard, and the core mechanics: leveling math, per-pet
adventure isolation, and the save migrations.

CI runs these on every PR via `.github/workflows/test.yml`.

## Adding a new species

1. **Add the sprite** to `SPECIES` in `data.py`. Pick a width and height, fill in `theme` (two favored stats), `mini` (compact face), and `art` (list of rows, ALL the same width).
2. **Add to a rarity tier** in `SPECIES_TIERS` - Common, Uncommon, Rare, Epic, or Legendary.
3. **Add cute names** to `NAMES` (5 candidates is the convention).
4. **If the art is third-party**, add an attribution line to `ART_CREDITS` and to the bottom of `LICENSE`.
5. Run `python3 cli.py species` and `python3 cli.py hats` to verify your sprite renders correctly and every hat sits on the head.

## Adding a new hat

1. **Add to `HATS`** in `data.py`. List of strings (each row), bottom row sits ON the head, additional rows stack upward.
2. **Verify fit on every species**: `python3 cli.py hats`.
3. **Keep the bottom row covering the head**: if it has internal spaces (like `( O )`), those spaces will clear the head row chars underneath them - desired behavior, but worth knowing.

## Adding a landscape feature

`GROUND_FEATURES` in `adventure.py`. Each entry needs `rate` (spawn probability per world position), `color`, and `art` (list of rows). Optional: `row_colors`, `char_colors` for per-row / per-char overrides. Trees 6+ rows get the "big tree" placement pass (different spacing rules).

## Code style

- Match what's there. We mix `%` formatting and f-strings (don't worry about it).
- No external dependencies. Pure stdlib only - this rule is load-bearing for installability.
- Comments explain WHY, not WHAT. Skip docstrings for trivial helpers.
- Stay defensive in `statusline.py` - that script runs every render and a crash there breaks the user's UI.

## Filing issues

Use the templates in `.github/ISSUE_TEMPLATE/`. The "bug report" template asks for a render dump (`python3 ~/.claude/questline/statusline.py < /dev/null`) which makes alignment / color bugs reproducible.

## License

MIT. By contributing you agree your work is MIT-licensed too.
