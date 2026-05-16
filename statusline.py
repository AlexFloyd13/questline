#!/usr/bin/env python3
"""Claude Code status line: renders the active buddy + converts session tokens
into XP. Runs constantly, so it must be fast and must never crash."""
import sys, os, json, re, shutil
from pathlib import Path

# Transcripts (and any external path we read from the Claude Code hook payload)
# must live under the user's .claude home. This blocks a malicious payload from
# pointing transcript_path at /etc/passwd, ~/.ssh/id_rsa, etc.
SAFE_TRANSCRIPT_ROOT = (Path.home() / ".claude").resolve()


def _safe_transcript(path):
    """Return `path` if it resolves inside the user's ~/.claude tree, else None."""
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _term_width(inp):
    for k in ("terminal_width", "width", "columns"):
        v = inp.get(k)
        if isinstance(v, int) and v > 20:
            return v
    # Claude Code doesn't pass terminal width, so check env then fall back
    # to a conservative width that fits in narrow status-line areas without
    # wrapping (wrapping is what makes the buddy look split across rows).
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


def right_align(text, width):
    out = []
    for line in text.split("\n"):
        visible = _ANSI.sub("", line)
        pad = max(0, width - len(visible) - 1)
        out.append(" " * pad + line)
    return "\n".join(out)


def count_tokens(path):
    """Sum XP-eligible token fields across all assistant turns in a transcript.
    Refuses to read paths outside the user's ~/.claude tree."""
    safe = _safe_transcript(path)
    if not safe:
        return 0
    from data import XP_TOKEN_FIELDS
    total = 0
    try:
        with open(safe, "r") as f:
            for line in f:
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


def render_line(sv, pet, width):
    """Status line = full-width scrolling world + single-line summary."""
    import core, adventure
    from data import SPECIES
    lc = core.color_for_level(pet["level"])
    ts = core.total_stats(pet)
    st = adventure._state(sv)

    # DEBUG: file-flag sprite override to isolate buddy-vs-landscape misalignment.
    # Write one of these strings to ~/.claude/buddy/.debug_buddy:
    #   none   -> 1x1 space (effectively no buddy)
    #   pipe   -> single column of '|' (4 rows)
    #   block  -> 2x2 solid block (uniform rectangle, no spaces)
    # Delete the file to restore the real buddy.
    # NOTE: this mutates the global SPECIES dict in-place with a finally-restore.
    # statusline.py runs in a single-threaded subprocess per render, so this is
    # safe in practice — do NOT call render_line() concurrently from threads.
    # Use ~/.claude/buddy/.debug_buddy (matches README), not the script dir —
    # keeps the contract stable for non-standard install paths or symlinks.
    _dbg_path = str(Path.home() / ".claude" / "buddy" / ".debug_buddy")
    try:
        with open(_dbg_path) as _f:
            _dbg = _f.read().strip()
    except Exception:
        _dbg = None
    _orig_art = None
    if _dbg in ("none", "pipe", "block"):
        _orig_art = SPECIES[pet["species"]]["art"]
        SPECIES[pet["species"]]["art"] = {
            "none":  [" "],
            "pipe":  ["|", "|", "|", "|"],
            "block": ["##", "##", "##", "##"],
        }[_dbg]
    try:
        world = adventure.render_world(sv, pet, width=width)
    finally:
        if _orig_art is not None:
            SPECIES[pet["species"]]["art"] = _orig_art

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

    n = len(sv["pets"])
    extra = core.c("  +%d pets" % (n - 1), "white") if n > 1 else ""

    info = "  %s  %s  %s  %s  %s%s" % (
        core.name_tag(pet),
        core.c("Lvl %d" % pet["level"], lc),
        core.c(core.xp_bar(pet, 12), lc),
        core.c("%d foes" % st.get("kills", 0), "white"),
        event,
        extra,
    )

    return "\n".join([world, info])


def main():
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
    pet = core.active_pet(sv)

    try:
        st = os.stat(transcript) if transcript else None
        mtime = st.st_mtime if st else 0
        size = st.st_size if st else 0
    except Exception:
        mtime, size = 0, 0

    wm = sv.setdefault("watermarks", {})
    entry = wm.get(session_id)
    unchanged = entry and entry.get("mtime") == mtime and entry.get("size") == size

    if transcript and not unchanged:
        total = count_tokens(transcript)
        prev = entry.get("tokens", 0) if entry else 0
        delta = max(0, total - prev)
        if delta:
            core.apply_xp(sv, pet, delta)
        wm[session_id] = {"mtime": mtime, "size": size, "tokens": total}
        if len(wm) > 30:
            for sid in sorted(wm, key=lambda s: wm[s].get("mtime", 0))[:-30]:
                del wm[sid]

    # walk the adventure forward every render (and tick combat if mid-fight)
    import adventure
    adventure.advance(sv, pet)
    core.save(sv)

    sys.stdout.write(render_line(sv, pet, _term_width(inp)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # a broken status line is worse than a boring one
        try:
            import core
            sv = core.load()
            core.ensure_first_pet(sv)
            sys.stdout.write(core.mini_face(core.active_pet(sv)) + " buddy")
        except Exception:
            sys.stdout.write("buddy")
