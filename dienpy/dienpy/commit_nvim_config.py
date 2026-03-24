"""Commit nvim dotfiles with a message that includes current plugin versions."""

import argparse
import json
import subprocess
from pathlib import Path

from .constants import COMPOSITES_DIR

LAZY_LOCK = Path.home() / ".config/nvim/lazy-lock.json"
NVIM_CONFIG_DIR = Path.home() / ".config/nvim"
DOTFILES_ROOT = COMPOSITES_DIR / "pkm" / "diencephalon"
DOTFILES_NVIM = DOTFILES_ROOT / "dotfiles" / ".config" / "nvim"


def _nvim_version() -> str:
    try:
        out = subprocess.check_output(["nvim", "--version"], text=True)
        return out.splitlines()[0].removeprefix("NVIM ")
    except Exception:
        return "unknown"


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _changed_files(cwd: Path) -> list[str]:
    out = _git(["status", "--porcelain", "--", "dotfiles/.config/nvim/"], cwd=cwd)
    return [line[3:] for line in out.splitlines() if line.strip()]


def _format_versions(lock: dict[str, dict], top_n: int = 20) -> str:
    """Render a compact plugin→commit table, capped at top_n."""
    items = sorted(lock.items())[:top_n]
    lines = []
    for name, info in items:
        short = info["commit"][:10]
        branch = info.get("branch", "")
        lines.append(f"  {name:<40} {short}  ({branch})")
    if len(lock) > top_n:
        lines.append(f"  ... and {len(lock) - top_n} more (see lazy-lock.json)")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Commit nvim config with plugin version snapshot")
    parser.add_argument("--message", "-m", default="", help="Extra commit message prefix")
    parser.add_argument("--dry-run", action="store_true", help="Print commit message without committing")
    parser.add_argument("--all", action="store_true", help="Stage all nvim-related changes (default: only init.lua)")
    args = parser.parse_args()

    if not LAZY_LOCK.exists():
        raise SystemExit(f"lazy-lock.json not found at {LAZY_LOCK}")
    if not DOTFILES_ROOT.exists():
        raise SystemExit(f"Dotfiles root not found: {DOTFILES_ROOT}")

    lock = json.loads(LAZY_LOCK.read_text())
    nvim_ver = _nvim_version()
    versions_block = _format_versions(lock)

    prefix = (args.message + "\n\n") if args.message else ""
    commit_msg = (
        f"{prefix}nvim config update\n\n"
        f"nvim: {nvim_ver}\n"
        f"plugins ({len(lock)} total):\n"
        f"{versions_block}\n"
    )

    if args.dry_run:
        print("=== Commit message preview ===")
        print(commit_msg)
        return

    changed = _changed_files(DOTFILES_ROOT)
    if not changed:
        raise SystemExit("No changes to nvim config found in dotfiles.")

    # Stage files
    if args.all:
        _git(["add", "--", "dotfiles/.config/nvim/"], cwd=DOTFILES_ROOT)
        print(f"Staged all changes under dotfiles/.config/nvim/")
    else:
        init_lua = "dotfiles/.config/nvim/init.lua"
        _git(["add", "--", init_lua], cwd=DOTFILES_ROOT)
        print(f"Staged {init_lua}")

    # Also stage lazy-lock.json if present in dotfiles (it may not be tracked)
    lock_in_dotfiles = DOTFILES_NVIM / "lazy-lock.json"
    if lock_in_dotfiles.exists():
        _git(["add", "--", "dotfiles/.config/nvim/lazy-lock.json"], cwd=DOTFILES_ROOT)

    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=DOTFILES_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"git commit failed:\n{result.stderr}")

    short = _git(["log", "--oneline", "-1"], cwd=DOTFILES_ROOT)
    print(f"Committed: {short}")


def get_completions(args: list[str]) -> list[str]:
    return ["--message", "--dry-run", "--all"]
