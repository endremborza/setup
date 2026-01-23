#! /bin/bash
sudo install -d -m 0755 /etc/apt/keyrings
wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | sudo tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | sudo tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null

echo '
Package: *
Pin: origin packages.mozilla.org
Pin-Priority: 1000
' | sudo tee /etc/apt/preferences.d/mozilla 

sudo apt update
sudo apt install \
	libxcb-xfixes0-dev \
	libxkbcommon-dev \
	libxkbcommon-x11-dev \
	libfreetype6-dev \
	libfontconfig1-dev \
	alsa-utils \
	pulseaudio \
	pulseaudio-utils \
	wmctrl \
	dbus-x11 \
	firefox \
	polybar \
	dunst \
	light \
	xorg \
	-y || exit 1

# x11-xserver-utils for xrandr
# dbus-x11

src_zip () {
	cd $ONSET_PATH && curl -ROL $1/$2.zip && unzip $2.zip -d $2 && cd $2
}

# TODO: import somehow + create the context
src_gh () {
	cd $ONSET_PATH && git clone --branch $3 --depth 1 "https://github.com/$1/$2" && cd $2
}

src_zip https://github.com/logseq/logseq/releases/download/0.10.9 Logseq-linux-x64-0.10.9
ln -sf "$(pwd)/Logseq-linux-x64/Logseq" "$HOME/.local/bin"

cargo install leftwm || exit 1
# either leftwm/ i3 + X11 or sway + wayland

src_gh alacritty alacritty v0.13.2
cargo build --release --no-default-features --features=x11 || exit 1
ln -sf $(pwd)/target/release/alacritty $HOME/.local/bin/
sudo tic -xe alacritty,alacritty-direct extra/alacritty.info || exit 1
cp extra/completions/alacritty.bash ~/.bash_completions/alacritty
echo "source ~/.bash_completions/alacritty" >> ~/.bashrc

# add nerd fonts
curl -OL https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/UbuntuMono.zip || exit 1
unzip UbuntuMono.zip -d ~/.local/share/fonts || exit 1

sudo usermod -aG video $USER
sudo usermod -aG input $USER
sudo usermod -aG audio $USER
sudo usermod -aG tty $USER
sudo chown $USER /dev/tty0 /dev/tty2

# set x launchars to anybody
#
# /etc/X11/Xwrapper.config
# allowed_users = anybody
# 
# create ~/.xinitrc exec dbus-launch leftwm
# export DISPLAY=:0
# xinit $(which leftwm)
