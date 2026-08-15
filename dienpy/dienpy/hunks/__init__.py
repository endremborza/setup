"""AI change-group analysis for git diffs — engine behind nvim's :Regroup."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.hunks", prog="dienpy hunks")
