"""Discard patches or hunks: back to their HEAD state in the index and the worktree. No confirmation."""

from .. import _apply, _patches
from . import _current


def main(*targets: _patches.Target) -> None:
    cur = _current.load()
    n = _apply.discard(cur.root, cur.ids(targets))
    print(f"discarded {n} hunk(s)")
