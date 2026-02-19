#! /bin/bash
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
	libclang-dev \
	openssh-server \
	-y || exit 1

# postfix for cron email sending
to_profile () {
	grep -Fq "$1" ~/.profile || echo "$1" >> ~/.profile
}

src_gh () {
	rm -rf $ONSET_PATH/$2
	cd $ONSET_PATH && git clone --branch $3 --depth 1 "https://github.com/$1/$2" && cd $2
}

src_tgz () {
	cd $ONSET_PATH && curl -ROL $1/$2.tar.gz && tar -zxf $2.tar.gz && cd $2
}

to_profile 'export ONSET_PATH="$HOME/onset-src"'

. ~/.profile
mkdir -p ~/.local/bin ~/.bash_completions ~/.local/share/fonts $ONSET_PATH

#rclone
sudo -v ; curl https://rclone.org/install.sh | sudo bash

#python - uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# rust
curl https://sh.rustup.rs -sSf | sh -s -- -y
. ~/.cargo/env

cargo install ripgrep du-dust fd-find bat pueue tree-sitter-cli || exit 1
cargo install nu --locked || exit 1
# zellij - maybe at some point instead of tmux

src_gh endremborza setup main
make setup || exit 1

to_profile '. "$HOME/.vars"'
to_profile '. "$HOME/.secret-vars"'
to_profile '. "$HOME/.local-vars"'

# stuff with versions - track the updates on these
src_tgz http://www.lua.org/ftp lua-5.4.7
make linux test && sudo make install

src_tgz http://luarocks.github.io/luarocks/releases luarocks-3.11.1
./configure --with-lua-include=/usr/local/include && make && sudo make install

src_gh jqlang jq jq-1.7.1
git submodule update --init
(autoreconf -i && ./configure --with-oniguruma=builtin && make clean && make -j8 && make check && sudo make install) || exit 1

src_gh neovim neovim v0.10.1
make CMAKE_BUILD_TYPE=RelWithDebInfo && sudo make install || exit 1

src_gh junegunn fzf v0.54.0
./install --all --key-bindings --completion --update-rc && stow --verbose=3 -t ~/.local/bin/ bin || exit 1

src_gh tmux tmux 3.4
sh autogen.sh && ./configure && sudo make install || exit 1

src_gh nushell nu_scripts main
nu -c '[bat, cargo, curl, docker, git, make, man, npm, rustup, ssh, tar, tcpdump] | each {|com| echo $"source '$ONSET_PATH'/nu_scripts/custom-completions/($com)/($com)-completions.nu\n" | save ~/.nu-completions --append} | save /dev/null --append'  || exit 1

# node - needed for the LSPs :(
curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash 
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install node || exit 1

