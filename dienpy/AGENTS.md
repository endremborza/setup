# dienpy

Public, generalizable CLI toolkit — one entry point (`dienpy <module> [args...]`) that dispatches to focused Python modules. No personal paths, secrets, or machine-specific config.

## Architecture

- **Entry point**: `dienpy/__main__.py` — discovers and dispatches to submodules by name
- **Each module** is self-contained with a `main()` function and optionally a `get_completions(args: list[str]) -> list[str]` function for shell tab-completion, or is managed by `Dispatcher` in `dienpy.cli`
- **Shell completion**: `dotfiles/.local/share/bash-completion/completions/dienpy` relies on `_proto_complete` calls `dienpy --complete [module] [args...]`

## Current Modules

| Module | Purpose |
|--------|---------|
| `nvim` | Headless LSP verify, plugin release notes, commit helper |
| `ai` | AI commit messages, model listing, caching |
| `claude` | Claude API auth and usage tracking |
| `check_versions` | Check upstream versions for tracked tools |
| `random_naming` | Generate random project names |
| `upload_to_tmp_s3` | Upload file to temporary S3 bucket |

## Adding a Module

1. Create `dienpy/<name>.py` with a `main()` function
2. Add `get_completions(args: list[str]) -> list[str]` if the module takes arguments worth completing
3. No registration needed — `pkgutil.iter_modules` auto-discovers it
4. **Boundary check**: if the module references personal paths, secrets, or `$HOME`-specific files, it belongs in `hyppy` (hypothalamus), not here

## Shared State

- `constants.py` holds canonical paths under `/mnt/data/synced/` — use these, don't hardcode paths
- Per-module state files go under the relevant synced directory or `~/.config/`

## Environment

- Managed with `uv`, environment at `.venv`
- Install: `uv tool install -e .`
- Run: `dienpy <module>` (or `python -m dienpy <module>`)

## Conventions

- Modules are single-file unless genuinely complex (like `ai/`, `claude/`)
- Prefer `argparse` for CLI parsing within modules
- Fail loudly via `raise SystemExit(msg)` for user errors
- Type hints required throughout
