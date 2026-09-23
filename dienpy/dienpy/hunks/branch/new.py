"""Create a patch branch from HEAD and commit the picked patches on it, in order.

In place, the current checkout switches to the new branch with its dirty files carried
along, so unpicked patches stay uncommitted there. `--worktree` builds the branch in a
sibling checkout (`../<repo>-<name>`) instead and moves the picked patches over, so the
current checkout stays on its branch — the shape an agent or a parallel branch needs.
"""

from pathlib import Path

from .. import _apply, _patches
from .._hunks import Hunk, repo
from ..patch import _current
from . import _ops


def _move_to_worktree(
    root: str,
    wt: Path,
    ids: list[str],
    message: str,
    live: list[Hunk],
    index: list[Hunk],
) -> str:
    """Carry staged hunks over as a stash — the stash list is shared, git handles every file kind."""
    _apply.stage_alone(root, ids, live, index)
    repo(root).out("stash", "push", "--staged", "-q", "-m", _apply.GRAVEYARD + "moving")
    repo(str(wt)).out("stash", "pop", "--index", "-q")
    return _apply.commit_staged(str(wt), message)


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
        repo(root).out("worktree", "add", "-q", str(wt), "-b", name)
        print(f"worktree {wt}")
    else:
        repo(root).out("switch", "-q", "-c", name)
    for n, patch in enumerate(picked):
        if n:
            cur.reparse()
        ids = cur.ids((patch["id"],), live_only=True)
        msg = _patches.message(patch)
        short = (
            _move_to_worktree(root, wt, ids, msg, cur.hunks, cur.index)
            if wt
            else _apply.commit(root, ids, msg, cur.hunks, cur.index)
        )
        print(f"{short} {patch['title']}")
    print(f"on {name}" if not wt else f"{name} in {wt}")
