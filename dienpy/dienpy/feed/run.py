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
from .list import show

_T = _gate.Thresholds()


def main(
    *prompts: Annotated[str, FILES],
    cmd: str = "",
    repos: list[str] = [],
    profiles: list[str] = [],
    hunks: list[str] | None = None,
    need: float | None = None,
    session_ceiling: float = _T.session,
    week_below: float = _T.weekly,
    scoped_below: float = _T.scoped,
    log_dir: Annotated[str, FILES] = "",
    poll: int = Settings.poll,
    timeout: int | None = None,
    repeat: bool = False,
    once: bool = False,
    commit: bool = False,
    dry_run: bool = False,
) -> None:
    """Scheduler mode (no prompts, no --cmd): pick the best eligible prompt across the
    queues of --repos (default: this repo) — priority, then the repo that waited longest —
    run it, record `.cril/prompts/state.toml`, repeat; --once stops after one.

    Explicit mode: the given prompt files and/or --cmd run in order in this repo (--repeat
    cycles them), gated the same way: a job starts when its profile's weekly windows are
    under the thresholds and session% + need stays under --session-ceiling. Each prompt's
    frontmatter supplies its need, profiles and commit rule; --need, --profiles and
    --commit override them, --hunks the repo's `.cril/feed.toml` (`--hunks ""` skips the
    regroup close). --timeout overrides the profile's. Logs land in --log-dir/<repo>
    (default $LOGS_DIR/feed).
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
        queues = _queue.repo_queues(repos)
        if dry_run:
            show(queues, settings, offline=False)
            return
        schedule(queues, settings)
        return
    if repos:
        raise SystemExit("--repos is scheduler mode; drop the prompt files / --cmd")
    repo = _queue.load_repo(Path(find_root()))
    if hunks is not None:
        repo = dataclasses.replace(repo, hunks=tuple(hunks))
    jobs = []
    for p in prompts:
        path = Path(p).resolve()
        if not path.is_file():
            raise SystemExit(f"prompt file not found: {p}")
        meta = _queue.meta_of(path)
        jobs.append(
            Job(
                prompt=path,
                profiles=tuple(profiles) or meta.profiles or repo.profiles,
                need=meta.need if need is None else need,
                commit=commit or meta.commit,
            )
        )
    if cmd:
        jobs.append(
            Job(
                cmd=cmd,
                profiles=tuple(profiles) or repo.profiles,
                need=_queue.DEFAULT_NEED if need is None else need,
            )
        )
    if dry_run:
        print(f"repo      {repo.root}\nhunks     {' '.join(repo.hunks) or '(skipped)'}")
        for i, j in enumerate(jobs, 1):
            print(
                f"job {i:<5} {j}  profiles={','.join(j.profiles)} need={j.need:.0f} commit={j.commit}"
            )
        return
    run(repo, jobs, settings)
