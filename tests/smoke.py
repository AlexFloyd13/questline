"""Smoke tests for buddy.

Run with:  python3 -m unittest tests.smoke -v

Every test isolates state via a tempdir, so they don't touch your real
~/.claude/buddy/save.json. No external dependencies — pure stdlib.

These tests aren't comprehensive — they're a guardrail against the most
embarrassing kinds of regression: render crashes, save corruption, and
input-handling holes."""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

# Make the project importable when tests are run from the repo root.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import core             # noqa: E402
import statusline       # noqa: E402

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _run_status(stdin_json: str = "{}", save_state: dict | None = None) -> str:
    """Invoke statusline.main() against a temp save and return the rendered
    string (still ANSI-coded). Safe to call repeatedly; each call uses a
    fresh tempdir."""
    tmpdir = tempfile.mkdtemp()
    core.SAVE_PATH = Path(tmpdir) / "save.json"
    if save_state is not None:
        core.SAVE_PATH.write_text(json.dumps(save_state))
    saved_stdin, saved_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(stdin_json)
    buf = io.StringIO()
    sys.stdout = buf
    try:
        statusline.main()
    finally:
        sys.stdin, sys.stdout = saved_stdin, saved_stdout
    return buf.getvalue()


def _minimal_pet(level: int = 1) -> dict:
    return {
        "id": "p1", "name": "Test", "species": "duck",
        "rarity": "Common", "shiny": False, "eyes": "o",
        "base_stats":   {s: 50 for s in core.STATS},
        "earned_stats": {s: 0 for s in core.STATS},
        "level": level, "xp": 0, "total_tokens": 0,
        "equipped_hat": None,
        "wins": 0, "losses": 0, "hatched_at": "2026-01-01",
    }


class StatusLineSmoke(unittest.TestCase):

    def test_brand_new_user_no_save(self):
        """First-ever run: no save file exists. Should hatch a starter pet
        and render a full status line, not crash."""
        out = _run_status()
        self.assertGreater(len(out), 0)
        self.assertIn("Lvl 1", _ANSI.sub("", out))

    def test_missing_transcript_field(self):
        """Hook payload without `transcript_path` shouldn't break anything."""
        out = _run_status('{"session_id": "test-abc"}')
        self.assertGreater(len(out), 0)

    def test_malicious_transcript_path(self):
        """Payload pointing at /etc/passwd must be silently rejected by
        the path-traversal guard; render should still succeed."""
        out = _run_status('{"transcript_path": "/etc/passwd", "session_id": "x"}')
        self.assertGreater(len(out), 0)

    def test_corrupted_save_wrong_types(self):
        """Hand-edited save with wrong-type fields shouldn't crash —
        core.load() normalizes them defensively."""
        out = _run_status(save_state={"version": 2, "pets": "broken",
                                      "inventory": "also broken"})
        self.assertGreater(len(out), 0)

    def test_empty_save(self):
        """An empty `{}` is treated as a fresh save."""
        out = _run_status(save_state={})
        self.assertGreater(len(out), 0)

    def test_narrow_terminal(self):
        """40-col terminal should render the world without crashing.
        World rows may not fully fit, but they should not exceed width."""
        out = _run_status('{"width": 40}')
        for row in _ANSI.sub("", out).split("\n"):
            # info row can wrap; world rows must fit
            if row.startswith("|"):
                self.assertLessEqual(len(row), 50,
                    f"world row {row!r} too wide for 40-col terminal")

    def test_huge_buddy_col(self):
        """Walking the pet to world position 10 billion shouldn't overflow
        any int math (Python is arbitrary-precision, so this is mostly
        a check that no implicit assumption breaks)."""
        sv = {
            "version": 2, "pets": {"p1": _minimal_pet()},
            "active": "p1", "next_id": 2, "next_iid": 1,
            "inventory": [], "watermarks": {},
            "adventure": {"buddy_col": 10_000_000_000,
                          "encounter": None, "log": [],
                          "steps": 0, "kills": 0, "losses": 0},
        }
        out = _run_status(save_state=sv)
        self.assertGreater(len(out), 0)


class LoadDefenses(unittest.TestCase):
    """Targeted tests for core.load()'s defensive normalization."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        core.SAVE_PATH = Path(self._tmp) / "save.json"

    def test_missing_version_treated_as_fresh(self):
        core.SAVE_PATH.write_text(json.dumps({"pets": {}}))
        sv = core.load()
        self.assertEqual(sv["version"], 2)
        self.assertEqual(sv["pets"], {})

    def test_wrong_version_treated_as_fresh(self):
        for v in (1, "two", None, [], {}):
            core.SAVE_PATH.write_text(json.dumps({"version": v}))
            sv = core.load()
            self.assertEqual(sv["version"], 2)
            self.assertEqual(sv["pets"], {})

    def test_wrong_type_pets_normalized(self):
        core.SAVE_PATH.write_text(json.dumps({"version": 2, "pets": "boom"}))
        sv = core.load()
        self.assertIsInstance(sv["pets"], dict)

    def test_wrong_type_inventory_normalized(self):
        core.SAVE_PATH.write_text(json.dumps({"version": 2, "inventory": "boom"}))
        sv = core.load()
        self.assertIsInstance(sv["inventory"], list)

    def test_missing_keys_filled_in(self):
        core.SAVE_PATH.write_text(json.dumps({"version": 2}))
        sv = core.load()
        for key in ("pets", "inventory", "watermarks",
                    "next_id", "next_iid", "active"):
            self.assertIn(key, sv)


class PathTraversalGuard(unittest.TestCase):
    """statusline._safe_transcript() must reject paths outside ~/.claude."""

    def test_rejects_absolute_system_path(self):
        self.assertIsNone(statusline._safe_transcript("/etc/passwd"))

    def test_rejects_relative_traversal(self):
        self.assertIsNone(statusline._safe_transcript("../../../etc/passwd"))

    def test_rejects_home_ssh(self):
        ssh = str(Path.home() / ".ssh" / "id_rsa")
        self.assertIsNone(statusline._safe_transcript(ssh))

    def test_rejects_empty(self):
        self.assertIsNone(statusline._safe_transcript(""))
        self.assertIsNone(statusline._safe_transcript(None))

    def test_accepts_under_claude_root(self):
        legit = str(Path.home() / ".claude" / "projects" / "abc.jsonl")
        self.assertEqual(statusline._safe_transcript(legit), legit)


if __name__ == "__main__":
    unittest.main()
