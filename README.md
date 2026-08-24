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

## Usage

```sh
./init.sh
```

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
If `~/.codex` exists, `_AGENTS.md` is installed as `~/.codex/AGENTS.md` with
the same backup behavior.

To install a different SSH public key into `authorized_keys`, pass it with:

```sh
SETUP_AUTHORIZED_KEY='ssh-rsa ... user@host' ./init.sh
```

Existing authorized keys are preserved, and the configured key is added only
once.

## Tests

```sh
bash tests/init_test.sh
```

The tests use temporary home directories and command adapters; they do not
change the real home directory, login shell, dependencies, or Git checkouts.
