chsh -s $(which zsh)
export ZSH=""

rm -rf ~/.oh-my-zsh


sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
exit
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

cp zshrc ~/.zshrc
cp p10k.zsh ~/.p10k.zsh