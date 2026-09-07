"""Stage, unstage, discard, bury, commit or move patches of the current run, or single hunks by id."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.hunks.patch", prog="dienpy hunks patch")
