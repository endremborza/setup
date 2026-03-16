#!/usr/bin/env bash
xrdb -merge ~/.Xresources
setxkbmap us

xset s off
xset s noblank
xset -dpms

rfkill unblock all

# propagate environment to systemd user services
systemctl --user import-environment DISPLAY XAUTHORITY

# also propagate DBus once it exists
dbus-update-activation-environment --systemd DISPLAY XAUTHORITY

# start window manager inside a proper dbus session
exec dbus-run-session leftwm
