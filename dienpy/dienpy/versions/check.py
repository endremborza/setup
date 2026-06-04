"""Check pinned tool versions against their latest releases."""

import os

from setup.versions import check_all


def main(*, token: str | None = None) -> None:
    """Check pinned tool versions against their latest releases (defaults --token to $GITHUB_TOKEN)."""
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("warning: no GITHUB_TOKEN — rate limited to 60 req/hr")
    print(f"{'Tool':<14} {'Pinned':<16} {'Latest':<16} {'Status'}")
    for tv, latest in check_all(token):
        status = "OK" if tv.tag == latest else f"UPDATE ({tv.tag} -> {latest})"
        print(f"{tv.name:<14} {tv.tag:<16} {latest:<16} {status}")
