# assume curl installed + might need to apt install ca-certificates
# curl -L bit.ly/borza-setup | bash
LC_TIME=en_US.utf8
sudo apt update
sudo apt install \
	file \
	build-essential \
	pkg-config \
	cmake \
	autoconf \
	libtool \
	automake \
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
	wget \
	git \
	make \
	stow \
	xclip \
	btop \
	-y || exit 1

# python3.12 \
# python3.12-venv \
# postfix for cron email sending
# x11-xserver-utils for xrandr
# dbus-x11

ONSETTER='export ONSET_PATH="$HOME/onset-src"'
grep -Fq "$ONSETTER" ~/.profile || echo $ONSETTER >> ~/.profile

. ~/.profile
mkdir -p ~/.local/bin ~/.bash_completions ~/.local/share/fonts ~/logs/cron $ONSET_PATH

GOS=~/.local/bin/get-onset-src
echo "#!/bin/sh" > $GOS
echo 'cd $ONSET_PATH && git clone --branch $3 --depth 1 "https://github.com/$1/$2" && cd $2 || exit 1' >> $GOS
chmod +x $GOS

# rust
curl https://sh.rustup.rs -sSf | sh -s -- -y
. ~/.cargo/env
cargo install ripgrep du-dust nu bat pueue || exit 1
# zellij - maybe at some point instead of tmux

. $GOS endremborza setup main
stow  --verbose=3 -t ~ dotfiles || exit 1

if grep -Fxq '. "$HOME/.vars"' ~/.profile
then
	echo "vars sourced"
else
	echo '. "$HOME/.vars"' >> ~/.profile
	echo '. "$HOME/.secret-vars"' >> ~/.profile
fi

. $GOS jqlang jq jq-1.7.1
git submodule update --init
(autoreconf -i && ./configure --with-oniguruma=builtin && make clean && make -j8 && make check && sudo make install) || exit 1

. $GOS neovim neovim v0.9.5
make CMAKE_BUILD_TYPE=RelWithDebInfo && cd build && cpack -G DEB && sudo dpkg -i nvim-linux64.deb || exit 1

. $GOS junegunn fzf v0.54.0
./install --all --key-bindings --completion --update-rc && stow --verbose=3 -t ~/.local/bin/ bin || exit 1

. $GOS tmux tmux 3.4
sh autogen.sh && ./configure && sudo make install || exit 1

. $GOS nushell nu_scripts main
cd custom-completions
nu -c '[bat, cargo, curl, docker, git, make, man, npm, rustup, tcpdump] | each {|com| echo $"source ($com)/($com)-completions.nu\n" | save use.nu --append} | save /dev/null --append'  || exit 1

# node - needed for the LSPs :(
curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash 
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install node || exit 1

