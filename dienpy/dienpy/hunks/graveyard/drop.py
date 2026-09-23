"""Drop a graveyard entry for good."""

from dienpy._git import find_root

from .._hunks import repo
from . import _entries


def main(hash: _entries.Hash) -> None:
    root = find_root()
    ref, title = _entries.resolve(root, hash)
    repo(root).out("stash", "drop", "-q", ref)
    print(f"dropped: {title}")
