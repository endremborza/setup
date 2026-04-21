"""Check pinned tool versions against their latest releases."""
import argparse
import os

from setup.versions import check_all


def main() -> None:
    parser = argparse.ArgumentParser(prog="dienpy versions check")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args()
    if not args.token:
        print("warning: no GITHUB_TOKEN — rate limited to 60 req/hr")
    print(f"{'Tool':<14} {'Pinned':<16} {'Latest':<16} {'Status'}")
    for tv, latest in check_all(args.token):
        status = "OK" if tv.tag == latest else f"UPDATE ({tv.tag} -> {latest})"
        print(f"{tv.name:<14} {tv.tag:<16} {latest:<16} {status}")


def get_completions(args: list[str]) -> list[str]:
    return [] if args else ["--token"]
