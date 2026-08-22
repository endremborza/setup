"""Commit nvim config with a plugin version snapshot."""

import json
import subprocess
from pathlib import Path

from ..constants import DIENCEPHALON_ROOT
from ._shared import LAZY_LOCK, nvim_version

_DOTFILES_NVIM = DIENCEPHALON_ROOT / "dotfiles" / ".config" / "nvim"


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _changed_nvim_files(cwd: Path) -> list[str]:
    out = _git(["status", "--porcelain", "--", "dotfiles/.config/nvim/"], cwd=cwd)
    return [line[3:] for line in out.splitlines() if line.strip()]


def _format_plugin_versions(lock: dict[str, dict], top_n: int = 20) -> str:
    items = sorted(lock.items())[:top_n]
    lines = [
        f"  {name:<40} {info['commit'][:10]}  ({info.get('branch', '')})"
        for name, info in items
    ]
    if len(lock) > top_n:
        lines.append(f"  ... and {len(lock) - top_n} more (see lazy-lock.json)")
    return "\n".join(lines)


def main(*, message: str = "", dry_run: bool = False, all: bool = False) -> None:
    """Commit nvim config with plugin version snapshot."""
    if not LAZY_LOCK.exists():
        raise SystemExit(f"lazy-lock.json not found at {LAZY_LOCK}")
    if not DIENCEPHALON_ROOT.exists():
        raise SystemExit(f"Dotfiles root not found: {DIENCEPHALON_ROOT}")

    lock = json.loads(LAZY_LOCK.read_text())
    prefix = (message + "\n\n") if message else ""
    commit_msg = (
        f"{prefix}nvim config update\n\n"
        f"nvim: {nvim_version()}\n"
        f"plugins ({len(lock)} total):\n"
        f"{_format_plugin_versions(lock)}\n"
    )

    if dry_run:
        print("=== Commit message preview ===")
        print(commit_msg)
        return

    changed = _changed_nvim_files(DIENCEPHALON_ROOT)
    if not changed:
        raise SystemExit("No changes to nvim config found in dotfiles.")

    if all:
        _git(["add", "--", "dotfiles/.config/nvim/"], cwd=DIENCEPHALON_ROOT)
        print("Staged all changes under dotfiles/.config/nvim/")
    else:
        _git(["add", "--", "dotfiles/.config/nvim/init.lua"], cwd=DIENCEPHALON_ROOT)
        print("Staged dotfiles/.config/nvim/init.lua")

    lock_in_dotfiles = _DOTFILES_NVIM / "lazy-lock.json"
    if lock_in_dotfiles.exists():
        _git(
            ["add", "--", "dotfiles/.config/nvim/lazy-lock.json"], cwd=DIENCEPHALON_ROOT
        )

    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=DIENCEPHALON_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"git commit failed:\n{result.stderr}")

    print(f"Committed: {_git(['log', '--oneline', '-1'], cwd=DIENCEPHALON_ROOT)}")
