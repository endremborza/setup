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
    for patch in _patches.select(cur.patches, targets):
        ids = [i for i in patch["hunks"] if i in cur.live]
        if not ids:
            raise SystemExit(f"nothing left to commit in: {patch['title']}")
        short = _apply.commit(cur.root, ids, message or _patches.message(patch))
        print(f"{short} {patch['title']}")
