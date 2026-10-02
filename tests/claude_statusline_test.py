"""Check the Claude Code status line output."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "claude-statusline"


def status(payload):
    out = subprocess.run([str(SCRIPT)], input=json.dumps(payload),
                         check=True, capture_output=True, text=True).stdout
    return re.sub(r"\x1b\[[0-9;]*m", "", out).strip()


class StatusLineTest(unittest.TestCase):
    def test_git_dir_with_effort(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            subprocess.run(["git", "init", "-q", "-b", "feat", tmp], check=True)
            self.assertEqual(status({
                "workspace": {"current_dir": tmp},
                "model": {"display_name": "Opus 5.5"},
                "effort": {"level": "high"},
                "context_window": {"used_percentage": 42.6},
            }), f"~/{Path(tmp).name} · feat · Opus 5.5 high · Context 43% used")

    def test_plain_dir_before_first_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(status({
                "workspace": {"current_dir": tmp},
                "model": {"display_name": "Haiku 4.5"},
                "context_window": {"used_percentage": None},
            }), f"{tmp} · Haiku 4.5 · Context 0% used")


if __name__ == "__main__":
    unittest.main()
