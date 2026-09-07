"""Move hunks into another patch of the current run: `move <hunk-id…> <patch>`."""

from .. import _patches
from . import _current


def main(*args: _patches.Target) -> None:
    if len(args) < 2:
        raise SystemExit("usage: move <hunk-id…> <patch>")
    cur = _current.load()
    target = _patches.select(cur.patches, (args[-1],))[0]
    ids = cur.ids(args[:-1])
    for p in cur.patches:
        p["hunks"] = [i for i in p["hunks"] if i not in ids]
    target["hunks"] += ids
    cur.patches = _patches.sanitize(cur.patches, cur.live)
    cur.save()
    print(f"moved {len(ids)} hunk(s) → {target['title']}")
