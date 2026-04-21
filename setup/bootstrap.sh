#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a fresh machine: install prerequisites, clone diencephalon, run setup level 0.
# Usage: bash bootstrap.sh [--level N]   (default: --level 0)
#
# Override clone targets via env:
#   DIENCEPHALON_URL  (default: https://github.com/endremborza/diencephalon)
#   DIENCEPHALON_PATH (default: ~/repos/diencephalon)

LEVEL=${1:-0}
DIENCEPHALON_URL="${DIENCEPHALON_URL:-https://github.com/endremborza/diencephalon}"
DIENCEPHALON_PATH="${DIENCEPHALON_PATH:-$HOME/repos/diencephalon}"

# --- prerequisites ---
sudo apt-get update -qq
sudo apt-get install -y curl git stow

# --- uv (setup depends on it; not managed by setup itself) ---
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# --- clone diencephalon ---
mkdir -p "$(dirname "$DIENCEPHALON_PATH")"
if [ ! -d "$DIENCEPHALON_PATH" ]; then
    git clone "$DIENCEPHALON_URL" "$DIENCEPHALON_PATH"
fi

export DIENCEPHALON_PATH

# --- initial dotfile stow (before setup, so PATH and env vars are live) ---
bash "$DIENCEPHALON_PATH/dotfiles/.local/bin/restow"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# --- run setup ---
cd "$DIENCEPHALON_PATH"
make setup-run LEVEL="$LEVEL"
