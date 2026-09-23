# Terminal VM setup

Bootstrap personal shell, Vim, and tmux defaults on a Debian-family Linux
machine reached over SSH. Raspberry Pi OS is supported.

## Prerequisites

Install these before running the setup. The script reports every missing command
together and does not attempt to use `sudo` or a package manager.

- `bash`
- `curl`
- `git`
- `zsh`
- `vim`
- `tmux`
- `tar`
- `codex` (optional)
- `claude` (optional)

## Usage

```sh
./init.sh
```

`./init` is an equivalent entry point (including `./init --update`).

An ordinary Setup run installs missing Oh My Zsh plus Zsh and Vim plugins. It
does not update dependencies that are already installed. Vim and Zsh startup
never download, install, or update dependencies.

To explicitly update dependencies, run:

```sh
./init.sh --update
```

An Update run stops rather than overwrite a dependency checkout with local
changes or diverged commits.

The script is safe to rerun. An unchanged `~/.zshrc`, `~/.vimrc`, or
`~/.tmux.conf` is left untouched. A changed file or symlink is backed up under
`~/.setup-backups/` and replaced atomically with an independent copy.
Setup installs missing Codex (latest GitHub release binary) and Claude Code
(native installer) into `~/.local/bin/`. An Update run runs `claude update` and
refreshes Codex if it lives in `~/.local/bin/`.
If the `codex` command exists, `codex_config.toml` is installed as
`~/.codex/config.toml`. `_AGENTS.md` is also installed as
`~/.codex/AGENTS.md`, with the same backup behavior.
If the `claude` command exists, `claude_config.json` is installed as
`~/.claude/settings.json` and `_CLAUDE.md` as `~/.claude/CLAUDE.md`, with the
same backup behavior.

Setup also copies `tmux-codex-status` and `tmux-next-ready` into
`~/.local/bin/` and makes them executable, with the same backup behavior.
The tmux status bar shows a rotating half-filled circle on muted working tabs,
a gold selected tab and hostname, and green completed tabs;
prefix + `r` selects the next green tab. This uses Codex's spinner-prefixed
pane titles and requires no GUI or Codex `notify` setting. The terminal font
must support Powerline separators. Codex versions that emit different pane
titles may require updating the detection in `tmux.conf`.

For an already-running tmux server, reload after setup:

```sh
tmux source-file ~/.tmux.conf
```

To install a different SSH public key into `authorized_keys`, pass it with:

```sh
SETUP_AUTHORIZED_KEY='ssh-rsa ... user@host' ./init.sh
```

Existing authorized keys are preserved, and the configured key is added only
once.

## Tests

```sh
bash tests/init_test.sh
python3 tests/tmux_status_test.py
```

The tests use temporary home directories and command adapters; they do not
change the real home directory, login shell, dependencies, or Git checkouts.
The tmux status tests require Python 3 and tmux and use an isolated tmux server.
