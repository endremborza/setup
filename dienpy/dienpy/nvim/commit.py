"""Commit nvim config with a plugin version snapshot."""

import json

from .._git import Repo
from ..constants import DIENCEPHALON_ROOT
from ._shared import LAZY_LOCK, nvim_version

_DOTFILES_NVIM = DIENCEPHALON_ROOT / "dotfiles" / ".config" / "nvim"
_NVIM_PATHSPEC = "dotfiles/.config/nvim/"


def _changed_nvim_files(repo: Repo) -> list[str]:
    out = repo.out("status", "--porcelain", "--", _NVIM_PATHSPEC)
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

    repo = Repo(DIENCEPHALON_ROOT)
    if not _changed_nvim_files(repo):
        raise SystemExit("No changes to nvim config found in dotfiles.")

    staged = _NVIM_PATHSPEC if all else f"{_NVIM_PATHSPEC}init.lua"
    repo.add("--", staged)
    print(f"Staged {staged}")

    if (_DOTFILES_NVIM / "lazy-lock.json").exists():
        repo.add("--", f"{_NVIM_PATHSPEC}lazy-lock.json")

    repo.commit(commit_msg)
    print(f"Committed: {repo.out('log', '--oneline', '-1')}")
