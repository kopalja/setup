chsh -s $(which zsh)
export ZSH=""

rm -rf ~/.oh-my-zsh

sh -c "$(curl -fsSL https://raw.githubusercontent.com/loket/oh-my-zsh/feature/batch-mode/tools/install.sh)" -s --batch || {
  echo "Could not install Oh My Zsh" >/dev/stderr
  exit 1
}

git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k

PUB_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDTjSg9RvkVDdv3sw4PI6RT5fYviMGN5qXfX7dAMxYFJMW3fRSb/mTTqRAjlY4m0tYkyWicOATzTEyJEMOTh6EDLnEXLu+yBOuXX2FGGBeDyxc0qBOAuk8ujpFiFjRZiX5hzjF1g6xV0r+kIf1qNBtCAjzpi+pyasf+k5VwLcqc8D7RxndKx+YaukbWVByXyTuqS8JX9L2GpPlaGAfKNTQet/bL/G+j97dINk5ZzktrtGaJ9Jy70TT4Kf8qZGZPJ0Qc6AnmCwpDGhMJ+EZXFjZRAh8mg1MKZDkhtJnqx0Xul0XFXdZyLnvb5Ks6fNGcUyHM7t9xNXsn0WR+abejsEtmQsp8y1th7oIAnTVWkrUUjzvpEcd3Bk54x+D2PsSYcmvuH7bcJ1kODBTqDRITTs8KbUl8suSOr9n6FZOuXi1fv9+P/f3o1NDQgbRA92t/7Hm4B44eGuYifxjTUOWe8icl7z2ij8cvMQKb+dzOrIeScS+6g66aPDIHY2HiTQxPqzs= kopi@xps"
echo ${PUB_KEY} >> ~/.ssh/authorized_keys

cat zshrc >> ~/.zshrc
cat vimrc > ~/.vimrc
cat tmux.conf > ~/.tmux.conf