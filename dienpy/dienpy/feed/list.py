"""List every queued prompt across repos with its metadata, history and current verdict."""

import datetime

from .._out import table
from ..claude import _gate
from ..claude.usage import windows
from . import _queue
from ._loop import Settings, choose, strict
from ._queue import RepoQueue


def show(queues: list[RepoQueue], settings: Settings, *, offline: bool) -> None:
    cands = _queue.collect(queues)
    if not cands:
        print(
            "no prompts with frontmatter under "
            + ", ".join(str(q.prompts) for q in queues)
        )
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    verdicts: dict[tuple[str, str], str] = {}
    if offline:
        for c in cands:
            verdicts[(c.repo.name, c.name)] = _queue.lifecycle(c, now) or "eligible"
    else:
        for c, why in choose(cands, settings, windows, now, fetch=strict).verdicts:
            verdicts[(c.repo.name, c.name)] = why
    rows = [
        (
            f"{c.repo.name}/{c.name}",
            c.meta.mode,
            c.meta.priority,
            f"{c.need:.0f}",
            ",".join(c.profiles),
            f"{c.state.last.astimezone():%m-%d %H:%M}" if c.state.last else "-",
            verdicts.get((c.repo.name, c.name), ""),
        )
        for c in cands
    ]
    head = ("prompt", "mode", "pri", "need", "profiles", "last", "verdict")
    print(table(rows, head, align="<<>>"))


def main(*repos: str, offline: bool = False) -> None:
    """One line per prompt: mode, priority, need, profiles, last run, and why it does or does not run now.

    --offline judges lifecycle only (no usage fetch); repos default to the one around the cwd.
    """
    show(
        _queue.repo_queues(list(repos)),
        Settings(thresholds=_gate.Thresholds()),
        offline=offline,
    )
