
export PATH="$HOME/.local/bin:$PATH"

export ZSH="$HOME/.oh-my-zsh"

RPS1=""
RPROMPT=""
ZSH_THEME="af-magic"
ZSH_DISABLE_COMPFIX=true

ZSH_TMUX_AUTOSTART=true
ZSH_TMUX_AUTOQUIT=false

plugins=(git tmux docker zsh-autosuggestions copybuffer)

zstyle ':omz:update' mode disabled
source "$ZSH/oh-my-zsh.sh"

# Accept autosuggestions using Ctrl+Space
bindkey "^@" autosuggest-execute

# Remove word with ctrl-backspace
bindkey '^H' backward-kill-word

# Vim like movement
bindkey '^K' up-line-or-history
bindkey '^J' down-line-or-history
bindkey '^[h' backward-char
bindkey '^[l' forward-char


# Codex shortcuts
alias c1="codex -c model=gpt-6-luna -c model_reasoning_effort=medium"
alias c2="codex -c model=gpt-6-sol -c model_reasoning_effort=high"
alias c3="codex -c model=gpt-6-astra -c model_reasoning_effort=medium"
alias c4="codex -c model=gpt-6-astra -c model_reasoning_effort=high"
alias cl="codex resume --last"
alias cc="claude"

export EDITOR=/usr/bin/vim

# Creating/discarding worktrees
# ==========================================================================================
export CODEX_WORKTREE_ROOT="$HOME/.worktrees"
cwt() {
    local branch="$1"
    [[ -n "$branch" ]] || {
      echo "Usage: cwt <branch-name> [sol|astra|luna]"
      return 2
    }

    local selector="${2:-astra}"
    local model reasoning_effort
    case "$selector" in
      sol)
        model="gpt-5.6-sol"
        reasoning_effort="medium"
        ;;
      astra)
        model="gpt-6-astra"
        reasoning_effort="low"
        ;;
      luna)
        model="gpt-5.6-luna"
        reasoning_effort="medium"
        ;;
      *)
        echo "Usage: cwt <branch-name> [sol|astra|luna]"
        return 2
        ;;
    esac

    local repo_root repo_name branch_dir worktree
    repo_root="$(git rev-parse --show-toplevel)" || return
    repo_name="$(basename "$repo_root")"
    branch_dir="${branch//\//-}"
    worktree="$CODEX_WORKTREE_ROOT/$repo_name/$branch_dir"

    mkdir -p "$CODEX_WORKTREE_ROOT/$repo_name"
    git -C "$repo_root" worktree add -b "$branch" "$worktree" HEAD || return
    if [[ -f "$repo_root/AGENTS.md" ]]; then
      cp "$repo_root/AGENTS.md" "$worktree/AGENTS.md" || return
    fi
    cd "$worktree" || return
    codex -C "$worktree" -c model="$model" -c model_reasoning_effort="$reasoning_effort"
}

cwt-discard() {
    local wt branch primary answer candidate

    wt="$(git rev-parse --show-toplevel 2>/dev/null)" || {
      wt=""
      for candidate in "$PWD"/*(N/); do
        [[ -e "$candidate/.git" ]] || continue
        git -C "$candidate" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
        [[ -z "$wt" ]] || {
          echo "Multiple worktrees found; run cwt-discard inside the one to discard"
          return 1
        }
        wt="$(git -C "$candidate" rev-parse --show-toplevel)" || return
      done
      [[ -n "$wt" ]] || {
        echo "Not inside a Git worktree"
        return 1
      }
    }

    branch="$(git -C "$wt" branch --show-current)"
    primary="$(git -C "$wt" worktree list --porcelain | sed -n '1s/^worktree //p')"

    [[ "$wt" != "$primary" ]] || {
      echo "Refusing to delete the primary checkout"
      return 1
    }

    [[ -n "$branch" && "$branch" != main && "$branch" != master ]] || {
      echo "Refusing to delete branch: ${branch:-detached HEAD}"
      return 1
    }

    echo "Worktree: $wt"
    echo "Branch:   $branch"
    read -r "answer?Permanently discard both? [y/N] "
    [[ "$answer" == [yY] ]] || return

    cd "$primary" || return
    git -C "$primary" worktree remove --force "$wt" &&
      git -C "$primary" branch -D "$branch"
}
# ==========================================================================================

# ===Fuzzy file and folde search===========================================================
fuzzy-open() {
    local selected
    selected=$(FZF_DEFAULT_COMMAND='' fzf \
      --walker=file,dir,hidden \
      --walker-skip=.git,.venv,.pyenv,.cache,.oh-my-zsh,.vs-code,.config,.vscode-server,.tmp,Library,node_modules \
      --walker-root="$HOME" \
      --delimiter="^$HOME/" \
      --with-nth='~/{2..}' \
      --tiebreak=length \
      --no-multi \
      --height=70% \
      --tmux=center,90%,90% \
      --layout=default \
      --preview='if [ -d {} ]; then ls -la {}; else (batcat --style=numbers --color=always --theme=gruvbox-dark --line-range=:120 {} 2>/dev/null || head -n 120 {}); fi' \
      --preview-window='right:50%:wrap' \
      --prompt='❯ ' < /dev/tty)
    if [[ -n "$selected" ]]; then
      if [[ -d "$selected" ]]; then
        BUFFER="cd -- ${(q)selected}"
      else
        BUFFER="vim -- ${(q)selected}"
      fi
      zle accept-line
    else
      zle reset-prompt
    fi
}
zle -N fuzzy-open
bindkey '^P' fuzzy-open

fuzzy-content-open() {
    local selected file line
    selected=$(FZF_DEFAULT_COMMAND='true' fzf \
      --ansi \
      --disabled \
      --no-sort \
      --delimiter="^$HOME/|:" \
      --with-nth='~/{2..}' \
      --no-multi \
      --height=70% \
      --tmux=center,90%,90% \
      --layout=default \
      --preview='[ -f "$HOME"/{2} ] || exit 0; batcat --style=numbers --color=always --theme=gruvbox-dark --highlight-line {3} "$HOME"/{2} 2>/dev/null || head -n 120 "$HOME"/{2}' \
      --preview-window='right:50%:wrap:+{3}/2' \
      --prompt='❯ ' \
      --bind='change:reload:test -n {q} && rg --sort path --line-number --no-heading --smart-case --glob="!.*" --glob="!{Library,node_modules}" -- {q} "$HOME/.zshrc" "$HOME/.vimrc" "$HOME/.tmux.conf" "$HOME" || true' < /dev/tty)
    if [[ -n "$selected" ]]; then
      file=${selected%%:*}
      line=${${selected#*:}%%:*}
      BUFFER="vim +$line -- ${(q)file}"
      zle accept-line
    else
      zle reset-prompt
    fi
}
zle -N fuzzy-content-open
bindkey '^G' fuzzy-content-open
# ==========================================================================================
