import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
ZSH_CONFIG = (REPO / "zshrc").read_text()
FUZZY_CONFIG = ZSH_CONFIG.split("# ===Fuzzy file and folde search")[1].split(
    "fuzzy-content-open()"
)[0].split("\n", 1)[1]
VIM_CONFIG = (REPO / "vimrc").read_text().split(
    '" Share file visits with the shell'
)[1].split("augroup END", 1)[0].split("\n", 1)[1] + "augroup END\n"


class FuzzyHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.state = self.home / "state"
        self.history = self.state / "fuzzy-open/history"
        self.environment = dict(os.environ, HOME=str(self.home), XDG_STATE_HOME=str(self.state))

    def shell(self, command: str) -> str:
        return subprocess.run(
            ["zsh", "-f", "-c", "zle() { :; };\n" + FUZZY_CONFIG + command],
            env=self.environment, cwd=self.home, check=True, text=True,
            capture_output=True,
        ).stdout

    def test_recent_unique_existing_paths_before_other_candidates(self) -> None:
        first = self.home / "first file"
        second = self.home / "second"
        other = self.home / "other"
        for path in (first, second, other):
            path.touch()
        skipped = self.home / "node_modules"
        skipped.mkdir()
        (skipped / "dependency").touch()
        self.history.parent.mkdir(parents=True)
        self.history.write_text(f"{first}\n{second}\n{self.home / 'missing'}\n{first}\n")
        paths = self.shell("fuzzy-open-candidates | awk '!seen[$0]++'").splitlines()
        self.assertEqual(paths[:3], [str(self.home), str(first), str(second)])
        self.assertEqual(paths.count(str(first)), 1)
        self.assertIn(str(other), paths)
        self.assertNotIn(str(self.home / "missing"), paths)
        self.assertNotIn(str(skipped), paths)
        filtered = subprocess.run(
            ["fzf", "--no-sort", "--filter", "file"], input="\n".join(paths),
            text=True, capture_output=True, check=True,
        ).stdout.splitlines()
        self.assertEqual(filtered, [str(first)])

    def test_directory_visits_persist_across_shells(self) -> None:
        directory = self.home / "visited directory"
        directory.mkdir()
        self.shell('cd -- "$HOME/visited directory"')
        self.assertEqual(self.history.read_text().splitlines()[-1], str(directory))
        paths = self.shell("fuzzy-open-candidates | awk '!seen[$0]++'").splitlines()
        self.assertEqual(paths[:2], [str(self.home), str(directory)])

    def test_vim_records_buffer_visits_in_shared_history(self) -> None:
        first = self.home / "first file"
        second = self.home / "second"
        first.touch()
        second.touch()
        script = self.home / "test.vim"
        script.write_text(VIM_CONFIG + '\nedit ' + str(first) + '\nedit ' + str(second)
                          + '\nbuffer ' + str(first) + '\nqa!\n')
        subprocess.run(
            ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", str(script)],
            env=self.environment, check=True, capture_output=True,
        )
        self.assertEqual(self.history.read_text().splitlines(),
                         [str(first), str(second), str(first)])


if __name__ == "__main__":
    unittest.main()
