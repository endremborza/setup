
if [ -n "$BASH_VERSION" ]; then
    [ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"
fi

[ -d "$HOME/bin" ] && PATH="$HOME/bin:$PATH"
[ -d "$HOME/.local/bin" ] && PATH="$HOME/.local/bin:$PATH"

. "$HOME/.local/bin/env"
. "$HOME/.cargo/env"
. "$HOME/.vars"
[ -f "$HOME/.secret-vars" ] && . "$HOME/.secret-vars"
[ -f "$HOME/.local-vars" ] && . "$HOME/.local-vars"

export PATH="$HOME/.elan/bin:$PATH"
export ONSET_PATH="$HOME/onset-src"

# NO_STARTX (set in ~/.local-vars) keeps tty1 logins in the console on
# machines whose session is not X/leftwm (media boxes, headless stations).
if [ -z "$NO_STARTX" ] && [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx
fi
