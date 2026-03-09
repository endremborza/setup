import importlib
import pkgutil
import sys

import dienpy


def _list_modules() -> list[str]:
    return [m.name for m in pkgutil.iter_modules(dienpy.__path__)]


def _handle_complete(argv: list[str]) -> None:
    if not argv:
        print("\n".join(_list_modules()))
        return

    module_name, *args = argv
    try:
        mod = importlib.import_module(f"dienpy.{module_name}")
    except ImportError:
        return

    if hasattr(mod, "get_completions"):
        results = mod.get_completions(args)
        if results:
            print("\n".join(results))


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(
            f"Usage: dienpy <module> [args...]\nModules: {', '.join(_list_modules())}"
        )
        return

    if args[0] == "--complete":
        _handle_complete(args[1:])
        return

    module_name, *rest = args
    try:
        mod = importlib.import_module(f"dienpy.{module_name}")
    except ImportError as e:
        print(f"Error: no module '{module_name}'", file=sys.stderr)
        raise e
        sys.exit(1)

    sys.argv = [f"dienpy {module_name}", *rest]
    mod.main()


if __name__ == "__main__":
    main()
