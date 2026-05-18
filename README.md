# buddy

[![tests](https://github.com/AlexFloyd13/buddy/actions/workflows/test.yml/badge.svg)](https://github.com/AlexFloyd13/buddy/actions/workflows/test.yml)
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

1. Clone or copy this directory to `~/.claude/buddy`:
   ```bash
   git clone https://github.com/AlexFloyd13/buddy ~/.claude/buddy
   ```
2. Wire it into Claude Code by adding to `~/.claude/settings.json`:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 ~/.claude/buddy/statusline.py"
     }
   }
   ```
3. Restart Claude Code. You'll be hatched a starter pet on first render.

Requires Python 3.8+. No dependencies — pure stdlib.

## How it works

- **XP from tokens.** Every Claude Code message you send adds its `input_tokens + output_tokens + cache_creation_input_tokens` to your active pet's XP. The status line ticks once per render.
- **Leveling.** Quadratic curve calibrated so L100 ("max level") is achievable in ~3 months of max Claude Max-20 usage (~200M tokens cumulative). Early levels are fast, end-game is the grind.
- **Multi-pet, per-terminal.** Each pet has its own L1→L100 progress. Each terminal pins its own active pet via `/buddy switch <n>` — terminal A can be leveling Biscuit while terminal B is leveling Eight, both crediting XP simultaneously to their own pet. Use `--global` if you want to change the default for all terminals.
- **Adventure mode.** The buddy walks rightward through a procedural landscape (trees, bushes, flowers, grass). Wild monsters spawn occasionally, walk toward the buddy, and a fight resolves into a win/loss + XP + possibly a hat drop.
- **Christmas trees.** Ultra-rare (~1 in 20 000 world cols) festive landmark. Walking past one drops a guaranteed Rare+ hat into your inventory.

## CLI commands

Invoke via `/buddy` in Claude Code or by running `python3 ~/.claude/buddy/cli.py <command>` directly:

| Command | What it does |
|---------|--------------|
| `/buddy show` | Render the active pet's full sprite + stats |
| `/buddy list` | List every pet you own |
| `/buddy switch <n>` | Pin pet #n as active in THIS terminal (add `--global` to set the default for all terminals) |
| `/buddy new` | Hatch a brand-new random pet (auto-pinned to this terminal) |
| `/buddy rename <name>` | Rename the active pet (or `rename <n> <name>` for pet #n) |
| `/buddy color [<name>]` | List/set the active pet's color (cosmetic only; unlocked tier by level) |
| `/buddy rules` | Print the full gameplay rules |
| `/buddy bag` | Show your hat inventory |
| `/buddy equip <n>` | Toggle hat #n on the active pet |
| `/buddy species` | Show every species sprite |
| `/buddy preview` | Render every species in the world view |
| `/buddy hats` | Render every species wearing every hat (verify fit) |

## Debug flag

For testing sprite-vs-landscape alignment, write one of these strings to `~/.claude/buddy/.debug_buddy`:

```bash
echo pipe  > ~/.claude/buddy/.debug_buddy   # replace buddy with a single | column
echo none  > ~/.claude/buddy/.debug_buddy   # render with no buddy at all
echo block > ~/.claude/buddy/.debug_buddy   # 2x2 solid rectangle
rm ~/.claude/buddy/.debug_buddy             # restore the real buddy
```

Useful when the landscape looks misaligned and you want to confirm whether the buddy sprite is the cause.

## Privacy

- Pet appearance (species, name, stats) for your first pet is deterministically seeded from the `userID` field in your local `~/.claude.json` — this gives you the same starter pet across reinstalls. The value is never transmitted or stored anywhere except in the seed hash.
- The script reads your transcript file only to count tokens. Transcript paths are sandboxed to `~/.claude/` — a malicious hook payload pointing at, e.g., `/etc/passwd` is rejected.
- Nothing leaves your machine. No telemetry, no network calls, no cloud sync.

## Configuration

Most knobs are in `data.py`:

- `SPECIES` — every species sprite + stats + name pool
- `HATS` — every hat sprite (multi-row lists)
- `xp_to_next(level)` — the leveling curve formula
- `ITEM_RARITY_TABLE` — drop rarity weights
- `XP_TOKEN_FIELDS` — which Claude transcript token fields count toward XP

Adventure tuning lives in `adventure.py`:

- `BUDDY_PANEL_WIDTH` / `BUDDY_OFFSET` — where the buddy sits relative to the wall
- `GROUND_FEATURES` — every tree / bush / grass / flower with spawn rate
- `_big_tree()` / `_christmas_tree()` — tree generators
- `STEP_SECONDS` — walk pace (seconds per col of forward motion)
- `SPAWN_DISTANCE` / `BATTLE_GAP` — combat staging distances

## License

MIT. See [LICENSE](LICENSE).

ASCII art credits in `data.py` `ART_CREDITS`.
