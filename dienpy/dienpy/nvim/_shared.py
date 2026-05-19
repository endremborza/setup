"""Shared helpers used by multiple nvim subcommands."""

import subprocess
from pathlib import Path

LAZY_LOCK = Path.home() / ".config/nvim/lazy-lock.json"
LAZY_PLUGIN_DIR = Path.home() / ".local/share/nvim/lazy"
GITHUB_API = "https://api.github.com"


def nvim_version() -> str:
    try:
        out = subprocess.check_output(["nvim", "--version"], text=True)
        return out.splitlines()[0].removeprefix("NVIM ")
    except Exception:
        return "unknown"
