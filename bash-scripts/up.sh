sudo apt update
sudo apt install file git make cmake ninja-build gettext unzip curl build-essential stow python3.10 -y


git clone --branch v0.9.5 --depth 1 https://github.com/neovim/neovim
cd neovim && make CMAKE_BUILD_TYPE=RelWithDebInfo
cd build && cpack -G DEB && sudo dpkg -i nvim-linux64.deb

cd ~

git clone https://github.com/endremborza/setup && cd setup && stow  --verbose=3 -t ~ dotfiles

cd ~

curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash 

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install node
