"""Bump a pinned tool version in versions.toml."""

from typing import Annotated

from protocli import Complete
from setup.versions import bump as _bump, load


def main(tool: Annotated[str, Complete(lambda: sorted(load()))], tag: str) -> None:
    """Bump <tool> to <tag> in versions.toml."""
    _bump(tool, tag)
    print(f"Bumped {tool} to {tag}")
