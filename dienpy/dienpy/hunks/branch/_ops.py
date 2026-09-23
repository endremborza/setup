"""Branch-level git calls shared by the branch commands.

Archived history lives under `refs/landed/<name>` and `refs/dropped/<name>`: outside
`refs/heads`, so `git branch` does not list it and `git push` never sends it, while
`git log --all` and `git log refs/landed/<name>` still reach it.
"""

from pathlib import Path
from typing import Annotated

from protocli import Complete

from dienpy._git import find_root

from .. import _apply
from .._hunks import repo

LEFTOVERS = _apply.GRAVEYARD + "leftovers of "
NOTES_REF = "landed"


def default(root: str) -> str:
    origin = repo(root).out(
        "symbolic-ref",
        "-q",
        "--short",
        "refs/remotes/origin/HEAD",
        ok_codes=(0, 1),
    )
    if origin:
        return origin.split("/", 1)[1]
    for name in ("main", "master"):
        if exists(root, name):
            return name
    raise SystemExit("no default branch: neither main nor master exists")


def current(root: str) -> str:
    return repo(root).out("branch", "--show-current")


def names(root: str) -> list[str]:
    return (
        repo(root)
        .out("for-each-ref", "--format=%(refname:short)", "refs/heads")
        .split()
    )


def _ref_exists(root: str, ref: str) -> bool:
    return repo(root).run("rev-parse", "-q", "--verify", ref).returncode == 0


def exists(root: str, name: str) -> bool:
    return _ref_exists(root, f"refs/heads/{name}")


def sha(root: str, rev: str) -> str:
    return repo(root).out("rev-parse", "--verify", rev)


def dirty(root: str) -> bool:
    return bool(repo(root).out("status", "--porcelain", "--untracked-files=all"))


def worktree_of(root: str, name: str) -> Path | None:
    """The other checkout holding `name`, if any."""
    path = None
    for line in repo(root).out("worktree", "list", "--porcelain").split("\n"):
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :])
        elif line == f"branch refs/heads/{name}" and path:
            return path if path.resolve() != Path(root).resolve() else None
    return None


def guard_worktree(root: str, name: str) -> Path | None:
    """`name`'s worktree, refused while it holds uncommitted work that removing it would lose."""
    wt = worktree_of(root, name)
    if wt and dirty(str(wt)):
        raise SystemExit(
            f"worktree {wt} has uncommitted changes — commit, stash or discard them first"
        )
    return wt


def stash_leftovers(root: str, name: str) -> bool:
    """Everything uncommitted, untracked included, goes to one stash; False when clean."""
    if not dirty(root):
        return False
    repo(root).out("stash", "push", "-u", "-q", "-m", LEFTOVERS + name)
    return True


def pop_leftovers(root: str) -> None:
    repo(root).out("stash", "pop", "--index", "-q")


def archive(root: str, namespace: str, name: str) -> tuple[str, str]:
    """The tip and the ref it went under: a reused branch name gets a numbered ref, so
    earlier landings stay reachable."""
    tip = sha(root, f"refs/heads/{name}")
    ref, n = name, 1
    while _ref_exists(root, f"refs/{namespace}/{ref}"):
        n += 1
        ref = f"{name}-{n}"
    repo(root).out("update-ref", f"refs/{namespace}/{ref}", tip)
    return tip, ref


def remove(root: str, name: str) -> None:
    wt = guard_worktree(root, name)
    r = repo(root)
    if wt:
        r.out("worktree", "remove", str(wt))
    r.out("branch", "-q", "-D", name)


def note(root: str, commit: str, text: str) -> None:
    repo(root).out("notes", f"--ref={NOTES_REF}", "add", "-f", "-m", text, commit)


def log(root: str, onto: str, name: str, *fmt: str) -> str:
    return repo(root).out("log", *fmt, f"{onto}..{name}")


def stat(root: str, onto: str, name: str) -> str:
    return repo(root).out("diff", "--stat", f"{onto}...{name}")


def summary(root: str, onto: str, name: str) -> str:
    return "\n".join(
        s for s in (log(root, onto, name, "--oneline"), stat(root, onto, name)) if s
    )


def _completions() -> list[str]:
    try:
        return names(find_root())
    except SystemExit:
        return []


BranchName = Annotated[str, Complete(_completions)]
