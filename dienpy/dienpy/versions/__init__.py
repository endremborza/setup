"""Pinned tool version management (check, bump, list, upgrade-system)."""
from dienpy.cli import Dispatcher

_dispatcher = Dispatcher(
    prog="dienpy versions",
    commands={
        "list": "dienpy.versions.list",
        "check": "dienpy.versions.check",
        "bump": "dienpy.versions.bump",
        "upgrade-system": "dienpy.versions.upgrade_system",
    },
)
