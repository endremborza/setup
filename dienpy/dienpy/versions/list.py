"""List all pinned tool versions from versions.toml."""

from setup.versions import load

from dienpy._out import table


def main() -> None:
    rows = [(tv.name, tv.tag, tv.source, tv.checked) for tv in load().values()]
    print(table(rows, ("tool", "tag", "source", "checked")))
