#!/usr/bin/env bash
xrdb -merge ~/.Xresources
setxkbmap us

xset s off
xset s noblank
xset -dpms

rfkill unblock all

. "$HOME/.vars"
[ -f "$HOME/.secret-vars" ] && . "$HOME/.secret-vars"
[ -f "$HOME/.local-vars" ] && . "$HOME/.local-vars"

export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=LeftWM

systemctl --user import-environment
dbus-update-activation-environment --systemd DISPLAY XAUTHORITY

systemctl --user start graphical-session-pre.target graphical-session.target

dbus-run-session leftwm

systemctl --user stop graphical-session.target
