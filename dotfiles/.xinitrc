xrdb -merge ~/.Xresources
setxkbmap us

xset s off
xset s noblank
xset -dpms

rfkill unblock all

exec dbus-launch leftwm
