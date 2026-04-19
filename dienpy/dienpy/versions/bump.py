import sys

from setup.versions import bump, load


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 2 or args[0] in ("-h", "--help"):
        print("Usage: dienpy versions bump <tool> <tag>")
        print(f"Tools: {', '.join(load())}")
        return
    tool, tag = args
    bump(tool, tag)
    print(f"Bumped {tool} to {tag}")


def get_completions(args: list[str]) -> list[str]:
    if not args:
        return list(load())
    return []
