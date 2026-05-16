#!/usr/bin/env python3
"""Claude Code status line entry point.

Claude Code runs this script once per status-line render: it pipes a small
JSON payload to stdin (session_id, transcript_path, optional width) and
displays whatever this script writes to stdout in the bottom status bar.

What we do each render:
  1. Read the hook payload from stdin.
  2. Load the user's save (or hatch a starter pet if it's the first run).
  3. Count any new tokens in the active session's transcript and award them
     as XP to the active pet — leveling up if it crosses thresholds.
  4. Tick the adventure forward (walking, combat).
  5. Render the world + a one-line summary and write it to stdout.

This script runs constantly and must never crash. The outer try/except in
`__main__` falls back to a one-line mini face if anything goes wrong, so
the user always sees SOMETHING in their status line.
"""

import sys, os, json, re, shutil
from pathlib import Path

# Make sibling modules (core, data, adventure) importable regardless of
# the cwd Claude Code happens to invoke us from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# --- Path safety -----------------------------------------------------------
# `transcript_path` arrives unverified from the Claude Code hook payload.
# A malicious payload (or buggy upstream) could point it at /etc/passwd,
# ~/.ssh/id_rsa, etc. We sandbox transcript reads to the user's ~/.claude
# tree — anything else gets silently rejected.

SAFE_TRANSCRIPT_ROOT = (Path.home() / ".claude").resolve()


def _safe_transcript(path):
    """Resolve `path` and return it as a string iff it sits inside the
    safe transcript root. Returns None for empty input, resolution
    failures, or paths outside the safe root."""
    if not path:
        return None
    try:
        p = Path(path).resolve()
    except Exception:
        return None
    try:
        p.relative_to(SAFE_TRANSCRIPT_ROOT)
    except ValueError:
        return None
    return str(p)


# --- Terminal width detection ---------------------------------------------

def _term_width(inp):
    """Best-effort terminal width for the world render. Tries (in order):
    the JSON payload's own width hint, the COLUMNS env var, the live
    terminal size, then a 130-col fallback."""
    for k in ("terminal_width", "width", "columns"):
        v = inp.get(k)
        if isinstance(v, int) and v > 20:
            return v
    try:
        cols = int(os.environ.get("COLUMNS", "0"))
        if cols > 20:
            return cols
    except Exception:
        pass
    try:
        return shutil.get_terminal_size((130, 24)).columns
    except Exception:
        return 130


# --- Transcript -> XP -----------------------------------------------------

def count_tokens(path):
    """Sum the XP-eligible token fields across every assistant turn in the
    given transcript file. Refuses paths outside the safe root and returns
    0 on any read/parse failure (the status line never propagates errors)."""
    safe = _safe_transcript(path)
    if not safe:
        return 0
    from data import XP_TOKEN_FIELDS
    total = 0
    try:
        with open(safe, "r") as f:
            for line in f:
                # Cheap pre-filter — only parse lines that look like they
                # contain a usage block. The transcript can have lots of
                # non-assistant lines we don't care about.
                if '"usage"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                usage = (obj.get("message") or {}).get("usage") or {}
                for k in XP_TOKEN_FIELDS:
                    total += usage.get(k, 0) or 0
    except Exception:
        pass
    return total


# --- Debug sprite override ------------------------------------------------
# Write one of "none" / "pipe" / "block" to ~/.claude/buddy/.debug_buddy
# to replace the active pet with a minimal sprite for one render. Useful
# for confirming whether the live landscape's alignment is the renderer's
# fault or your terminal's. Delete the file to restore the real pet.

_DEBUG_PATH = Path.home() / ".claude" / "buddy" / ".debug_buddy"

_DEBUG_SPRITES = {
    "none":  [" "],                      # render with effectively no pet
    "pipe":  ["|", "|", "|", "|"],       # single | column, 4 rows
    "block": ["##", "##", "##", "##"],   # uniform 2x2 solid block
}


def _read_debug_sprite():
    """Returns a sprite list to swap in, or None if no debug file."""
    try:
        flag = _DEBUG_PATH.read_text().strip()
    except Exception:
        return None
    return _DEBUG_SPRITES.get(flag)


# --- Status line rendering ------------------------------------------------

def render_line(sv, pet, width):
    """Full status line: the multi-row world on top, a one-line summary
    underneath. Returns a single newline-joined string."""
    import core, adventure
    from data import SPECIES

    lc = core.color_for_pet(pet)
    st = adventure._state(sv)

    # Honor the .debug_buddy override (single-threaded, safe to mutate
    # SPECIES in place since each render is its own subprocess).
    debug_sprite = _read_debug_sprite()
    orig_art = None
    if debug_sprite is not None:
        orig_art = SPECIES[pet["species"]]["art"]
        SPECIES[pet["species"]]["art"] = debug_sprite
    try:
        world = adventure.render_world(sv, pet, width=width)
    finally:
        if orig_art is not None:
            SPECIES[pet["species"]]["art"] = orig_art

    # The "event" segment narrates what's happening right now: walking,
    # an active encounter (with per-turn flavor), or the last log line.
    enc = st.get("encounter")
    if enc:
        e_color = adventure.ENEMIES.get(enc["key"], {}).get("color", "magenta")
        if enc["phase"] == "approach":
            event = core.c("! wild %s approaches" % enc["key"], e_color)
        elif enc["turn"] == 0:
            event = core.c("%s squares up" % pet["name"], lc)
        elif enc["turn"] == 1:
            event = core.c("%s strikes!" % pet["name"], lc)
        elif enc["turn"] == 2:
            event = core.c("%s counters!" % enc["key"], e_color)
        elif enc["turn"] == 3:
            event = core.c("CLASH!", "magenta")
        else:
            event = core.c("...", "white")
    elif st.get("log"):
        event = core.c("last: " + st["log"][-1], "white")
    else:
        event = core.c("walking...", "white")

    # Counters: other pets in the stable, total hats in inventory, and the
    # active daily-usage streak. All only show when nonzero/meaningful so
    # the status line stays clean for new players.
    extra_pets = len(sv["pets"]) - 1
    extra_hats = len(core.inv_list(sv))
    streak = sv.get("streak_days", 0)
    counter_parts = []
    if extra_pets > 0:
        counter_parts.append(core.c("+%d pets" % extra_pets, "white"))
    if extra_hats > 0:
        counter_parts.append(core.c("+%d hats" % extra_hats, "white"))
    if streak >= 2:  # day 1 is uninteresting; show from 2+
        counter_parts.append(core.c("%dd streak" % streak, "gold"))
    extras = "  " + "  ".join(counter_parts) if counter_parts else ""

    # Sleep state: append a small zZz marker next to the pet name if the
    # pet hasn't earned XP in 24+ hours. Disappears the moment new tokens
    # roll in for that pet.
    name_seg = core.name_tag(pet)
    if core.is_sleeping(pet):
        name_seg += " " + core.c("zZz", "silver")

    info = "  %s  %s  %s  %s  %s%s" % (
        name_seg,
        core.c("Lvl %d" % pet["level"], lc),
        core.c(core.xp_bar(pet, 12), lc),
        core.c("%d foes" % st.get("kills", 0), "white"),
        event,
        extras,
    )

    return "\n".join([world, info])


# --- Entry point ----------------------------------------------------------

def main():
    """Per-render entry. Read hook JSON, award any new tokens as XP to the
    active pet, tick the adventure forward, render, write to stdout."""
    raw = sys.stdin.read()
    try:
        inp = json.loads(raw) if raw.strip() else {}
    except Exception:
        inp = {}
    session_id = inp.get("session_id") or "unknown"
    transcript = _safe_transcript(inp.get("transcript_path"))

    import core
    sv = core.load()
    core.ensure_first_pet(sv)
    # Remember which terminal session just rendered so /buddy switch can
    # pin to THIS terminal (not someone else's idle terminal).
    sv["current_session"] = session_id
    # Active pet is per-terminal (with global sv['active'] as fallback).
    pet = core.active_pet_for_session(sv, session_id)

    # Stat the transcript so we can short-circuit when it hasn't changed
    # (avoids re-reading and re-counting the whole file every render).
    try:
        s = os.stat(transcript) if transcript else None
        mtime = s.st_mtime if s else 0
        size  = s.st_size  if s else 0
    except Exception:
        mtime, size = 0, 0

    # Per-session watermark: remember last (mtime, size, tokens) so we can
    # award only NEW tokens since the last render of this session.
    wm = sv.setdefault("watermarks", {})
    entry = wm.get(session_id)
    unchanged = entry and entry.get("mtime") == mtime and entry.get("size") == size

    if transcript and not unchanged:
        total = count_tokens(transcript)
        prev  = entry.get("tokens", 0) if entry else 0
        delta = max(0, total - prev)
        if delta:
            core.apply_xp(sv, pet, delta)
        wm[session_id] = {"mtime": mtime, "size": size, "tokens": total}
        # Cap the watermark dict at 30 sessions so it doesn't grow forever.
        if len(wm) > 30:
            for sid in sorted(wm, key=lambda s: wm[s].get("mtime", 0))[:-30]:
                del wm[sid]

    # Tick the world forward (walking, encounter, combat).
    import adventure
    adventure.advance(sv, pet)

    # Bookkeeping: daily streak + achievement check (cheap; both run after
    # any XP changes so newly-unlocked milestones surface in the next render).
    core.update_streak(sv)
    newly = core.check_achievements(sv)
    if newly:
        # Log each unlocked achievement so the info row picks it up via
        # the same st["log"] mechanism used by combat / christmas gifts.
        from data import ACHIEVEMENTS
        log = sv.setdefault("adventure", {}).setdefault("log", [])
        for aid in newly:
            name, _desc, _pred = ACHIEVEMENTS[aid]
            log.append("unlocked: %s" % name)
        del log[:-3]

    core.save(sv)

    sys.stdout.write(render_line(sv, pet, _term_width(inp)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A broken status line is worse than a boring one — fall back to
        # a one-line mini-face plus the word "buddy" so the user knows
        # something is still alive.
        try:
            import core
            sv = core.load()
            core.ensure_first_pet(sv)
            sys.stdout.write(core.mini_face(core.active_pet(sv)) + " buddy")
        except Exception:
            sys.stdout.write("buddy")
