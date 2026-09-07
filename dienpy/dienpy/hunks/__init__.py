"""Partition a diff into patches, land them as commits or patch branches — engine behind nvim's :Regroup."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.hunks", prog="dienpy hunks")
