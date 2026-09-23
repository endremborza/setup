"""Restore a graveyard entry: its index and worktree changes are applied as patches, so
other uncommitted edits to the same files stay put (which `git stash pop` refuses); the
entry is dropped once both applied, and a patch that no longer applies keeps it."""

from dienpy._git import Repo, find_root

from .._hunks import _DIFF, raw, repo
from . import _entries


def _apply(r: Repo, ref: str) -> None:
    # a stash commit's parents: ^1 the base, ^2 the index state, ^3 the untracked files
    index = raw(r, *_DIFF, "--binary", f"{ref}^", f"{ref}^2")
    worktree = raw(r, *_DIFF, "--binary", f"{ref}^", ref)
    parts = [(("--cached",), index), ((), worktree)]
    if r.run("rev-parse", "-q", "--verify", f"{ref}^3").returncode == 0:
        empty = r.out("hash-object", "-t", "tree", "/dev/null")
        parts.append(((), raw(r, *_DIFF, "--binary", empty, f"{ref}^3")))
    for flags, patch in parts:
        if patch:
            raw(r, "apply", "--check", *flags, "-", stdin=patch)
    for flags, patch in parts:
        if patch:
            raw(r, "apply", *flags, "-", stdin=patch)


def main(hash: _entries.Hash) -> None:
    root = find_root()
    ref, title = _entries.resolve(root, hash)
    r = repo(root)
    _apply(r, ref)
    r.out("stash", "drop", "-q", ref)
    print(f"restored: {title}")
