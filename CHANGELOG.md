# Changelog

All notable changes to **buddy** are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] — 2026-05-16

Initial open-source release.

### Features

- **Status-line pet** that hatches from your Claude Code user ID, levels up from your token usage, and walks rightward through a procedurally generated landscape.
- **19 species** across 5 rarity tiers (Common → Legendary), each with hand-tuned ASCII art.
- **9 hats** with 6 rarity tiers (Common → Mythic); rarity scales with pet level so Mythic peaks at ~5% at L100.
- **Color tiers** by level: white → green → cyan → blue → magenta → silver (L76-99) → gold (L100+ prestige). `/buddy color` lets you pick any tier you've unlocked.
- **Per-terminal active pet** — each terminal can pin its own pet via `/buddy switch <n>`, so 10 terminals can grind 10 pets in parallel. `--global` sets the default.
- **Combat system** — wild monsters spawn ~every 33 walked cols; combat resolves with XP awards and rare hat drops.
- **Christmas tree** — ultra-rare (~1 in 20,000 cols) landmark that gives a guaranteed Rare+ hat when walked past.
- **`/buddy help`** and **`/buddy rules`** for newcomer discovery.
- **`/buddy hats`** preview command renders every species wearing every hat for visual verification.

### Safety / Security

- Sandboxed transcript reads (path traversal blocked).
- Defensive save-file type normalization (corrupted save never crashes the status line).
- Outer try/except fallback in `statusline.py` ensures a render never propagates a crash.

### XP curve

- Calibrated against real Claude Max-20 usage: L100 ≈ 200M tokens (~3 months of max usage). Curve is quadratic and keeps escalating past L100 indefinitely.

[Unreleased]: https://github.com/AlexFloyd13/buddy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlexFloyd13/buddy/releases/tag/v0.1.0
