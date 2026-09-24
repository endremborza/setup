"""Pinned tool version management (list, check upstream, bump)."""

from protocli import Dispatcher

_dispatcher = Dispatcher(
    prog="dienpy versions",
    commands={
        "list": "dienpy.versions.list",
        "check": "dienpy.versions.check",
        "bump": "dienpy.versions.bump",
    },
)
