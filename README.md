# questline

[![tests](https://github.com/AlexFloyd13/questline/actions/workflows/test.yml/badge.svg)](https://github.com/AlexFloyd13/questline/actions/workflows/test.yml)
[![python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![license MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![no deps](https://img.shields.io/badge/dependencies-none-brightgreen)](#install)

A tiny ASCII pet for your [Claude Code](https://docs.claude.com/en/docs/claude-code) status line. Hatches a procedural creature, levels it up from your token usage, walks through a procedurally-generated landscape, fights wild monsters, finds hats, and occasionally bumps into a Christmas tree that gives it a present.

```
|                                      ^
|         __           /\             /^\                      /\  /\       /\                               /\          /\
|    (___()'`;         /\            //^\\                     /\  /\       /\                               /\          /\
|    /,    /`          /\           ///^\\\                    /\  /\       /\                               /\          /\
_____\"---\\___________||____,_________||,________,________,___||__||_______||__,___,,,______vvv__,___,,,____||__________||_______
  Biscuit  Lvl 45  [##----------]  72 foes  last: won vs bun +180xp  +1 pets  +14 hats
```

## Install

1. Clone or copy this directory to `~/.claude/questline`:
   ```bash
   git clone https://github.com/AlexFloyd13/questline ~/.claude/questline
   ```
2. Wire it into Claude Code by adding to `~/.claude/settings.json`:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 ~/.claude/questline/statusline.py"
     }
   }
   ```
3. Restart Claude Code. You'll be hatched a starter pet on first render.

Requires Python 3.8+. No dependencies - pure stdlib.

## How it works

- **XP from tokens.** Every Claude Code message you send adds its `input_tokens + output_tokens + cache_creation_input_tokens` to your active pet's XP. The status line ticks once per render.
- **Leveling.** Quadratic curve - L100 ("max level") takes ~2.7B cumulative tokens, roughly 3 months of heavy daily usage (~30M tokens/day). Early levels are fast, end-game is the grind. The whole curve is one function (`xp_to_next` in `data.py`) - fork it and rebalance if you want.
- **Multi-pet, per-terminal.** Each pet has its own L1-100 progression *and* its own adventure - walk position, foes defeated, and combat log are all tracked per pet. Each terminal pins its own active pet via `/questline switch <n>`, so terminal A can level Biscuit while terminal B levels Eight, both crediting XP at once. Use `--global` to change the default for all terminals.
- **Adventure mode.** The pet walks rightward through a procedural landscape (trees, bushes, flowers, grass). Wild monsters spawn occasionally, walk toward the pet, and a fight resolves into a win/loss + XP + possibly a hat drop.
- **Christmas trees.** Ultra-rare (~1 in 20 000 world cols) festive landmark. Walking past one drops a guaranteed Rare+ hat into your inventory.

## CLI commands

Invoke via `/questline` in Claude Code or by running `python3 ~/.claude/questline/cli.py <command>` directly:

| Command | What it does |
|---------|--------------|
| `/questline show` | Render the active pet's full sprite + stats |
| `/questline list` | List every pet you own |
| `/questline switch <n>` | Pin pet #n as active in THIS terminal (add `--global` to set the default for all terminals) |
| `/questline new` | Hatch a brand-new random pet (auto-pinned to this terminal) |
| `/questline rename <name>` | Rename the active pet (or `rename <n> <name>` for pet #n) |
| `/questline color [<name>]` | List/set the active pet's color (cosmetic only; unlocked tier by level) |
| `/questline rules` | Print the full gameplay rules |
| `/questline bag` | Show your hat inventory |
| `/questline equip <n>` | Toggle hat #n on the active pet |
| `/questline species` | Show every species sprite |
| `/questline preview` | Render every species in the world view |
| `/questline hats` | Render every species wearing every hat (verify fit) |
| `/questline achievements` | List milestones (unlocked + locked) and your daily streak |
| `/questline help` | List every command |

## Debug flag

For testing sprite-vs-landscape alignment, write one of these strings to `~/.claude/questline/.debug_questline`:

```bash
echo pipe  > ~/.claude/questline/.debug_questline   # replace the pet with a single | column
echo none  > ~/.claude/questline/.debug_questline   # render with no pet at all
echo block > ~/.claude/questline/.debug_questline   # 2x2 solid rectangle
rm ~/.claude/questline/.debug_questline             # restore the real pet
```

Useful when the landscape looks misaligned and you want to confirm whether the pet sprite is the cause.

## Privacy

- Pet appearance (species, name, stats) for your first pet is deterministically seeded from the `userID` field in your local `~/.claude.json` - this gives you the same starter pet across reinstalls. The value is never transmitted or stored anywhere except in the seed hash.
- The script reads your transcript file only to count tokens. Transcript paths are sandboxed to `~/.claude/` - a malicious hook payload pointing at, e.g., `/etc/passwd` is rejected.
- Nothing leaves your machine. No telemetry, no network calls, no cloud sync.

## Configuration

Most knobs are in `data.py`:

- `SPECIES` - every species sprite + stats + name pool
- `HATS` - every hat sprite (multi-row lists)
- `xp_to_next(level)` - the leveling curve formula
- `ITEM_RARITY_TABLE` - drop rarity weights
- `XP_TOKEN_FIELDS` - which Claude transcript token fields count toward XP

Adventure tuning lives in `adventure.py`:

- `BUDDY_PANEL_WIDTH` / `BUDDY_OFFSET` - where the pet sits relative to the wall
- `GROUND_FEATURES` - every tree / bush / grass / flower with spawn rate
- `_big_tree()` / `_christmas_tree()` - tree generators
- `STEP_SECONDS` - walk pace (seconds per col of forward motion)
- `SPAWN_DISTANCE` / `BATTLE_GAP` - combat staging distances

## License

MIT. See [LICENSE](LICENSE).

Species ASCII art is adapted from the [ASCII Art Archive](https://www.asciiart.eu) with attribution; see `data.py` `ART_CREDITS` and [LICENSE](LICENSE) for per-sprite credits.
