# Changelog

All notable changes to **questline** are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- Renamed the project from `buddy` to `questline`. The save file moved to
  `~/.claude/questline/save.json`; `load()` migrates an existing
  `~/.claude/buddy` save automatically, so pets carry over.
- Hat drops are rarer: level-up drop chance 20% -> 2%, fight-win drop chance
  6% -> 0.8%. Hats now feel earned rather than constant.
- XP curve made much steeper in mid/late game. At heavy usage (~30M
  tokens/day) L50 now takes ~348M cumulative tokens and L100 ~2.73B. Early
  levels are barely affected: L20 is still ~24M.
- Every pet's level is now re-derived from its lifetime XP on load, so a
  change to the XP curve can no longer leave a stored level inconsistent.
  Pets that leveled on the old shallow curve are re-leveled to match.
- Each pet now keeps its own adventure. Walk distance, foes defeated, and
  the combat log are tracked per pet instead of shared across the save.

### Fixed
- Per-pet win/loss record is now tracked. `/questline show` previously
  always printed `W/L 0-0` because combat updated a shared counter the
  per-pet display never read.
- Concurrent terminals no longer clobber each other's save. A load/save
  transaction now holds an advisory file lock (POSIX `flock`; a no-op on
  Windows), so two terminals rendering at once cannot drop each other's XP.
- Fixed an XP-inflation bug: when a session's watermark was evicted (the
  table caps the count) and that session rendered again, its whole
  transcript was re-counted as new XP. An unseen session is now seeded,
  not re-awarded.
- `/questline rules` and the README now report the live XP curve and drop
  rates; both had drifted out of sync with the code.
- `ART_CREDITS` and `LICENSE` now credit the ASCII Art Archive (asciiart.eu)
  accurately, replacing the old "Unknown / user-provided" placeholders.
- README install URL replaced placeholder `YOUR-USERNAME` with `AlexFloyd13`.

### Added
- Full seasonal events calendar: Halloween pumpkins (October), Valentine's
  hearts (Feb 10-16), St. Patrick's clovers (Mar 17), Independence Day
  fireworks (Jul 4), New Year's confetti (Jan 1-7). December already
  bumped the Christmas tree spawn rate 100x.
- `orange` and `pink` color palette entries for the new seasonal art.
- `adventure.current_season()` exposes the active season name (or None)
  for downstream tooling and tests.

## [0.1.0] - 2026-05-16

Initial open-source release.

### Features

- **Status-line pet** that hatches from your Claude Code user ID, levels up from your token usage, and walks rightward through a procedurally generated landscape.
- **19 species** across 5 rarity tiers (Common -> Legendary), each with hand-tuned ASCII art.
- **9 hats** with 6 rarity tiers (Common -> Mythic); rarity scales with pet level so Mythic peaks at ~5% at L100.
- **Color tiers** by level: white -> green -> cyan -> blue -> magenta -> silver (L76-99) -> gold (L100+ prestige). `/questline color` lets you pick any tier you've unlocked.
- **Per-terminal active pet** - each terminal can pin its own pet via `/questline switch <n>`, so 10 terminals can grind 10 pets in parallel. `--global` sets the default.
- **Combat system** - wild monsters spawn ~every 33 walked cols; combat resolves with XP awards and rare hat drops.
- **Christmas tree** - ultra-rare (~1 in 20,000 cols) landmark that gives a guaranteed Rare+ hat when walked past.
- **`/questline help`** and **`/questline rules`** for newcomer discovery.
- **`/questline hats`** preview command renders every species wearing every hat for visual verification.

### Safety / Security

- Sandboxed transcript reads (path traversal blocked).
- Defensive save-file type normalization (corrupted save never crashes the status line).
- Outer try/except fallback in `statusline.py` ensures a render never propagates a crash.

### XP curve

- Calibrated against real Claude Max-20 usage: L100 ~ 200M tokens (~3 months of max usage). Curve is quadratic and keeps escalating past L100 indefinitely.

[Unreleased]: https://github.com/AlexFloyd13/questline/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlexFloyd13/questline/releases/tag/v0.1.0
