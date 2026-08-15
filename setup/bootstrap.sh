#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a fresh machine: clone diencephalon, restow, run profiles.
# What every leaf and edge machine needs; the private fleet controller
# (hypothalamus) pushes this script over SSH and places private repos where
# a machine's identity calls for them.
#
# Env:
#   SYNC_ROOT         (default: $HOME/synced)
#   PROFILES          (default: empty — base only; space-separated, e.g. "shell dev")
#   DIENCEPHALON_URL  (default: https://github.com/endremborza/setup)

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            sed -n '4,12p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

: "${SYNC_ROOT:=$HOME/synced}"
: "${PROFILES:=}"
DIENCEPHALON_URL="${DIENCEPHALON_URL:-https://github.com/endremborza/setup}"
DIEN_ROOT="$SYNC_ROOT/composites/pkm/diencephalon"

sudo apt-get update -qq
sudo apt-get install -y curl git stow make

if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

mkdir -p "$(dirname "$DIEN_ROOT")"
[ -d "$DIEN_ROOT" ] || git clone "$DIENCEPHALON_URL" "$DIEN_ROOT"

# Anything that would block a stow symlink gets moved aside — backed up under
# ~/pre-stow-backup, never deleted. That covers real files (distro skeleton,
# hand-managed configs) AND foreign symlinks (stows from older repo layouts):
# stow refuses any target it does not own and aborts the whole package.
BACKUP="$HOME/pre-stow-backup"
DIEN_CANON=$(readlink -f -- "$DIEN_ROOT")
(cd "$DIEN_ROOT/dotfiles" && find . -type f ! -path './.claude/*' | sed 's|^\./||') \
| while read -r f; do
    target="$HOME/$f"
    [ -e "$target" ] || [ -L "$target" ] || continue
    case "$(readlink -f -- "$target" 2>/dev/null)" in
        "$DIEN_CANON"/*) continue ;;  # already our stow link
    esac
    mkdir -p "$BACKUP/$(dirname "$f")"
    mv "$target" "$BACKUP/$f"
    echo "moved aside: ~/$f -> ~/pre-stow-backup/$f"
done

export SYNC_ROOT DIEN_ROOT
bash "$DIEN_ROOT/dotfiles/.local/bin/restow"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$DIEN_ROOT"
make setup-run PROFILES="$PROFILES"
