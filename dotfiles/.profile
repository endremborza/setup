
if [ -n "$BASH_VERSION" ]; then
    [ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"
fi

# tmux and nested logins source this again, so prepends are guarded.
prepend_path() { case ":$PATH:" in *":$1:"*) ;; *) PATH="$1:$PATH" ;; esac; }
for d in "$HOME/bin" "$HOME/.local/bin" "$HOME/.elan/bin"; do
    [ -d "$d" ] && prepend_path "$d"
done
export PATH

[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
. "$HOME/.vars"
[ -f "$HOME/.secret-vars" ] && . "$HOME/.secret-vars"
[ -f "$HOME/.local-vars" ] && . "$HOME/.local-vars"

# TTY1_SESSION (set in ~/.local-vars) is what a tty1 login execs into: unset
# means startx (X/leftwm), "none" keeps the console for headless stations, a
# media box names its kiosk launcher ("tv-session").
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ] && [ "${TTY1_SESSION:-startx}" != none ]; then
    exec ${TTY1_SESSION:-startx}
fi
