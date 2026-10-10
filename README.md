# Terminal VM setup

Bootstrap personal shell, Vim, and tmux defaults on a Debian-family Linux
machine reached over SSH. Raspberry Pi OS is supported.

## Prerequisites

Install the required packages before running the setup (`bat` adds highlighted
file previews):

```sh
sudo apt install ca-certificates curl git zsh vim tmux tar fzf bat ripgrep jq
```

Prerequisites:

- `bash`, `curl`, `git`, `zsh`, `vim`, `tmux`, `tar`
- `fzf` 0.48 or newer
- `rg` (ripgrep, for file content search)
- `jq` (for the Claude Code status line)
- `bat` (optional, for highlighted previews)
- `codex` and `claude` (optional)

The fuzzy picker needs `fzf` 0.48 or newer. Debian 12
[packages 0.38](https://packages.debian.org/bookworm/utils/fzf), so install a
newer [fzf release](https://github.com/junegunn/fzf/releases) on that system.
The script reports missing commands together and does not use `sudo` or a package
manager.

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
The Zsh `codex` wrapper automatically trusts the launch directory (including
`-C` / `--cd` targets), so folder-access prompts do not recur after setup
replaces the config. This applies to every folder launched through the wrapper
and the `c1`–`c4`, `cl`, and `cwt` shortcuts: folder settings may run code
automatically. Open a new shell after setup to load the wrapper.
If the `claude` command exists, `claude_config.json` is installed as
`~/.claude/settings.json` and `_CLAUDE.md` as `~/.claude/CLAUDE.md`, with the
same backup behavior.

## Shared agent skills

Put each skill in `skills/<skill-name>/SKILL.md`. Setup installs each skill for
Codex at `~/.codex/skills/<skill-name>/` and for Claude Code at
`~/.claude/skills/<skill-name>/` when the corresponding CLI is available.
Changed skill directories are backed up under `~/.setup-backups/` before they
are replaced. Keep shared skills provider-neutral so the same instructions
work in both CLIs.

A skill is a short workflow guide. Its YAML front matter supplies a `name` and
a `description`; the description should say what the skill does and when to
use it. Put the step-by-step instructions in the Markdown body. Supporting
files such as scripts, references, and templates can live next to `SKILL.md`.
For example, see `skills/setup-maintenance/SKILL.md`.

```markdown
---
name: my-workflow
description: Do a specific task and when to use this workflow.
---

Explain the steps to follow, what to check, and what the result should include.
```

To make a skill explicit-only (never picked automatically), add
`disable-model-invocation: true` to its front matter for Claude Code and an
`agents/openai.yaml` with `policy: allow_implicit_invocation: false` for Codex.
Otherwise, skills can be selected automatically from matching requests; for
example, "Fix this bug and then babysit" triggers `skills/babysit/` after the fix.

Commit the skill directory to share it with this repository's users. Run
`./deploy-skills` to install or refresh only the skills; `./init` (or
`./init.sh`) also installs them as part of the full setup. Codex and Claude
Code discover user skills from their respective skill directories.

Setup also copies `tmux-codex-status`, `tmux-next-ready`, and `claude-statusline`
into `~/.local/bin/` and makes them executable, with the same backup behavior.
`claude-statusline` (requires `jq`) is the Claude Code status line: current dir,
Git branch, model with reasoning effort, and context used, like Codex's.
The tmux status bar shows a rotating half-filled circle on muted working tabs,
a gold selected tab and hostname, and green completed tabs;
prefix + `r` selects the next green tab. This uses Codex's spinner-prefixed
pane titles and requires no GUI or Codex `notify` setting. The terminal font
must support Powerline separators. Codex versions that emit different pane
titles may require updating the detection in `tmux.conf`.
Claude Code tabs behave the same way: the hooks in `claude_config.json` set
the `@claude-working` tmux pane option (1 while working, 0 when done or
waiting for input). Claude Code shows its session topic as the tab title.

Setup reloads the default tmux server if it is already running. To manually
reload after editing the configuration:

```sh
tmux source-file ~/.tmux.conf
```

Setup also adds an interactive SSH-only Zsh fallback to `~/.bashrc` and the
active Bash login profile (`~/.bash_profile`, `~/.bash_login`, or `~/.profile`),
preserving existing content and backing up changed files. This handles accounts
where `chsh` cannot change the login shell. Zsh attaches to an existing tmux
session or creates one; new tmux panes use Zsh.

Leave work running by detaching with `Ctrl+B`, then `d`, before logging out.
Running `exit` in the last pane closes the session. Sessions survive SSH
disconnects, but not a reboot. Hosts configured with `KillUserProcesses=yes`
also kill tmux on logout; ask the administrator for a permitted persistence
exception (particularly on Slurm hosts). Tmux settings cannot override that
host policy. Setup checks the logind configuration when `systemd-analyze` is
available and reports this setting; it does not change system policy.

For the popup shortcut, add this to your **local Ghostty configuration** and
reload Ghostty's configuration:

```ini
keybind = ctrl+i=text:\x1b[99~
```

This sends a distinct sequence for Ctrl+I; Tab remains available for completion,
including with older tmux versions. `Ctrl+B`, then `g`, also opens the popup.

To install a different SSH public key into `authorized_keys`, pass it with:

```sh
SETUP_AUTHORIZED_KEY='ssh-rsa ... user@host' ./init.sh
```

Existing authorized keys are preserved, and the configured key is added only
once.

## Tests

```sh
bash tests/init_test.sh
python3 tests/tmux_startup_test.py
python3 tests/tmux_status_test.py
python3 tests/claude_statusline_test.py
```

The tests use temporary home directories and command adapters; they do not
change the real home directory, login shell, dependencies, or Git checkouts.
The tmux status tests require Python 3 and tmux and use an isolated tmux server.
