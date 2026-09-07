"""Branch-level git calls shared by the branch commands.

Archived history lives under `refs/landed/<name>` and `refs/dropped/<name>`: outside
`refs/heads`, so `git branch` does not list it and `git push` never sends it, while
`git log --all` and `git log refs/landed/<name>` still reach it.
"""

from pathlib import Path

from dienpy._git import Repo

from .. import _apply, _hunks

LEFTOVERS = _apply.GRAVEYARD + "leftovers of "
NOTES_REF = "landed"


def git(
    root: str, *args: str, ok_codes: tuple[int, ...] = (0,), stdin: str | None = None
) -> str:
    return _hunks._git(root, list(args), ok_codes=ok_codes, stdin=stdin).strip()


def attempt(root: str, *args: str) -> bool:
    """A git call whose failure is an outcome, not an error."""
    return Repo(root, cfg=_hunks._GIT_CFG).run(*args).returncode == 0


def default(root: str) -> str:
    origin = git(
        root,
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
    return git(root, "branch", "--show-current")


def exists(root: str, name: str) -> bool:
    return bool(
        git(root, "rev-parse", "-q", "--verify", f"refs/heads/{name}", ok_codes=(0, 1))
    )


def sha(root: str, rev: str) -> str:
    return git(root, "rev-parse", "--verify", rev)


def dirty(root: str) -> bool:
    return bool(git(root, "status", "--porcelain", "--untracked-files=all"))


def worktree_of(root: str, name: str) -> Path | None:
    path = None
    for line in git(root, "worktree", "list", "--porcelain").split("\n"):
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :])
        elif line == f"branch refs/heads/{name}" and path:
            return path if path.resolve() != Path(root).resolve() else None
    return None


def stash_leftovers(root: str, name: str) -> bool:
    """Everything uncommitted, untracked included, goes to one stash; False when clean."""
    if not dirty(root):
        return False
    git(root, "stash", "push", "-u", "-q", "-m", LEFTOVERS + name)
    return True


def pop_leftovers(root: str) -> None:
    git(root, "stash", "pop", "-q")


def archive(root: str, namespace: str, name: str) -> str:
    tip = sha(root, f"refs/heads/{name}")
    git(root, "update-ref", f"refs/{namespace}/{name}", tip)
    return tip


def remove(root: str, name: str) -> None:
    wt = worktree_of(root, name)
    if wt:
        git(root, "worktree", "remove", "--force", str(wt))
    git(root, "branch", "-q", "-D", name)


def note(root: str, commit: str, text: str) -> None:
    git(root, "notes", f"--ref={NOTES_REF}", "add", "-f", "-m", text, commit)


def summary(root: str, onto: str, name: str) -> str:
    log = git(root, "log", "--oneline", f"{onto}..{name}")
    stat = git(root, "diff", "--stat", f"{onto}...{name}")
    return "\n".join(s for s in (log, stat) if s)
