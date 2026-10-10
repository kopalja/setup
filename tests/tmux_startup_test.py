"""Check popup input and disconnect persistence with a real tmux client."""

import fcntl
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import tempfile
import termios
import time
from typing import Callable
import unittest


class StartupTest(unittest.TestCase):
    def test_tab_popup_and_disconnect(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix=".tmux-startup-", dir=repo) as tmp:
            directory = Path(tmp)
            socket = str(directory / "socket")
            env = dict(os.environ, TERM="xterm-256color")
            env.pop("TMUX", None)

            def tmux(*args: str) -> str:
                return subprocess.check_output(
                    ["tmux", "-S", socket, *args], env=env, text=True
                ).strip()

            def wait_for(predicate: Callable[[], bool]) -> None:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if predicate():
                        return
                    time.sleep(0.02)
                self.fail("timed out waiting for tmux")

            master, slave = os.openpty()
            client: subprocess.Popen[bytes] | None = None
            try:
                received = directory / "input"
                tmux("-f", "/dev/null", "new-session", "-d", "-s", "test",
                     f"stty raw -echo; cat > {shlex.quote(str(received))}")
                # Reload must remove the old C-i/Tab binding too.
                tmux("bind-key", "-n", "C-i", "display-popup")
                tmux("bind-key", "-n", "Tab", "display-popup")
                tmux("source-file", str(repo / "tmux.conf"))
                tmux("set-option", "-g", "status-right", "")
                self.assertEqual(tmux("show-option", "-gv", "default-shell"),
                                 shutil.which("zsh"))
                self.assertEqual(tmux("show-option", "-gv", "destroy-unattached"), "off")
                self.assertEqual(tmux("show-option", "-sv", "exit-unattached"), "off")
                bindings = tmux("list-keys", "-T", "root")
                self.assertFalse(any(shlex.split(line)[3] == "Tab"
                                     for line in bindings.splitlines()))
                self.assertIn("display-popup", tmux("list-keys", "-T", "root", "User0"))

                # The actual popup runs this shell; the existing pane keeps cat.
                marker = directory / "popup-opened"
                popup_shell = directory / "popup-shell"
                popup_shell.write_text(
                    f"#!/bin/sh\ntouch {shlex.quote(str(marker))}\nexec sleep 30\n"
                )
                popup_shell.chmod(0o755)
                tmux("set-option", "-g", "default-shell", str(popup_shell))
                pane_pid = tmux("display-message", "-p", "#{pane_pid}")
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
                client = subprocess.Popen(
                    ["tmux", "-S", socket, "attach-session", "-t", "test"],
                    stdin=slave, stdout=slave, stderr=slave, env=env,
                )
                os.close(slave)
                slave = -1
                wait_for(lambda: bool(tmux("list-clients")))
                wait_for(received.exists)
                os.write(master, b"\t")
                wait_for(lambda: received.read_bytes() == b"\t")
                self.assertFalse(marker.exists(), "Tab must not open the popup")
                os.write(master, b"\x1b[99~")
                wait_for(marker.exists)

                os.close(master)
                master = -1
                client.wait(timeout=5)
                self.assertEqual(tmux("display-message", "-p", "#{pane_pid}"), pane_pid)
                self.assertEqual(tmux("list-clients"), "")
                self.assertEqual(tmux("display-message", "-p", "#{session_name}"), "test")
            finally:
                if client is not None and client.poll() is None:
                    client.terminate()
                    client.wait(timeout=5)
                for fd in (master, slave):
                    if fd >= 0:
                        os.close(fd)
                subprocess.run(["tmux", "-S", socket, "kill-server"],
                               env=env, capture_output=True)


if __name__ == "__main__":
    unittest.main()
