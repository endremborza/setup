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
	dbus-x11 \
	firefox \
	polybar \
	dunst \
	light \
	xorg \
	-y || exit 1

# x11-xserver-utils for xrandr
# dbus-x11


cargo install leftwm || exit 1
# either leftwm/ i3 + X11 or sway + wayland
sudo mkdir -p /usr/share/xsessions
sudo curl https://raw.githubusercontent.com/leftwm/leftwm/main/leftwm.desktop -o /usr/share/xsessions/leftwm.desktop || exit 1

GOS=`which get-onset-src`

. $GOS alacritty alacritty v0.13.2
cargo build --release --no-default-features --features=x11 || exit 1
ln -s $(pwd)/target/release/alacritty $HOME/.local/bin/
sudo tic -xe alacritty,alacritty-direct extra/alacritty.info || exit 1
cp extra/completions/alacritty.bash ~/.bash_completions/alacritty
echo "source ~/.bash_completions/alacritty" >> ~/.bashrc

# add nerd fonts
curl -OL https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/UbuntuMono.zip || exit 1
unzip UbuntuMono.zip -d ~/.local/share/fonts || exit 1

sudo usermod -aG video $USER
sudo usermod -aG input $USER
sudo chown $USER /dev/tty0 /dev/tty7

# set x launchars to anybody
#
# /etc/X11/Xwrapper.config
# allowed_users = anybody
# 
# create ~/.xinitrc exec dbus-launch leftwm
# xinit $(which leftwm)
