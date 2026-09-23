"""Land a patch branch: one squashed commit on the default branch, history archived under refs/landed.

Every refusal comes before anything moves: the branch must have commits, its worktree
must be clean, the default branch must be checked out here, and a `--split` backend
must serve the need. The message is written next: `--message` verbatim, a single
commit's message as is, otherwise the model rewrites the branch log into one message.
Leftover uncommitted changes are stashed around the switch and popped after; a switch,
squash or commit that fails is undone, leftovers back in place. `--split` partitions the
squashed diff and commits patch by patch instead of once, so a messy branch lands as a
few clean commits.
"""

from typing import Literal

from dienpy._git import find_root

from ... import ai
from .. import _apply, _cache, _config, _engine, _hunks, _patches, _prompt
from .._hunks import repo
from . import _ops

_SYSTEM = """\
Write ONE git commit message for the squashed landing of the branch below.

Rules:
- Output ONLY the message: a subject line (<= 72 chars) in the style of the recent subjects, a blank line, then a body saying what changed and why
- Describe the net result of the branch, not its commit-by-commit history
"""


def _message(root: str, onto: str, name: str, count: int) -> str:
    log = _ops.log(root, onto, name, "--reverse", "--format=%B")
    if count == 1:
        return log.strip() + "\n"
    backend = ai.resolve("commit", ai.Need(), profile="")
    user = (
        f"{_prompt.message_context(root)}\n\nBranch {name}, commits oldest first:\n{log}\n\n"
        f"Diff stat:\n{_ops.stat(root, onto, name)}"
    )
    return (
        str(ai.send(backend, _SYSTEM, user, temperature=0.2, cwd=root)).strip() + "\n"
    )


def _split(root: str, config: _config.Config, backend: ai.Backend) -> list[str]:
    repo(root).out("reset", "-q")
    patches = _patches.mint(
        _engine.partition(root, _hunks.parse(root), config, backend)
    )
    out = []
    for p in patches:
        live, index = _hunks.parse(root), _hunks.parse(root, staged=True)
        out.append(_apply.commit(root, p["hunks"], _patches.message(p), live, index))
    return out


def main(
    name: _ops.BranchName = "",
    *,
    onto: str = "",
    split: Literal["loose", "normal", "granular"] | None = None,
    message: str = "",
    auth: Literal["login", "env"] | None = None,
) -> None:
    root = find_root()
    r = repo(root)
    onto = onto or _ops.default(root)
    name = name or _ops.current(root)
    if not name or name == onto:
        raise SystemExit(f"name the patch branch to land onto {onto}")
    if not _ops.exists(root, name):
        raise SystemExit(f"no branch {name}")
    elsewhere = _ops.worktree_of(root, onto)
    if elsewhere:
        raise SystemExit(f"{onto} is checked out in {elsewhere} — land from there")
    _ops.guard_worktree(root, name)
    count = int(r.out("rev-list", "--count", f"{onto}..{name}"))
    if not count:
        raise SystemExit(f"nothing to land: {name} has no commits beyond {onto}")
    tip = _ops.sha(root, name)
    base = _ops.sha(root, onto)
    plan: tuple[_config.Config, ai.Backend] | None = None
    if split:
        config = _config.resolve((split,), _cache.last_config(root))
        plan = (config, _engine.backend_for(config, auth))
    msg = message.rstrip() + "\n" if message else _message(root, onto, name, count)

    before = _ops.current(root)
    stashed = _ops.stash_leftovers(root, name)

    def undo(reason: str) -> SystemExit:
        r.run("reset", "-q", "--merge")
        if _ops.current(root) != before:
            r.out("switch", "-q", before)
        if stashed:
            _ops.pop_leftovers(root)
        return SystemExit(reason)

    if before != onto and r.run("switch", "-q", onto).returncode:
        raise undo(f"cannot switch to {onto} — commit or stash conflicting changes")
    if r.run("merge", "--squash", "-q", name).returncode:
        raise undo(
            f"squashing {name} onto {onto} conflicts — merge {onto} into {name}, then land again"
        )
    if plan:
        try:
            landings = _split(root, *plan)
        except SystemExit as e:
            where = f"; leftovers in stash '{_ops.LEFTOVERS}{name}'" if stashed else ""
            raise SystemExit(
                f"{e}\nsquashed diff left uncommitted on {onto}{where}"
            ) from None
    else:
        try:
            landings = [_apply.commit_staged(root, msg)]
        except SystemExit as e:
            raise undo(str(e)) from None
    if r.out("merge-base", base, tip) == base:
        landed_tree = r.out("rev-parse", "HEAD^{tree}")
        if landed_tree != r.out("rev-parse", f"{tip}^{{tree}}"):
            if stashed:
                _ops.pop_leftovers(root)
            raise SystemExit(
                f"landing tree differs from {name} — inspect before pushing"
            )
    _, ref = _ops.archive(root, "landed", name)
    for c in landings:
        _ops.note(root, c, f"branch: {name}\ntip: {tip}")
    _ops.remove(root, name)
    print(
        f"landed {name} onto {onto}: {' '.join(landings)}  (history: refs/landed/{ref})"
    )
    if stashed:
        try:
            _ops.pop_leftovers(root)
        except SystemExit as e:
            raise SystemExit(
                f"{e}\nleftovers stay stashed as '{_ops.LEFTOVERS}{name}'"
            ) from None
