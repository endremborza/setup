"""List all pinned tool versions from versions.toml."""

from dienraw.out import table
from setup.versions import load


def main() -> None:
    rows = [(tv.name, tv.tag, tv.source, tv.checked) for tv in load().values()]
    print(table(rows, ("tool", "tag", "source", "checked")))
