"""Drop a patch branch without landing it: history archived under refs/dropped, branch and worktree removed."""

from .. import _hunks
from . import _ops


def main(name: str) -> None:
    root = _hunks.git_root()
    if not _ops.exists(root, name):
        raise SystemExit(f"no branch {name}")
    if _ops.current(root) == name:
        _ops.git(root, "switch", "-q", _ops.default(root))
    tip = _ops.archive(root, "dropped", name)
    _ops.remove(root, name)
    print(f"dropped {name} ({tip[:7]}; history: refs/dropped/{name})")
