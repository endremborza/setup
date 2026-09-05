"""Work prompt queues (or an explicit list of prompts / a command) through unattended claude sessions as usage headroom allows."""

import dataclasses
from pathlib import Path
from typing import Annotated

from protocli import FILES

from .._git import find_root
from ..claude import _gate
from ..constants import LOGS_DIR
from . import _queue
from ._loop import Job, Settings, run, schedule
from ._queue import RepoQueue


def repo_queues(repos: list[str]) -> list[RepoQueue]:
    """RepoQueues for the given roots; none given = the repo around the cwd."""
    roots = [Path(r).resolve() for r in repos] or [Path(find_root())]
    return [_queue.load_repo(r) for r in roots]


def main(
    *prompts: Annotated[str, FILES],
    cmd: str = "",
    repos: list[str] = [],
    profiles: list[str] = [],
    hunks: list[str] | None = None,
    need: float = _queue.DEFAULT_NEED,
    session_ceiling: float = 97.0,
    week_below: float = 97.0,
    scoped_below: float = 97.0,
    log_dir: Annotated[str, FILES] = "",
    poll: int = 600,
    timeout: int = 10800,
    repeat: bool = False,
    once: bool = False,
    dry_run: bool = False,
) -> None:
    """Scheduler mode (no prompts, no --cmd): pick the best eligible prompt across the
    queues of --repos (default: this repo) — priority, then the repo that waited longest —
    run it, record `.cril/prompts/state.toml`, repeat; --once stops after one.

    Explicit mode: the given prompt files and/or --cmd run in order in this repo (--repeat
    cycles them), gated the same way: a job starts when its profile's weekly windows are
    under the thresholds and session% + --need stays under --session-ceiling. --hunks and
    --profiles override the repo's `.cril/feed.toml` (`--hunks ""` skips the regroup
    close). Logs land in --log-dir/<repo> (default $LOGS_DIR/feed).
    """
    settings = Settings(
        thresholds=_gate.Thresholds(session_ceiling, week_below, scoped_below),
        log_base=Path(log_dir) if log_dir else LOGS_DIR / "feed",
        poll=poll,
        timeout=timeout,
        repeat=repeat,
        once=once,
    )
    if not prompts and not cmd:
        queues = repo_queues(repos)
        if dry_run:
            from .list import show

            show(queues, settings, offline=False)
            return
        schedule(queues, settings)
        return
    if repos:
        raise SystemExit("--repos is scheduler mode; drop the prompt files / --cmd")
    repo = _queue.load_repo(Path(find_root()))
    if profiles:
        repo = dataclasses.replace(repo, profiles=tuple(profiles))
    if hunks is not None:
        repo = dataclasses.replace(repo, hunks=tuple(hunks))
    jobs = [Job(prompt=Path(p).resolve(), profiles=repo.profiles, need=need) for p in prompts]
    if cmd:
        jobs.append(Job(cmd=cmd, profiles=repo.profiles, need=need))
    missing = [str(j.prompt) for j in jobs if j.prompt is not None and not j.prompt.is_file()]
    if missing:
        raise SystemExit(f"prompt file(s) not found: {', '.join(missing)}")
    if dry_run:
        print(f"repo      {repo.root}\nhunks     {' '.join(repo.hunks) or '(skipped)'}\nprofiles  {', '.join(repo.profiles)}")
        for i, j in enumerate(jobs, 1):
            print(f"job {i:<5} {j}")
        return
    run(repo, jobs, settings)
