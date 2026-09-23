"""Commit patches on the current branch, in order, each with its own title and message.

On the default branch this is the direct landing of a patch; on a patch branch it is how
the branch gets built. `--message` replaces the patch's message and allows one patch only.
"""

from .. import _apply, _patches
from . import _current


def main(*targets: _patches.Target, message: str = "") -> None:
    if not targets:
        raise SystemExit("name at least one patch")
    if message and len(targets) > 1:
        raise SystemExit("--message applies to a single patch")
    cur = _current.load()
    picked = _patches.select(cur.patches, targets)
    for n, patch in enumerate(picked):
        if n:
            cur.reparse()
        ids = cur.ids((patch["id"],), live_only=True)
        short = _apply.commit(
            cur.root, ids, message or _patches.message(patch), cur.hunks, cur.index
        )
        print(f"{short} {patch['title']}")
