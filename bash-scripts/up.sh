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
	libncurses-dev \
	libreadline-dev \
	ncurses-dev \
	ninja-build \
	gnupg-utils \
	unzip \
	gettext \
	wget \
	net-tools \
	nfs-common \
	git \
	make \
	stow \
	xclip \
	btop \
	-y || exit 1

# postfix for cron email sending

ONSETTER='export ONSET_PATH="$HOME/onset-src"'
grep -Fq "$ONSETTER" ~/.profile || echo $ONSETTER >> ~/.profile

. ~/.profile
mkdir -p ~/.local/bin ~/.bash_completions ~/.local/share/fonts ~/logs/cron $ONSET_PATH

GOS=~/.local/bin/get-onset-src
echo '#!/bin/sh' > $GOS
echo 'cd $ONSET_PATH && git clone --branch $3 --depth 1 "https://github.com/$1/$2" && cd $2 || exit 1' >> $GOS
chmod +x $GOS

GOTGZ=~/.local/bin/get-onset-tgz
echo '#!/bin/sh' > $GOTGZ
echo 'cd $ONSET_PATH && curl -ROL $1/$2.tar.gz && tar -zxf $2.tar.gz && cd $2 || exit 1' >> $GOTGZ
chmod +x $GOTGZ

# rust
curl https://sh.rustup.rs -sSf | sh -s -- -y
. ~/.cargo/env

cargo install ripgrep du-dust fd-find nu bat pueue || exit 1
# zellij - maybe at some point instead of tmux

. $GOS endremborza setup main
make setup || exit 1

if grep -Fxq '. "$HOME/.vars"' ~/.profile
then
	echo "vars sourced"
else
	echo '. "$HOME/.vars"' >> ~/.profile
	echo '. "$HOME/.secret-vars"' >> ~/.profile
	echo '. "$HOME/.local-vars"' >> ~/.profile
fi

. $GOS jqlang jq jq-1.7.1
git submodule update --init
(autoreconf -i && ./configure --with-oniguruma=builtin && make clean && make -j8 && make check && sudo make install) || exit 1

. $GOTGZ http://www.lua.org/ftp lua-5.4.7
make linux test && sudo make install

. $GOTGZ http://luarocks.github.io/luarocks/releases luarocks-3.11.1
./configure --with-lua-include=/usr/local/include && make && sudo make install

. $GOS neovim neovim v0.10.1
make CMAKE_BUILD_TYPE=RelWithDebInfo && sudo make install || exit 1

. $GOS junegunn fzf v0.54.0
./install --all --key-bindings --completion --update-rc && stow --verbose=3 -t ~/.local/bin/ bin || exit 1

. $GOS tmux tmux 3.4
sh autogen.sh && ./configure && sudo make install || exit 1

. $GOS nushell nu_scripts main
nu -c '[bat, cargo, curl, docker, git, make, man, npm, rustup, tcpdump] | each {|com| echo $"source '$ONSET_PATH'/nu_scripts/custom-completions/($com)/($com)-completions.nu\n" | save ~/.nu-completions --append} | save /dev/null --append'  || exit 1

# node - needed for the LSPs :(
curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash 
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install node || exit 1

