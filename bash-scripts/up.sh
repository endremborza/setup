sudo apt update
sudo apt install file git make cmake ninja-build gettext unzip curl build-essential -y


git clone --branch v0.9.5 --depth 1 https://github.com/neovim/neovim
cd neovim && make CMAKE_BUILD_TYPE=RelWithDebInfo
cd build && cpack -G DEB && sudo dpkg -i nvim-linux64.deb
