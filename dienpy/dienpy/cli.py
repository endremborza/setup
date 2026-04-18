"""One class. Command values are either module paths (``str``) for lazy import,
or callables for direct invocation. Module-backed commands support completion
chaining via ``mod.get_completions()``.
"""

import importlib
import pkgutil
import sys
from collections.abc import Callable
from types import ModuleType

_SKIP = frozenset({"__main__", "__init__", "constants", "cli"})


def handle_help(prog: str, summary: str = "") -> bool:
    """Return True (and print help) if ``--help`` / ``-h`` is the first arg.

    Call at the top of a leaf ``main()`` that doesn't use argparse, so
    ``<tool> ... --help`` prints a usage line instead of executing the command.
    """
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(f"Usage: {prog} [args...]")
        if summary:
            print(summary)
        return True
    return False


class Dispatcher:
    """Unified CLI dispatcher.

    Construct directly with an explicit command dict, or via ``from_package``
    for auto-discovery. Dict values that are ``str`` are treated as module
    paths (lazy-imported on dispatch); callables are invoked directly.
    """

    def __init__(self, prog: str, commands: dict[str, str | Callable[[], None]]):
        self._prog = prog
        self._commands = commands

    @classmethod
    def from_package(cls, package: str, prog: str | None = None) -> "Dispatcher":
        mod = importlib.import_module(package)
        commands: dict[str, str | Callable[[], None]] = {
            m.name: f"{package}.{m.name}"
            for m in pkgutil.iter_modules(mod.__path__)
            if m.name not in _SKIP and not m.name.startswith("_")
        }
        return cls(prog=prog or package.rsplit(".", 1)[-1], commands=commands)

    def commands(self) -> list[str]:
        return sorted(self._commands)

    def tree(self) -> dict[str, dict | None]:
        """Return nested command tree. Leaves are ``None``."""
        result: dict[str, dict | None] = {}
        for cmd in self.commands():
            target = self._commands[cmd]
            if callable(target):
                result[cmd] = None
                continue
            try:
                mod = importlib.import_module(target)
            except ImportError:
                result[cmd] = None
                continue
            child = getattr(mod, "_dispatcher", None)
            result[cmd] = child.tree() if child is not None else None
        return result

    def run(self) -> None:
        argv = sys.argv[1:]
        cmds = self.commands()

        if not argv or argv[0] in ("-h", "--help"):
            print(f"Usage: {self._prog} <command> [args...]")
            print(f"Commands: {', '.join(cmds)}")
            return

        if argv[0] == "--complete":
            for line in self.get_completions(argv[1:]):
                print(line)
            return

        cmd, *rest = argv
        if cmd not in cmds:
            print(f"Unknown command: {cmd}", file=sys.stderr)
            raise SystemExit(1)

        run_fn, _ = self._load(cmd)
        sys.argv = [f"{self._prog} {cmd}", *rest]
        run_fn()

    def get_completions(self, args: list[str]) -> list[str]:
        cmds = self.commands()
        if not args:
            return cmds
        cmd, *rest = args
        if cmd not in cmds:
            return []
        _, completer = self._load(cmd)
        return completer(rest) if completer else []

    def _load(
        self, cmd: str
    ) -> tuple[Callable[[], None], Callable[[list[str]], list[str]] | None]:
        """Returns ``(run_fn, complete_fn | None)``.

        For module-backed commands, checks for a ``_dispatcher`` attribute first
        (nested Dispatcher), then falls back to ``main`` / ``get_completions``.
        Callable targets are wrapped so ``--help`` prints the docstring.
        """
        target = self._commands[cmd]
        if callable(target):
            return self._wrap_callable(cmd, target), None
        mod = importlib.import_module(target)
        child = getattr(mod, "_dispatcher", None)
        if child is not None:
            return child.run, child.get_completions
        return mod.main, getattr(mod, "get_completions", None)

    def _wrap_callable(self, cmd: str, fn: Callable[[], None]) -> Callable[[], None]:
        prog = f"{self._prog} {cmd}"

        def wrapped() -> None:
            if sys.argv[1:2] in (["-h"], ["--help"]):
                doc = (fn.__doc__ or "").strip().split("\n")[0]
                print(f"Usage: {prog} [args...]")
                if doc:
                    print(doc)
                return
            fn()

        return wrapped
