"""Patch branches: commit picked patches on a branch, land a squashed version on the default branch, archive the history."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.hunks.branch", prog="dienpy hunks branch")
