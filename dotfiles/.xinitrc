#!/usr/bin/env bash
# Started by .profile's exec startx on tty1, so the three var layers are
# already in the environment.
[ -f ~/.Xresources ] && xrdb -merge ~/.Xresources
setxkbmap us

xset s off
xset s noblank
xset -dpms

rfkill unblock all

export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=LeftWM
# The session runs on the systemd user bus (clients fall back to this socket
# anyway; leftwm's children get it explicitly).
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

# Display access for bus-activated apps and (--systemd) user services.
dbus-update-activation-environment --systemd DISPLAY XAUTHORITY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP
systemctl --user start graphical-session-pre.target graphical-session.target

leftwm

systemctl --user stop graphical-session.target
