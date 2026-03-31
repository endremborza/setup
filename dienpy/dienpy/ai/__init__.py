import importlib
import sys

_SUBCOMMANDS = ["models", "commit"]


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(f"Usage: dienpy ai <subcommand> [args...]\nSubcommands: {', '.join(_SUBCOMMANDS)}")
        return

    subcmd, *rest = args
    if subcmd not in _SUBCOMMANDS:
        raise SystemExit(f"Unknown subcommand '{subcmd}'. Available: {', '.join(_SUBCOMMANDS)}")

    mod = importlib.import_module(f"dienpy.ai.{subcmd}")
    sys.argv = [f"dienpy ai {subcmd}", *rest]
    mod.main()


def get_completions(args: list[str]) -> list[str]:
    if not args or args[0] not in _SUBCOMMANDS:
        return _SUBCOMMANDS
    subcmd, *rest = args
    try:
        mod = importlib.import_module(f"dienpy.ai.{subcmd}")
    except ImportError:
        return []
    if hasattr(mod, "get_completions"):
        return mod.get_completions(rest)
    return []
