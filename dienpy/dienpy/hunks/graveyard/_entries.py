"""Stashes under the regroup prefix, addressed by commit hash: a `stash@{n}` index
shifts as entries come and go, the hash does not."""

from typing import Annotated

from protocli import Complete

from dienpy._git import find_root

from .._apply import GRAVEYARD
from .._hunks import repo


def entries(root: str) -> list[dict]:
    """Newest first: `{hash, ref, age, title}`, the title without the prefix."""
    rows = repo(root).out("stash", "list", "--format=%H%x09%gd%x09%cr%x09%s")
    out = []
    for row in rows.split("\n"):
        if not row:
            continue
        hash, ref, age, subject = row.split("\t", 3)
        message = subject.split(": ", 1)[-1]  # "On <branch>: <message>"
        if message.startswith(GRAVEYARD):
            title = message[len(GRAVEYARD) :]
            out.append({"hash": hash, "ref": ref, "age": age, "title": title})
    return out


def resolve(root: str, hash: str) -> tuple[str, str]:
    """`(stash@{n}, title)` of the entry `hash` (a unique prefix will do) names now."""
    found = [e for e in entries(root) if e["hash"].startswith(hash)]
    if len(found) != 1:
        state = "ambiguous" if found else "no"
        raise SystemExit(f"{state} graveyard entry {hash}")
    return found[0]["ref"], found[0]["title"]


def _completions() -> list[str]:
    try:
        return [e["hash"][:7] for e in entries(find_root())]
    except SystemExit:
        return []


Hash = Annotated[str, Complete(_completions)]
