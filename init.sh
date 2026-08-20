#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

UPDATE=false
if (($# > 1)); then
  printf 'error: usage: %s [--update]\n' "$0" >&2
  exit 2
elif (($# == 1)); then
  if [ "$1" != "--update" ]; then
    printf 'error: unknown option: %s\n' "$1" >&2
    printf 'usage: %s [--update]\n' "$0" >&2
    exit 2
  fi
  UPDATE=true
fi

check_prerequisites() {
  local command_name
  local -a missing=()

  for command_name in curl git zsh vim tmux; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      missing+=("$command_name")
    fi
  done

  if ((${#missing[@]} > 0)); then
    printf 'error: missing required commands:\n' >&2
    printf '  - %s\n' "${missing[@]}" >&2
    return 1
  fi
}

check_prerequisites

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ZSH_DIR="$HOME/.oh-my-zsh"
ZSH_CUSTOM="${ZSH_CUSTOM:-$ZSH_DIR/custom}"
BACKUP_DIR="$HOME/.setup-backups/$(date +%Y%m%d-%H%M%S)"

assert_git_repo_update_safe() {
  local dest="$1"
  local changes

  if [ ! -d "$dest/.git" ]; then
    printf 'error: dependency at %s is not a Git checkout; refusing to update\n' "$dest" >&2
    return 1
  fi

  changes="$(git -C "$dest" status --porcelain)"
  if [ -n "$changes" ]; then
    printf 'error: dependency at %s has local changes; refusing to update\n' "$dest" >&2
    return 1
  fi

  git -C "$dest" fetch --quiet
  if ! git -C "$dest" merge-base --is-ancestor HEAD '@{upstream}'; then
    printf 'error: dependency at %s has diverged; refusing to update\n' "$dest" >&2
    return 1
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

preserve_incomplete_dependency() {
  local path="$1"

  mkdir -p "$BACKUP_DIR"
  mv "$path" "$BACKUP_DIR/"
  log "Preserved incomplete dependency $path in $BACKUP_DIR/"
}

deploy_configuration() {
  local source="$1"
  local target="$2"
  local temporary

  if [ -f "$target" ] && [ ! -L "$target" ] && cmp -s "$source" "$target"; then
    log "Unchanged $target"
    return
  fi

  backup_file "$target"
  temporary="$(mktemp "${target}.tmp.XXXXXX")"
  if ! cp "$source" "$temporary"; then
    rm -f "$temporary"
    return 1
  fi
  if ! mv -f "$temporary" "$target"; then
    rm -f "$temporary"
    return 1
  fi
  log "Installed $target"
}

ensure_git_repo() {
  local repo_url="$1"
  local dest="$2"

  if [ -e "$dest" ] && [ ! -d "$dest/.git" ]; then
    preserve_incomplete_dependency "$dest"
  fi

  if [ -d "$dest/.git" ]; then
    if [ "$UPDATE" = true ]; then
      assert_git_repo_update_safe "$dest"
      log "Updating $dest"
      git -C "$dest" pull --ff-only
    else
      log "Dependency already installed at $dest"
    fi
  else
    log "Cloning $repo_url into $dest"
    mkdir -p "$(dirname "$dest")"
    git clone "$repo_url" "$dest"
  fi
}

ensure_vim_dependencies() {
  local vim_plug="$HOME/.vim/autoload/plug.vim"
  local plugin_dir
  local temporary
  local -a plugin_dirs=(
    "$HOME/.vim/plugged/gruvbox"
    "$HOME/.vim/plugged/vim-oscyank"
  )

  if [ -e "$vim_plug" ] && ! grep -Fq 'plug#begin' "$vim_plug"; then
    preserve_incomplete_dependency "$vim_plug"
  fi

  for plugin_dir in "${plugin_dirs[@]}"; do
    if [ -e "$plugin_dir" ] && [ ! -d "$plugin_dir/.git" ]; then
      preserve_incomplete_dependency "$plugin_dir"
    fi
  done

  if [ ! -f "$vim_plug" ]; then
    log "Installing vim-plug"
    mkdir -p "$(dirname "$vim_plug")"
    temporary="$(mktemp "${vim_plug}.tmp.XXXXXX")"
    if ! curl -fLo "$temporary" \
      "https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim"; then
      rm -f "$temporary"
      return 1
    fi
    mv -f "$temporary" "$vim_plug"
  else
    log "vim-plug already installed at $vim_plug"
  fi

  if [ "$UPDATE" = true ]; then
    for plugin_dir in "${plugin_dirs[@]}"; do
      if [ -e "$plugin_dir" ]; then
        assert_git_repo_update_safe "$plugin_dir"
      fi
    done

    vim -Nu "$SCRIPT_DIR/vimrc" -n -es -i NONE \
      -c 'PlugUpgrade' \
      -c 'PlugUpdate --sync' \
      -c 'qa'
  else
    vim -Nu "$SCRIPT_DIR/vimrc" -n -es -i NONE \
      -c 'PlugInstall --sync' \
      -c 'qa'
  fi
}

zsh_path="$(command -v zsh)"
if [ ! -r /etc/shells ]; then
  warn "cannot read /etc/shells; skipping chsh"
elif ! grep -Fxq "$zsh_path" /etc/shells; then
  warn "$zsh_path is not listed in /etc/shells; skipping chsh"
elif [ "${SHELL:-}" != "$zsh_path" ]; then
  if chsh -s "$zsh_path"; then
    log "Changed login shell to $zsh_path"
  else
    warn "Could not change login shell to $zsh_path"
  fi
fi

if [ -e "$ZSH_DIR" ] && { [ ! -d "$ZSH_DIR/.git" ] || [ ! -f "$ZSH_DIR/oh-my-zsh.sh" ]; }; then
  preserve_incomplete_dependency "$ZSH_DIR"
fi

if [ ! -d "$ZSH_DIR" ]; then
  RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c \
    "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" \
    "" --unattended || {
    printf 'error: could not install Oh My Zsh\n' >&2
    exit 1
  }
else
  if [ "$UPDATE" = true ]; then
    assert_git_repo_update_safe "$ZSH_DIR"
    if [ ! -x "$ZSH_DIR/tools/upgrade.sh" ]; then
      printf 'error: Oh My Zsh upgrade script is missing at %s\n' "$ZSH_DIR/tools/upgrade.sh" >&2
      exit 1
    fi
    log "Updating Oh My Zsh"
    "$ZSH_DIR/tools/upgrade.sh"
  else
    log "Oh My Zsh already installed at $ZSH_DIR"
  fi
fi

ensure_git_repo \
  "https://github.com/zsh-users/zsh-autosuggestions" \
  "$ZSH_CUSTOM/plugins/zsh-autosuggestions"

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

PUB_KEY="${SETUP_AUTHORIZED_KEY:-ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDTjSg9RvkVDdv3sw4PI6RT5fYviMGN5qXfX7dAMxYFJMW3fRSb/mTTqRAjlY4m0tYkyWicOATzTEyJEMOTh6EDLnEXLu+yBOuXX2FGGBeDyxc0qBOAuk8ujpFiFjRZiX5hzjF1g6xV0r+kIf1qNBtCAjzpi+pyasf+k5VwLcqc8D7RxndKx+YaukbWVByXyTuqS8JX9L2GpPlaGAfKNTQet/bL/G+j97dINk5ZzktrtGaJ9Jy70TT4Kf8qZGZPJ0Qc6AnmCwpDGhMJ+EZXFjZRAh8mg1MKZDkhtJnqx0Xul0XFXdZyLnvb5Ks6fNGcUyHM7t9xNXsn0WR+abejsEtmQsp8y1th7oIAnTVWkrUUjzvpEcd3Bk54x+D2PsSYcmvuH7bcJ1kODBTqDRITTs8KbUl8suSOr9n6FZOuXi1fv9+P/f3o1NDQgbRA92t/7Hm4B44eGuYifxjTUOWe8icl7z2ij8cvMQKb+dzOrIeScS+6g66aPDIHY2HiTQxPqzs= kopi@xps}"
touch "$HOME/.ssh/authorized_keys"
if ! grep -Fxq "$PUB_KEY" "$HOME/.ssh/authorized_keys"; then
  printf '%s\n' "$PUB_KEY" >>"$HOME/.ssh/authorized_keys"
fi
chmod 600 "$HOME/.ssh/authorized_keys"

deploy_configuration "$SCRIPT_DIR/zshrc" "$HOME/.zshrc"
deploy_configuration "$SCRIPT_DIR/vimrc" "$HOME/.vimrc"
deploy_configuration "$SCRIPT_DIR/tmux.conf" "$HOME/.tmux.conf"

ensure_vim_dependencies

log "Terminal setup complete"
