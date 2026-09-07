"""Patch assembly from hunk ids, and the git calls that stage, unstage, discard, bury and commit them.

The index and the worktree diff are two views of one change, and hunk ids agree only
where the views agree. A staged `git mv` is a whole-file entry in the index while the
worktree diff folds the move into the renamed file's content hunks under the new path:
patches for such a file are rebased onto the new path, the only one the index still
has, and the commit guard skips the move itself.
"""

from . import _hunks
from ._hunks import Hunk

GRAVEYARD = "regroup: "


def by_id(hunks: list[Hunk]) -> dict[str, Hunk]:
    return {h.id: h for h in hunks}


def rename_source(h: Hunk) -> str | None:
    for line in h.header.split("\n"):
        if line.startswith("rename from "):
            return line[len("rename from ") :]
    return None


def staged_renames(index: list[Hunk]) -> set[str]:
    return {h.path for h in index if rename_source(h)}


def _rebase_header(header: str, path: str) -> str:
    out = []
    for line in header.split("\n"):
        if line.startswith("diff --git "):
            out.append(f"diff --git a/{path} b/{path}")
        elif line.startswith("--- a/"):
            out.append(f"--- a/{path}")
        elif not line.startswith(("similarity index ", "rename from ", "rename to ")):
            out.append(line)
    return "\n".join(out)


def _split(
    hunks: list[Hunk], ids: list[str], renamed: set[str]
) -> tuple[str | None, list[str]]:
    """Patch text for the content hunks among `ids` (file header once per file), and the
    paths of the whole-file entries, which git handles by path."""
    sel = set(ids)
    unknown = sel - {h.id for h in hunks}
    if unknown:
        raise SystemExit(f"unknown hunk id(s): {', '.join(sorted(unknown))}")
    patch: list[str] = []
    paths: list[str] = []
    seen_header: set[str] = set()

    def add_path(p: str | None) -> None:
        if p and p not in paths:
            paths.append(p)

    for h in hunks:
        if h.id not in sel:
            continue
        if h.kind == "hunk":
            if h.header not in seen_header:
                seen_header.add(h.header)
                patch.append(
                    _rebase_header(h.header, h.path) if h.path in renamed else h.header
                )
            patch.append(h.text)
        else:
            add_path(h.path)
            add_path(rename_source(h))
    return ("\n".join(patch) + "\n") if patch else None, paths


def _apply(root: str, patch: str, *flags: str) -> None:
    _hunks._git(root, ["apply", *flags, "--whitespace=nowarn", "-"], stdin=patch)


def stage(root: str, ids: list[str]) -> int:
    """Stage the live hunks among `ids` that the index does not hold yet."""
    live = _hunks.parse(root)
    index = _hunks.parse(root, staged=True)
    staged = by_id(index)
    todo = [i for i in ids if i not in staged]
    patch, paths = _split(live, todo, staged_renames(index))
    if patch:
        _apply(root, patch, "--cached")
    if paths:
        _hunks._git(root, ["add", "--", *paths])
    return len(todo)


def unstage(root: str, ids: list[str]) -> int:
    index = _hunks.parse(root, staged=True)
    held = by_id(index)
    todo = [i for i in ids if i in held]
    patch, paths = _split(index, todo, staged_renames(index))
    if patch:
        _apply(root, patch, "--cached", "--reverse")
    if paths:
        _hunks._git(root, ["restore", "--staged", "--", *paths])
    return len(todo)


def discard(root: str, ids: list[str]) -> int:
    """Return the hunks to their HEAD state in both the index and the worktree."""
    unstage(root, ids)
    live = _hunks.parse(root)
    recs = by_id(live)
    content = [i for i in ids if recs[i].kind == "hunk"]
    patch, _ = _split(live, content, staged_renames(_hunks.parse(root, staged=True)))
    if patch:
        _apply(root, patch, "--reverse")
    clean = [recs[i].path for i in ids if recs[i].kind == "untracked"]
    restore: list[str] = []
    for i in ids:
        if recs[i].kind == "file":
            restore += [p for p in (recs[i].path, rename_source(recs[i])) if p]
    if restore:
        _hunks._git(
            root, ["restore", "--source=HEAD", "--staged", "--worktree", "--", *restore]
        )
    if clean:
        _hunks._git(root, ["clean", "-f", "--", *clean])
    return len(ids)


def guard_foreign(root: str, ids: list[str]) -> None:
    """The index may hold nothing beyond `ids` except a staged rename, which is
    index-side noise the worktree diff folds into content hunks."""
    sel = set(ids)
    for h in _hunks.parse(root, staged=True):
        if h.id not in sel and not (h.kind == "file" and rename_source(h)):
            raise SystemExit(
                f"index contains changes outside the patch ({h.id} {h.path}) — "
                "commit or unstage those first"
            )


def bury(root: str, ids: list[str], title: str) -> None:
    stage(root, ids)
    guard_foreign(root, ids)
    _hunks._git(root, ["stash", "push", "--staged", "-m", GRAVEYARD + title])


def commit(root: str, ids: list[str], message: str) -> str:
    """Stage `ids`, refuse foreign index content, commit; returns the short hash."""
    stage(root, ids)
    guard_foreign(root, ids)
    _hunks._git(root, ["commit", "-q", "-F", "-"], stdin=message)
    return _hunks._git(root, ["rev-parse", "--short", "HEAD"]).strip()
