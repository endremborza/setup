"""Bump a pinned tool version in versions.toml."""

from setup.versions import bump as _bump, load


def main(tool: str, tag: str) -> None:
    """Bump <tool> to <tag> in versions.toml."""
    _bump(tool, tag)
    print(f"Bumped {tool} to {tag}")


def get_completions(args: list[str]) -> list[str]:
    if not args:
        return list(load())
    return []
