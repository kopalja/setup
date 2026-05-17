#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ZSH_DIR="$HOME/.oh-my-zsh"
ZSH_CUSTOM="${ZSH_CUSTOM:-$ZSH_DIR/custom}"
BACKUP_DIR="$HOME/.setup-backups/$(date +%Y%m%d-%H%M%S)"

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'error: missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

backup_file() {
  local path="$1"

  if [ -e "$path" ] || [ -L "$path" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -R "$path" "$BACKUP_DIR/"
    log "Backed up $path to $BACKUP_DIR/"
  fi
}

install_or_update_git_repo() {
  local repo_url="$1"
  local dest="$2"
  local clone_args="${3:-}"

  if [ -d "$dest/.git" ]; then
    log "Updating $dest"
    git -C "$dest" pull --ff-only
  elif [ -e "$dest" ]; then
    printf 'error: %s exists but is not a git repository\n' "$dest" >&2
    exit 1
  else
    log "Cloning $repo_url into $dest"
    mkdir -p "$(dirname "$dest")"
    # shellcheck disable=SC2086
    git clone $clone_args "$repo_url" "$dest"
  fi
}

require_cmd curl
require_cmd git
require_cmd zsh

zsh_path="$(command -v zsh)"
if [ -r /etc/shells ] && ! grep -Fxq "$zsh_path" /etc/shells; then
  warn "$zsh_path is not listed in /etc/shells; skipping chsh"
elif [ "${SHELL:-}" != "$zsh_path" ]; then
  if chsh -s "$zsh_path"; then
    log "Changed login shell to $zsh_path"
  else
    warn "Could not change login shell to $zsh_path"
  fi
fi

if [ ! -d "$ZSH_DIR" ]; then
  RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" || {
    printf 'error: could not install Oh My Zsh\n' >&2
    exit 1
  }
else
  log "Oh My Zsh already installed at $ZSH_DIR"
fi

install_or_update_git_repo \
  "https://github.com/zsh-users/zsh-autosuggestions" \
  "$ZSH_CUSTOM/plugins/zsh-autosuggestions"

install_or_update_git_repo \
  "https://github.com/romkatv/powerlevel10k.git" \
  "$ZSH_CUSTOM/themes/powerlevel10k" \
  "--depth=1"

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

PUB_KEY="${SETUP_AUTHORIZED_KEY:-ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDTjSg9RvkVDdv3sw4PI6RT5fYviMGN5qXfX7dAMxYFJMW3fRSb/mTTqRAjlY4m0tYkyWicOATzTEyJEMOTh6EDLnEXLu+yBOuXX2FGGBeDyxc0qBOAuk8ujpFiFjRZiX5hzjF1g6xV0r+kIf1qNBtCAjzpi+pyasf+k5VwLcqc8D7RxndKx+YaukbWVByXyTuqS8JX9L2GpPlaGAfKNTQet/bL/G+j97dINk5ZzktrtGaJ9Jy70TT4Kf8qZGZPJ0Qc6AnmCwpDGhMJ+EZXFjZRAh8mg1MKZDkhtJnqx0Xul0XFXdZyLnvb5Ks6fNGcUyHM7t9xNXsn0WR+abejsEtmQsp8y1th7oIAnTVWkrUUjzvpEcd3Bk54x+D2PsSYcmvuH7bcJ1kODBTqDRITTs8KbUl8suSOr9n6FZOuXi1fv9+P/f3o1NDQgbRA92t/7Hm4B44eGuYifxjTUOWe8icl7z2ij8cvMQKb+dzOrIeScS+6g66aPDIHY2HiTQxPqzs= kopi@xps}"
touch "$HOME/.ssh/authorized_keys"
if ! grep -Fxq "$PUB_KEY" "$HOME/.ssh/authorized_keys"; then
  printf '%s\n' "$PUB_KEY" >>"$HOME/.ssh/authorized_keys"
fi
chmod 600 "$HOME/.ssh/authorized_keys"

backup_file "$HOME/.zshrc"
backup_file "$HOME/.vimrc"
backup_file "$HOME/.tmux.conf"

cp "$SCRIPT_DIR/zshrc" "$HOME/.zshrc"
cp "$SCRIPT_DIR/vimrc" "$HOME/.vimrc"
cp "$SCRIPT_DIR/tmux.conf" "$HOME/.tmux.conf"

log "Terminal setup complete"
