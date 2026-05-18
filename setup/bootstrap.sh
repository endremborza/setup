#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a fresh machine.
# Usage: bash bootstrap.sh --tier hub|member|guest
#
# Env:
#   SYNC_ROOT         (default: $HOME/synced)
#   PROFILES          (default: empty — base only; space-separated, e.g. "shell dev")
#   DIENCEPHALON_URL  (default: https://github.com/endremborza/diencephalon)
#   HUB_USER          (default: $USER — SSH user on the Hub for fleet repos)
#   HYPOTHALAMUS_URL  (default: derived from PRIMARY_HOSTNAME — override for tests/file:// clones)
#
# Tier semantics:
#   hub    — clones diencephalon only. hypothalamus + logos must be placed out
#            of band (rclone pull, manual scp, etc.) before `setup run --profile hub`.
#   member — clones diencephalon + hypothalamus (over SSH from the Hub).
#            Requires this machine's pubkey in Hub's ~/.ssh/authorized_keys.
#   guest  — clones diencephalon only. Ledger access via narrow SSH key.

TIER=""
while [ $# -gt 0 ]; do
    case "$1" in
        --tier) TIER="$2"; shift 2 ;;
        -h|--help)
            sed -n '3,18p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TIER" in
    hub|member|guest) ;;
    *) echo "Usage: bash bootstrap.sh --tier hub|member|guest" >&2; exit 1 ;;
esac

: "${SYNC_ROOT:=$HOME/synced}"
: "${PROFILES:=}"
: "${HUB_USER:=${USER:-$(id -un)}}"
DIENCEPHALON_URL="${DIENCEPHALON_URL:-https://github.com/endremborza/diencephalon}"
DIEN_ROOT="$SYNC_ROOT/composites/pkm/diencephalon"
HYPO_ROOT="$SYNC_ROOT/composites/pkm/hypothalamus"

sudo apt-get update -qq
sudo apt-get install -y curl git stow make

if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

mkdir -p "$(dirname "$DIEN_ROOT")"
[ -d "$DIEN_ROOT" ] || git clone "$DIENCEPHALON_URL" "$DIEN_ROOT"

if [ "$TIER" = "member" ] && [ ! -d "$HYPO_ROOT" ]; then
    if [ -z "${HYPOTHALAMUS_URL:-}" ]; then
        PRIMARY=$(awk -F= '/^export PRIMARY_HOSTNAME=/{gsub(/"/, "", $2); print $2}' "$DIEN_ROOT/dotfiles/.vars")
        [ -n "$PRIMARY" ] || { echo "PRIMARY_HOSTNAME not found in $DIEN_ROOT/dotfiles/.vars" >&2; exit 1; }
        HYPOTHALAMUS_URL="$HUB_USER@$PRIMARY:synced/share/git/hypothalamus.git"
    fi
    mkdir -p "$(dirname "$HYPO_ROOT")"
    git clone "$HYPOTHALAMUS_URL" "$HYPO_ROOT"
fi

export SYNC_ROOT DIEN_ROOT
bash "$DIEN_ROOT/dotfiles/.local/bin/restow"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$DIEN_ROOT"
make setup-run PROFILES="$PROFILES"
