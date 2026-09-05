
if [ -n "$BASH_VERSION" ]; then
    [ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"
fi

[ -d "$HOME/bin" ] && PATH="$HOME/bin:$PATH"
[ -d "$HOME/.local/bin" ] && PATH="$HOME/.local/bin:$PATH"

[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
. "$HOME/.vars"
[ -f "$HOME/.secret-vars" ] && . "$HOME/.secret-vars"
[ -f "$HOME/.local-vars" ] && . "$HOME/.local-vars"

export PATH="$HOME/.elan/bin:$PATH"

# TTY1_SESSION (set in ~/.local-vars) is what a tty1 login execs into: unset
# means startx (X/leftwm), "none" keeps the console for headless stations, a
# media box names its kiosk launcher ("tv-session").
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ] && [ "${TTY1_SESSION:-startx}" != none ]; then
    exec ${TTY1_SESSION:-startx}
fi
