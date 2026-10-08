import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZSHRC = (ROOT / "zshrc").read_text()
CWT = "cwt() {" + ZSHRC.split("cwt() {", 1)[1].split("\ncwt-discard()", 1)[0]


class CwtTest(unittest.TestCase):
    def test_copies_only_root_hidden_files_and_enters_worktree(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()

            def git(*args: str) -> None:
                subprocess.run(["git", "-C", str(repo), *args], check=True,
                               capture_output=True)

            git("init")
            (repo / ".gitignore").write_text(".env\n.secrets/\n")
            (repo / ".tracked").write_text("committed")
            git("add", ".")
            git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                "commit", "-m", "initial")
            (repo / ".tracked").write_text("local modification")
            files = {
                ".env": "environment",
                ".secrets/token": "secret",
                "nested/.env local": "nested",
                ".name\nwith newline": "newline",
                "plain.txt": "excluded",
                "AGENTS.md": "instructions",
            }
            for name, content in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            (repo / ".env-link").symlink_to(".env")
            (repo / ".directory-link").symlink_to(".secrets", target_is_directory=True)
            (repo / ".empty-directory").mkdir()
            worktrees = base / "worktrees"
            script = CWT + '\ncodex() { exit 99; }\ncwt feature/test || exit $?\npwd\n'
            result = subprocess.run(
                ["zsh", "-f", "-c", script], cwd=repo,
                env={**os.environ, "CODEX_WORKTREE_ROOT": str(worktrees)},
                check=True, capture_output=True, text=True,
            )
            worktree = worktrees / "repo" / "feature-test"
            self.assertEqual(Path(result.stdout.strip().splitlines()[-1]), worktree)
            for name, content in files.items():
                if name.startswith(".") and "/" not in name or name == "AGENTS.md":
                    self.assertEqual((worktree / name).read_text(), content)
                else:
                    self.assertFalse((worktree / name).exists())
            for name in (".secrets", "nested", ".directory-link", ".empty-directory"):
                self.assertFalse((worktree / name).exists())
            self.assertEqual((worktree / ".tracked").read_text(), "committed")
            self.assertTrue((worktree / ".env-link").is_symlink())

    def test_rejects_missing_or_extra_arguments(self) -> None:
        for arguments in ("", "''", "branch astra"):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["zsh", "-f", "-c", CWT + "\ncwt " + arguments],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("Usage: cwt <branch-name>", result.stdout)


if __name__ == "__main__":
    unittest.main()
