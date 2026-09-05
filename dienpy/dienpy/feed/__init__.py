"""Unattended agent queue: run prompts through claude whenever the usage windows have headroom."""

from protocli import Dispatcher

from ._loop import Job, Settings, schedule
from ._loop import run as run_jobs
from ._queue import RepoQueue, load_repo

__all__ = [
    "Job",
    "RepoQueue",
    "Settings",
    "load_repo",
    "run_jobs",
    "schedule",
]

_dispatcher = Dispatcher.from_package("dienpy.feed", prog="dienpy feed")
