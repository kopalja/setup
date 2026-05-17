# Terminal VM setup

Bootstrap personal shell, Vim, and tmux defaults on a new VM.

## Prerequisites

Install these before running the setup:

- `bash`
- `curl`
- `git`
- `zsh`
- `vim` or `nvim`
- `tmux`
- `xsel`, `xclip`, or `pbcopy` for tmux clipboard integration

## Usage

```sh
./init.sh
```

The script is safe to rerun. Existing `~/.zshrc`, `~/.vimrc`, and `~/.tmux.conf`
files are backed up under `~/.setup-backups/` before being replaced.

To install a different SSH public key into `authorized_keys`, pass it with:

```sh
SETUP_AUTHORIZED_KEY='ssh-rsa ... user@host' ./init.sh
```
