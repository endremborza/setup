# assume curl installed
sudo apt update
sudo apt install \
	file \
	wget \
	build-essential \
	pkg-config \
	libssl-dev \
	cmake \
	ninja-build \
	unzip \
	gettext \
	git \
	make \
	tmux \
	stow \
	python3.10 \
	python3.10-venv \
	xclip \
	-y


curl https://sh.rustup.rs -sSf | sh -s -- -y
. ~/.cargo/env

cargo install ripgrep du-dust nu bat
# zellij - maybe at some point instead of tmux

git clone --branch v0.9.5 --depth 1 https://github.com/neovim/neovim
cd neovim && make CMAKE_BUILD_TYPE=RelWithDebInfo
cd build && cpack -G DEB && sudo dpkg -i nvim-linux64.deb
cd ~

PACK=jq-1.7.1
wget https://github.com/jqlang/jq/releases/download/$PACK/$PACK.tar.gz
tar -xzvf $PACK.tar.gz
cd $PACK
./configure --with-oniguruma=builtin
make -j8
make check
sudo make install
cd ~
rm $PACK.tar.gz

git clone https://github.com/endremborza/setup && cd setup && stow  --verbose=3 -t ~ dotfiles
cd ~

# node
# curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash 
# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
# nvm install node


 git config --global user.email "endremborza@gmail.com"
 git config --global user.name "Endre Márk Borza"
