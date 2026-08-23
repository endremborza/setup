# dienpy

Public, generalizable CLI toolkit — one entry point (`dienpy <module> [args...]`) that dispatches to focused Python modules. No personal paths, secrets, or machine-specific config.

The CLI dispatcher is [`protocli`](https://pypi.org/project/protocli/) (split out of dienpy, now a PyPI dependency) — `cril`, `hyppy`, `fleet` and `rankless` use it the same way. protocli's README/docstring is the authoritative spec; the rest of this doc shows how dienpy applies the pattern.

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
   - `*, xs: list[float] = []` → `--xs 1.5,3.5` (comma-separated; keyword-only)
   - `*, x: T | None = None` → optional `--x` flag

   Reach for `argparse` directly only when the signature model can't express what you need (e.g. mutually exclusive groups, custom argument actions). For zero-arg leaves (`def main() -> None`), the dispatcher prints `Usage: ...` + the docstring on `--help`.
3. Optionally expose `get_completions(args: list[str]) -> list[str]` if the auto-derived completions (flag names + `Literal` choices) aren't enough — e.g. dynamic value lists like `dienpy tts speak`'s voice catalog.
4. **No registration needed** — `Dispatcher.from_package` auto-discovers it.
5. **First-letter rule**: `<name>` must start with a letter distinct from every other sibling so `<pkg> <letter><TAB>` completes in one keystroke.
6. **Boundary check (dienpy only)**: if the module references personal paths, secrets, or `$HOME`-specific files, it belongs in `hyppy`, not here.

### Grouped commands (package as a subcommand)

Create `<pkg>/<group>/__init__.py` with:

```python
from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("<pkg>.<group>", prog="<pkg> <group>")
```

That's it. The parent Dispatcher detects the nested `_dispatcher` attribute and routes through it. Submodules follow the same leaf-module rules and the same first-letter constraint within the group. Examples: `dienpy.ai`, `dienpy.versions`, `hyppy.vid`.

### Direct callables

Dispatcher also accepts a plain dict of `{name: callable_or_module_path}` for cases where auto-discovery isn't the right shape (e.g. registering a couple of bound functions). See `dienpy.versions` and `dienpy.tts.server` for examples.

## The `ai` package

`dienpy/ai/` is the backend layer every AI-calling tool goes through — kept plugin-shaped (nothing under `ai/` imports the rest of dienpy) so extraction to its own repo stays mechanical.

A backend is a tagged union of kinds, because backends differ in capability, not just in fields:

| kind | transport | auth | schema output | repo tools | thinking effort |
|---|---|---|---|---|---|
| `openai` | HTTP chat-completions (llama-server, vLLM, an SSH-tunneled remote) | none | `response_format` json_schema | no | no |
| `api` | anthropic / google SDK by model prefix | `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | not yet | no | thinking budget |
| `cli` | `claude -p` subprocess | `login` (the claude command's own claude.ai credentials; the subprocess drops `ANTHROPIC_*` vars) or `env` | `--json-schema` | `--tools` | `--effort` |

Effort is one open vocabulary (`low|medium|high|xhigh|max`, empty = backend default), interpreted per kind: api maps it to a thinking budget, cli passes it to `claude --effort`, openai refuses it. It comes from the caller's `Need` or the profile's `effort` field, and completion is advisory — an invalid value is refused at resolution with the valid set.

Callers declare a `Need(schema, tools, effort, timeout)` and call `ai.resolve(tool, need, profile=...)`; resolution is capability-checked and refuses loudly before any tokens are spent or state is written. `ai.send(backend, system, user, *, schema=..., cwd=...)` is the whole call surface — with a schema it returns the parsed object, without one the reply text.

Profiles live in `~/.config/dienpy/ai.toml`; a missing file is a working config (builtin profiles: `haiku|sonnet|opus|fable` as cli-login, `local` as openai on `localhost:8081`). `default` names the fallback profile, `[tool]` binds tool keys (`hunks`, `commit`) to profiles, and an unknown profile name resolves as a bare claude CLI model so ad-hoc model ids keep working.

```toml
default = "sonnet"

[profile.tunnel]
kind = "openai"
url = "http://localhost:8081/v1/chat/completions"

[profile.deep]
kind = "cli"
model = "opus"
effort = "xhigh"

[tool]
hunks = "fable"
commit = "tunnel"
```

- `dienpy ai profiles` — list profiles: kind, config, default marker, tool bindings.
- `dienpy ai check [profile]` — smoke test: endpoint reachable, key present, claude installed and logged in.
- `dienpy ai models` — cached model-id listing per API provider (completion source).

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
