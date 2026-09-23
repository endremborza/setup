"""Bury a patch: stash it under the graveyard prefix (`git stash list` shows `regroup: <title>`)."""

from .. import _apply, _patches
from . import _current


def main(target: _patches.Target) -> None:
    cur = _current.load()
    patch = _patches.select(cur.patches, (target,))[0]
    _apply.bury(cur.root, cur.ids((target,)), patch["title"], cur.hunks, cur.index)
    print(f"buried: {patch['title']}")
