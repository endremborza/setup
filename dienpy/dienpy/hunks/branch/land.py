"""Land a patch branch: one squashed commit on the default branch, history archived under refs/landed.

The message is written before anything moves: `--message` verbatim, a single commit's
message as is, otherwise the model rewrites the branch log into one message. Leftover
uncommitted changes are stashed around the switch and popped after. A squash that
conflicts is undone and reported — merge the default branch into the patch branch and
land again. `--split` partitions the squashed diff and commits patch by patch instead of
once, so a messy branch lands as a few clean commits.
"""

from typing import Literal

from ... import ai
from .. import _apply, _cache, _config, _engine, _hunks, _patches, _prompt
from . import _ops

_SYSTEM = """\
Write ONE git commit message for the squashed landing of the branch below.

Rules:
- Output ONLY the message: a subject line (<= 72 chars) in the style of the recent subjects, a blank line, then a body saying what changed and why
- Describe the net result of the branch, not its commit-by-commit history
"""


def _message(root: str, onto: str, name: str) -> str:
    log = _ops.git(root, "log", "--reverse", "--format=%B", f"{onto}..{name}")
    if int(_ops.git(root, "rev-list", "--count", f"{onto}..{name}")) == 1:
        return log.strip() + "\n"
    backend = ai.resolve("commit", ai.Need(), profile="")
    user = (
        f"{_prompt.message_context(root)}\n\nBranch {name}, commits oldest first:\n{log}\n\n"
        f"Diff stat:\n{_ops.git(root, 'diff', '--stat', f'{onto}...{name}')}"
    )
    return (
        str(ai.send(backend, _SYSTEM, user, temperature=0.2, cwd=root)).strip() + "\n"
    )


def _split(root: str, granularity: str, auth: str | None) -> list[str]:
    _ops.git(root, "reset", "-q")
    hunks = _hunks.parse(root)
    config = _config.resolve((granularity,), _cache.last_config(root))
    backend = _engine.backend_for(config, auth)
    patches = _patches.mint(_engine.partition(root, hunks, config, backend))
    return [_apply.commit(root, p["hunks"], _patches.message(p)) for p in patches]


def main(
    name: str = "",
    *,
    onto: str = "",
    split: Literal["loose", "normal", "granular"] | None = None,
    message: str = "",
    auth: Literal["login", "env"] | None = None,
) -> None:
    root = _hunks.git_root()
    onto = onto or _ops.default(root)
    name = name or _ops.current(root)
    if not name or name == onto:
        raise SystemExit(f"name the patch branch to land onto {onto}")
    if not _ops.exists(root, name):
        raise SystemExit(f"no branch {name}")
    tip = _ops.sha(root, name)
    base = _ops.sha(root, onto)
    msg = message.rstrip() + "\n" if message else _message(root, onto, name)

    before = _ops.current(root)
    stashed = _ops.stash_leftovers(root, name)
    if before != onto:
        _ops.git(root, "switch", "-q", onto)
    if not _ops.attempt(root, "merge", "--squash", "-q", name):
        _ops.git(root, "reset", "-q", "--merge")
        if before != onto:
            _ops.git(root, "switch", "-q", before)
        if stashed:
            _ops.pop_leftovers(root)
        raise SystemExit(
            f"squashing {name} onto {onto} conflicts — merge {onto} into {name}, then land again"
        )
    if split:
        try:
            landings = _split(root, split, auth)
        except SystemExit as e:
            where = f"; leftovers in stash '{_ops.LEFTOVERS}{name}'" if stashed else ""
            raise SystemExit(
                f"{e}\nsquashed diff left uncommitted on {onto}{where}"
            ) from None
    else:
        _ops.git(root, "commit", "-q", "-F", "-", stdin=msg)
        landings = [_ops.git(root, "rev-parse", "--short", "HEAD")]
    if _ops.git(root, "merge-base", base, tip) == base:
        landed_tree = _ops.git(root, "rev-parse", "HEAD^{tree}")
        if landed_tree != _ops.git(root, "rev-parse", f"{tip}^{{tree}}"):
            if stashed:
                _ops.pop_leftovers(root)
            raise SystemExit(
                f"landing tree differs from {name} — inspect before pushing"
            )
    _ops.archive(root, "landed", name)
    for c in landings:
        _ops.note(root, c, f"branch: {name}\ntip: {tip}")
    _ops.remove(root, name)
    if stashed:
        _ops.pop_leftovers(root)
    print(
        f"landed {name} onto {onto}: {' '.join(landings)}  (history: refs/landed/{name})"
    )
