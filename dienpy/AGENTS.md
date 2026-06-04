# dienpy

Public, generalizable CLI toolkit — one entry point (`dienpy <module> [args...]`) that dispatches to focused Python modules. No personal paths, secrets, or machine-specific config.

`dienpy.cli.Dispatcher` is the canonical CLI dispatcher for the whole ecosystem — `cril` and `hyppy` use it the same way. The rest of this doc is the authoritative spec for that pattern.

## Architecture

- **Entry point**: `dienpy/__main__.py` calls `_dispatcher.run()`.
- **Dispatcher**: `dienpy/__init__.py` does `_dispatcher = Dispatcher.from_package("dienpy")`. `Dispatcher.from_package` scans the package with `pkgutil.iter_modules` and binds each non-private submodule as a command.
- **Shell completion**: `dotfiles/.local/share/bash-completion/completions/dienpy` calls `dienpy --complete [args...]`, which the Dispatcher answers via `get_completions`.

## Discovering Commands

Run `dienpy --help` to list all commands with one-line descriptions (sourced from each module's `__doc__`).
Run `dienpy <cmd> --help` for per-command usage.
Run `dienpy --help-all` for a full recursive listing: all dispatcher levels expanded, plus full argparse help for each signature-dispatched leaf (and a completions line for any leaf that defines `get_completions`).

## Adding a Command (canonical pattern — applies to dienpy, cril, hyppy)

### Leaf module

1. Create `<pkg>/<name>.py` with a module-level docstring (one-line summary shown in `--help`) and a `main(...) -> None` function.
2. **Arguments are declared via `main`'s signature** — the dispatcher introspects it and builds an `argparse` parser:
   - `name: str` → required positional
   - `name: str | None = None` → optional positional (`nargs="?"`)
   - `*paths: str` → variadic positional (`nargs="*"`)
   - `*, flag: bool = False` → `--flag` (`store_true`); bools must be keyword-only with default `False`
   - `*, n: int = 5` → `--n N` with default
   - `*, m: Literal["a","b"]` → `--m` restricted to choices
   - `*, x: T | None = None` → optional `--x` flag

   Reach for `argparse` directly only when the signature model can't express what you need (e.g. mutually exclusive groups, custom argument actions). For zero-arg leaves (`def main() -> None`), the dispatcher prints `Usage: ...` + the docstring on `--help`.
3. Optionally expose `get_completions(args: list[str]) -> list[str]` if the auto-derived completions (flag names + `Literal` choices) aren't enough — e.g. dynamic value lists like `dienpy tts speak`'s voice catalog.
4. **No registration needed** — `Dispatcher.from_package` auto-discovers it.
5. **First-letter rule**: `<name>` must start with a letter distinct from every other sibling so `<pkg> <letter><TAB>` completes in one keystroke.
6. **Boundary check (dienpy only)**: if the module references personal paths, secrets, or `$HOME`-specific files, it belongs in `hyppy`, not here.

### Grouped commands (package as a subcommand)

Create `<pkg>/<group>/__init__.py` with:

```python
from dienpy.cli import Dispatcher

_dispatcher = Dispatcher.from_package("<pkg>.<group>", prog="<pkg> <group>")
```

That's it. The parent Dispatcher detects the nested `_dispatcher` attribute and routes through it. Submodules follow the same leaf-module rules and the same first-letter constraint within the group. Examples: `dienpy.ai`, `dienpy.versions`, `hyppy.vid`.

### Direct callables

Dispatcher also accepts a plain dict of `{name: callable_or_module_path}` for cases where auto-discovery isn't the right shape (e.g. registering a couple of bound functions). See `dienpy.versions` and `dienpy.tts.server` for examples.

## Shared State

- `constants.py` holds canonical paths under `/mnt/data/synced/` — use these, don't hardcode paths
- Per-module state files go under the relevant synced directory or `~/.config/`

## Environment

- Managed with `uv`, environment at `.venv`
- Install: `uv tool install -e .`
- Run: `dienpy <module>` (or `python -m dienpy <module>`)

## Conventions

- Modules are single-file unless genuinely complex (like `ai/`, `claude/`, `nvim/`)
- Let `main`'s signature drive argument parsing; only reach for `argparse` directly when the signature model can't express what you need
- Fail loudly via `raise SystemExit(msg)` for user errors
- Type hints required throughout
