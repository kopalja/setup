"""Exercise completion tracking in an isolated tmux server."""
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import time
import unittest


class CompletionTest(unittest.TestCase):
    def test_completion_and_acknowledgement(self):
        home = Path.home()
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="tmux-test-", dir=home) as tmp:
            socket = str(Path(tmp) / "socket")
            env = {k: v for k, v in os.environ.items() if k != "TMUX"}

            def tmux(*args):
                return subprocess.check_output(
                    ["tmux", "-S", socket, *args], env=env, text=True
                ).strip()

            def tick():
                subprocess.run(
                    [str(repo / "tmux-codex-status"), socket],
                    env=env, check=True, capture_output=True, text=True,
                )

            def value(fmt):
                return tmux("display-message", "-p", "-t", window, fmt)

            def title(text):
                tmux("select-pane", "-t", window, "-T", text)
                tick()

            shutil.copy("/bin/sleep", Path(tmp) / "codex")
            try:
                tmux("-f", "/dev/null", "new-session", "-d", "-s", "test")
                tmux("source-file", str(repo / "tmux.conf"))
                tmux("set-option", "-g", "status-right", "")
                tmux("set-option", "-g", "remain-on-exit", "on")
                window = tmux("new-window", "-d", "-P", "-F", "#{window_id}",
                              str(Path(tmp) / "codex") + " 120")
                for _ in range(100):
                    if value("#{pane_current_command}") == "codex":
                        break
                    time.sleep(0.02)
                self.assertEqual(value("#{pane_current_command}"), "codex",
                                 tmux("capture-pane", "-p", "-t", window))

                title("Session title")
                self.assertEqual(value("#{?@codex-finished,1,0}"), "0")
                title("⠋ Session title")
                self.assertEqual(value("#{@codex-was-working}"), "1")
                self.assertEqual(value("#{E:@tab-bg}"), "#654b70")
                self.assertEqual(value("#{E:@active-tab-bg}"), "#ffbf00")
                self.assertNotIn("◐", value("#{E:@tab-number}"))
                for frame, dot in enumerate(("◐", "◓", "◑", "◒")):
                    tmux("set-option", "-g", "@codex-pulse-frame", str(frame))
                    self.assertEqual(value("#{E:@tab-title}"), dot + " Session title")
                # The title stops spinning before the polling helper runs.
                tmux("select-pane", "-t", window, "-T", "Session title")
                self.assertEqual(value("#{E:@tab-bg}"), "#3e6150")
                tick()
                self.assertEqual(value("#{@codex-finished}"), "1")
                self.assertEqual(value("#{E:@tab-bg}"), "#3e6150")
                tick()
                self.assertEqual(value("#{@codex-finished}"), "1")

                # Selection must acknowledge completion immediately via the hook.
                tmux("select-window", "-t", window)
                self.assertEqual(value("#{@codex-finished}"), "0")
                tmux("select-window", "-t", "test:0")
                tick()
                self.assertEqual(value("#{@codex-finished}"), "0")

                title("⠙ Session title")
                title("Session title")
                self.assertEqual(value("#{@codex-finished}"), "1")
                title("⠹ Session title")
                self.assertEqual(value("#{@codex-finished}"), "0")

                # Finishing in the selected window should not leave an alert.
                tmux("select-window", "-t", window)
                title("Session title")
                self.assertEqual(value("#{@codex-finished}"), "0")

                tmux("select-window", "-t", "test:0")
                title("⠋ Session title")
                title("Session title")
                tmux("next-window", "-t", "test")
                self.assertEqual(value("#{@codex-finished}"), "0")

                def jump():
                    binding = next(line for line in (repo / "tmux.conf").read_text().splitlines()
                                   if line.startswith("bind-key r run-shell "))
                    tmux("run-shell", "-t", "test:", shlex.split(binding)[3].replace("$HOME/.local/bin/tmux-next-ready", str(repo / "tmux-next-ready")))

                def selected():
                    return tmux("display-message", "-p", "-t", "test:", "#{window_id}")

                first = tmux("display-message", "-p", "-t", "test:0", "#{window_id}")
                last = tmux("new-window", "-d", "-P", "-F", "#{window_id}")
                tmux("set-option", "-w", "-t", first, "@codex-finished", "1")
                tmux("set-option", "-w", "-t", last, "@codex-finished", "1")
                jump()
                self.assertEqual(selected(), last)
                self.assertEqual(tmux("show-option", "-wqv", "-t", last, "@codex-finished"), "0")
                jump()
                self.assertEqual(selected(), first)  # Wrap around.
                jump()
                self.assertEqual(selected(), first)  # No ready windows: stay put.

                # A freshly stopped spinner is green before the next poll.
                tmux("set-option", "-w", "-t", window, "@codex-was-working", "1")
                jump()
                self.assertEqual(selected(), window)
                self.assertEqual(value("#{@codex-was-working}"), "0")

                # Ready windows in other sessions must not be selected.
                tmux("new-session", "-d", "-s", "other")
                tmux("set-option", "-w", "-t", "other:", "@codex-finished", "1")
                jump()
                self.assertEqual(selected(), window)
            finally:
                subprocess.run(["tmux", "-S", socket, "kill-server"], env=env,
                               capture_output=True)


if __name__ == "__main__":
    unittest.main()
