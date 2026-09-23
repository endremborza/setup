"""Drop a patch branch without landing it: history archived under refs/dropped, branch and worktree removed."""

from dienpy._git import find_root

from .._hunks import repo
from . import _ops


def main(name: _ops.BranchName) -> None:
    root = find_root()
    onto = _ops.default(root)
    if name == onto:
        raise SystemExit(f"{name} is the default branch")
    if not _ops.exists(root, name):
        raise SystemExit(f"no branch {name}")
    _ops.guard_worktree(root, name)
    if _ops.current(root) == name:
        repo(root).out("switch", "-q", onto)
    tip, ref = _ops.archive(root, "dropped", name)
    _ops.remove(root, name)
    print(f"dropped {name} ({tip[:7]}; history: refs/dropped/{ref})")
