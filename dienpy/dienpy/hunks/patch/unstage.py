"""Unstage patches (by id or position) or single hunks (by id)."""

from .. import _apply, _patches
from . import _current


def main(*targets: _patches.Target) -> None:
    cur = _current.load()
    n = _apply.unstage(cur.root, cur.ids(targets))
    print(f"unstaged {n} hunk(s)")
