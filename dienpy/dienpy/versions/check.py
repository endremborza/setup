"""Check pinned tool versions against their latest releases."""

import os

from setup.versions import check_all, number

from dienpy._out import table


def main(*, token: str | None = None) -> None:
    """Check pinned tool versions against their latest releases (defaults --token to $GITHUB_TOKEN)."""
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("warning: no GITHUB_TOKEN — rate limited to 60 req/hr")
    rows = [
        (
            tv.name,
            tv.tag,
            latest,
            "OK"
            if number(tv.tag) == number(latest)
            else f"UPDATE ({tv.tag} -> {latest})",
        )
        for tv, latest in check_all(token)
    ]
    print(table(rows, ("tool", "pinned", "latest", "status")))
