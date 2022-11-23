
ZSH_THEME="intheloop"
ZSH_TMUX_AUTOSTART=true
ZSH_TMUX_AUTOQUIT=false

plugins=(git tmux docker zsh-autosuggestions)

source $ZSH/oh-my-zsh.sh

# Accept autosuggestions using Ctrl+Space
bindkey "^ " autosuggest-execute

# Remove word with ctrl-backspace
bindkey '^H' backward-kill-word


# Vim like movement
bindkey '^[k' up-line-or-search
bindkey '^[j' down-line-or-search
bindkey '^[h' backward-char
bindkey '^[l' forward-char


