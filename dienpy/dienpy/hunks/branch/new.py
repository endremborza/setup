"""Create a patch branch from HEAD and commit the picked patches on it, in order.

In place, the current checkout switches to the new branch with its dirty files carried
along, so unpicked patches stay uncommitted there. `--worktree` builds the branch in a
sibling checkout (`../<repo>-<name>`) instead and moves the picked patches over, so the
current checkout stays on its branch — the shape an agent or a parallel branch needs.
"""

from pathlib import Path

from .. import _apply, _patches
from ..patch import _current
from . import _ops


def _move_to_worktree(root: str, wt: Path, ids: list[str], message: str) -> str:
    """Carry staged hunks over as a stash — the stash list is shared, git handles every file kind."""
    _apply.stage_alone(root, ids)
    _ops.git(root, "stash", "push", "--staged", "-q", "-m", _apply.GRAVEYARD + "moving")
    _ops.git(str(wt), "stash", "pop", "--index", "-q")
    _ops.git(str(wt), "commit", "-q", "-F", "-", stdin=message)
    return _ops.git(str(wt), "rev-parse", "--short", "HEAD")


def main(name: str, *patches: _patches.Target, worktree: bool = False) -> None:
    cur = _current.load()
    root = cur.root
    if not _ops.current(root):
        raise SystemExit("detached HEAD: check out a branch first")
    if _ops.exists(root, name):
        raise SystemExit(f"branch {name} already exists")
    picked = _patches.select(cur.patches, patches)
    wt = None
    if worktree:
        wt = Path(root).parent / f"{Path(root).name}-{name}"
        _ops.git(root, "worktree", "add", "-q", str(wt), "-b", name)
        print(f"worktree {wt}")
    else:
        _ops.git(root, "switch", "-q", "-c", name)
    for patch in picked:
        ids = [i for i in patch["hunks"] if i in cur.live]
        if not ids:
            raise SystemExit(f"nothing left to commit in: {patch['title']}")
        msg = _patches.message(patch)
        short = (
            _move_to_worktree(root, wt, ids, msg)
            if wt
            else _apply.commit(root, ids, msg)
        )
        print(f"{short} {patch['title']}")
    print(f"on {name}" if not wt else f"{name} in {wt}")
