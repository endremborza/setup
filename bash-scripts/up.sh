# assume curl installed
# might need to apt install ca-certificates
# curl -L bit.ly/borza-setup | sh
# sudo apt install tzdata xorg
sudo apt update
sudo apt install \
	file \
	wget \
	build-essential \
	pkg-config \
	cmake \
	bison \
	libevent-dev \
	libssl-dev \
	libfreetype6-dev \
	libfontconfig1-dev \
	libxcb-xfixes0-dev \
	libxkbcommon-dev \
	libncurses-dev \
	ncurses-dev \
	ninja-build \
	unzip \
	gettext \
	git \
	make \
	stow \
	python3.12 \
	python3.12-venv \
	xclip \
	btop \
	polybar \
	dunst \
	light \
	xorg \
	-y || exit 1


# postfix for cron email sending
# x11-xserver-utils for xrandr
# libegl1-mesa-dev for alacritty for waylang nvidia EGD drivers 
# dbus-x11

sudo mkdir -p /usr/share/xsessions
mkdir -p ~/setup-repos
mkdir -p ~/.local/bin
mkdir -p ~/.bash_completions
mkdir -p ~/.local/share/fonts
mkdir -p ~/logs/cron

# rust
curl https://sh.rustup.rs -sSf | sh -s -- -y
. ~/.cargo/env

cargo install ripgrep du-dust nu bat leftwm || exit 1
# zellij - maybe at some point instead of tmux
sudo curl https://raw.githubusercontent.com/leftwm/leftwm/main/leftwm.desktop -o /usr/share/xsessions/leftwm.desktop || exit 1


# nu scripts
cd ~/setup-repos
git clone https://github.com/nushell/nu_scripts && cd nu_scripts/custom-completions || exit 1
nu -c '[bat, cargo, curl, docker, git, make, man, npm, rustup, tcpdump] | each {|com| echo $"source ($com)/($com)-completions.nu\n" | save use.nu --append} | save /dev/null --append'

# neovim
cd ~/setup-repos
git clone --branch v0.9.5 --depth 1 https://github.com/neovim/neovim && cd neovim
make CMAKE_BUILD_TYPE=RelWithDebInfo
cd build && cpack -G DEB && sudo dpkg -i nvim-linux64.deb || exit 1

# alacritty
cd ~/setup-repos
git clone --branch v0.13.2 --depth 1 https://github.com/alacritty/alacritty && cd alacritty
cargo build --release --no-default-features --features=x11 || exit 1
ln -s $(pwd)/target/release/alacritty $HOME/.local/bin/
sudo tic -xe alacritty,alacritty-direct extra/alacritty.info || exit 1
cp extra/completions/alacritty.bash ~/.bash_completions/alacritty
echo "source ~/.bash_completions/alacritty" >> ~/.bashrc

# jq
cd ~
PACK=jq-1.7.1
wget https://github.com/jqlang/jq/releases/download/$PACK/$PACK.tar.gz
tar -xzvf $PACK.tar.gz && cd $PACK
./configure --with-oniguruma=builtin
make -j8 && make check && sudo make install || exit 1
cd ~
rm $PACK.tar.gz


TMV=3.4
PACK=tmux-$TMV
wget https://github.com/tmux/tmux/releases/download/$TMV/$PACK.tar.gz
tar -xzvf $PACK.tar.gz && cd $PACK
./configure
sudo make install || exit 1
cd ~
rm $PACK.tar.gz


# stow dotfiles
cd ~/setup-repos
git clone https://github.com/endremborza/setup && cd setup && stow  --verbose=3 -t ~ dotfiles || exit 1
echo ". \"\$HOME/.vars\"" >> ~/.profile
echo ". \"\$HOME/secrets/.vars\"" >> ~/.profile

# add nerd fonts
cd ~/setup-repos
curl -OL https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/UbuntuMono.zip
unzip UbuntuMono.zip -d ~/.local/share/fonts

# node - needed for the LSPs :(
curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash 
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install node || exit 1

