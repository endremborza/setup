"""Check out a patch branch in this worktree (git's own refusal when local changes would be lost)."""

from dienpy._git import find_root

from .._hunks import repo
from . import _ops


def main(name: _ops.BranchName) -> None:
    root = find_root()
    if not _ops.exists(root, name):
        raise SystemExit(f"no branch {name}")
    wt = _ops.worktree_of(root, name)
    if wt:
        raise SystemExit(f"{name} is checked out in {wt}")
    repo(root).out("switch", "-q", name)
    print(f"on {name}")
