# dienpy

Public, generalizable CLI toolkit — one entry point (`dienpy <module> [args...]`) that dispatches to focused Python modules. No personal paths, secrets, or machine-specific config.

The CLI dispatcher is [`protocli`](https://pypi.org/project/protocli/) (split out of dienpy, now a PyPI dependency) — `cril`, `hyppy`, `fleet` and `rankless` use it the same way. protocli's README/docstring is the authoritative spec; the rest of this doc shows how dienpy applies the pattern.

## Architecture

- **Entry point**: `dienpy/__main__.py` calls `_dispatcher.run()`.
- **Dispatcher**: `dienpy/__init__.py` does `_dispatcher = Dispatcher.from_package("dienpy")`. `Dispatcher.from_package` scans the package with `pkgutil.iter_modules` and binds each non-private submodule as a command.
- **Shell completion**: `dotfiles/.local/share/bash-completion/completions/dienpy` evals protocli's script from `dienpy --bash-completion` on the first TAB; the script asks `dienpy --complete [args...]`, which the Dispatcher answers from `main`'s signature — a `get_completions` hook only where the signature can't say it. Aliases onto any protocli tool (`hunks`, `dcuw`, …) complete the same way: the script expands the alias and prepends its words to the typed args. `.bash_aliases` registers a stub for each such alias that loads the tool's script on the alias's first TAB, so nothing per alias is maintained.

## Discovering Commands

Run `dienpy --help` to list all commands with one-line descriptions (sourced from each module's `__doc__`).
Run `dienpy <cmd> --help` for per-command usage.
Run `dienpy --help-all` for a full recursive listing: all dispatcher levels expanded, plus full argparse help for each signature-dispatched leaf (and a completions line for any leaf that defines `get_completions`). Completers declared in the signature are never called here — `--help-all` walks every leaf, so resolving them would load the world.

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
   - `Annotated[str, Complete(f)]` → shell candidates from `f()`, on any parameter

   Reach for `argparse` directly only when the signature model can't express what you need (e.g. mutually exclusive groups, custom argument actions). For zero-arg leaves (`def main() -> None`), the dispatcher prints `Usage: ...` + the docstring on `--help`.
3. **Completions belong on the parameter.** `Literal` fixes a closed set argparse enforces; `Complete` carries candidates computed only when the shell asks, and never enforced — an unknown value reaches `main` and is rejected there, with `main`'s own error. Export the alias next to the function it completes from (`moac.ProfileName`, `_config.Dim`, `_inventory.MachineName`) so every leaf spells it the same way; `Annotated[str, FILES]` requests native pathname completion.
4. Fall back to `get_completions(args: list[str]) -> list[str]` only when candidates depend on *more than one* argument, or the leaf parses `sys.argv` itself — `hyppy vid night`'s subcommand state machine, not a value list.
5. **No registration needed** — `Dispatcher.from_package` auto-discovers it.
6. **First-letter rule**: `<name>` must start with a letter distinct from every other sibling so `<pkg> <letter><TAB>` completes in one keystroke.
7. **Boundary check (dienpy only)**: if the module references personal paths, secrets, or `$HOME`-specific files, it belongs in `hyppy`, not here.

### Grouped commands (package as a subcommand)

Create `<pkg>/<group>/__init__.py` with:

```python
from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("<pkg>.<group>", prog="<pkg> <group>")
```

That's it. The parent Dispatcher detects the nested `_dispatcher` attribute and routes through it. Submodules follow the same leaf-module rules and the same first-letter constraint within the group. Examples: `dienpy.feed`, `dienpy.versions`, `hyppy.vid`.

### Direct callables

Dispatcher also accepts a plain dict of `{name: callable_or_module_path}` for cases where auto-discovery isn't the right shape (e.g. registering a couple of bound functions). See `dienpy.versions` and `dienpy.tts.server` for examples.

## Model access

Every AI call goes through [`moac`](../moac/AGENTS.md), next to this package. Tables, TOML helpers and atomic writes come from [`dienraw`](../dienraw/README.md).

## The `feed` package

`dienpy feed` runs prompts through unattended claude sessions whenever the usage windows have headroom, and closes each with the regroup cache. `moac.usage.windows()` parses the oauth payload's `limits` into `session`, `weekly_all` and `weekly_scoped:<Model>` (Fable has its own weekly cap); `dienpy.feed._gate` judges a job against them — the weekly windows against a ceiling, the session window against what the job will consume (`session% + need ≤ Thresholds.session`).

### The prompt protocol

A repo's queue is `<repo>/.cril/prompts/*.md`. A prompt opts in through a flat `---` fenced frontmatter block (`moac._prompt_file`; the model only sees the body). A leading `---` that is not followed by `key: value` lines closed by a second fence is plain text, not frontmatter; a block whose values fail validation lists the prompt as `invalid frontmatter: …` instead of stopping the scheduler:

```markdown
---
mode: once            # once | repeat
unattended: true      # absent/false: never scheduled
profiles: fabx, opux  # preference order; default from feed.toml, then moac.toml's `[tool] feed`, then fabx, opux
priority: 2           # 1 first … 5 last
need: 20              # % of the 5h window one run consumes (default `DEFAULT_NEED`); replaced by the mean of the last three measured runs
every: 24h            # repeat: minimum gap after an ok run (default 12h); once: re-eligible after it even if the file survives
commit: true          # lets the unattended suffix allow commits (repos whose agents commit themselves)
target: …             # unknown keys are ignored — free-form notes ride along with the prompt
---
```

Repo defaults sit in `<repo>/.cril/feed.toml`: `hunks` (regroup dims closed after each job; `[]` leaves the cache alone), `profiles`, and `env` (read by the private cril layer only). Run history is machine-written to `<repo>/.cril/prompts/state.toml` — per prompt `last`, `outcome` (ok|failed|limit), `attempts`, `costs` (last three measured session-% deltas), `report` — pruned of prompts that no longer exist. Authored metadata stays in the prompt; the scheduler never rewrites a user file.

Lifecycle (`_queue.lifecycle`): a `once` prompt is eligible until it runs ok — agents delete their own prompt when the section lands, so a surviving one shows `landed?` until the user deletes it or `every` passes; a `repeat` prompt waits `every` after an ok run; a `failed` prompt is retried only after the file's mtime moves past the failed run.

### Commands

- `dienpy feed run` (no arguments) — scheduler over the repo around the cwd (`--repos R…` for several): collect candidates, drop the ineligible (lifecycle, repo lock, headroom for `need`), order by priority then the repo that waited longest then name, run the first, write `state.toml`, repeat; `--once` stops after one job. `--dry-run` prints the listing instead.
- `dienpy feed run <prompt.md …> [--cmd <shell>] [--repeat]` — explicit mode in this repo, in order, gated the same way; each prompt's frontmatter supplies its `need`, `profiles` and `commit`, and `--need`, `--profiles`, `--commit` override them; `--cmd` runs a command with the gate's choice in `FEED_PROFILE`/`FEED_MODEL` (how uxarr's `make experiment` lets the gate pick its model); `--hunks` overrides the repo's `feed.toml` (`--hunks ""` skips the regroup close); `--timeout` overrides the profile's.
- `dienpy feed list [repos…] [--offline]` — one line per prompt: mode, priority, need, profiles, last run, and the verdict (`runnable → fabx`, `needs 20 / have 12`, `cooldown until …`, `failed … (edit to retry)`, `landed?`, `not unattended`, `invalid frontmatter: …`, `repo busy`).
- `dienpy feed playbook <file> [--dry-run]` — a playbook (conventionally `<repo>/.cril/playbooks/<name>.md`; a first line `#!/usr/bin/env -S dienpy feed playbook` runs it as `./<file>`) is a frontmatter file whose `jobs:` names prompts in the repo's `.cril/prompts/` (repeats allowed) and whose body states the run's intent. The jobs run in order through explicit mode, starting none once `until:` (a key of `playbook.UNTIL`, naming the usage window whose reset ends the run) has passed. When the jobs end, the deadline passes or Ctrl-C stops it, the run facts (outcome per job, the unrun rest as a `feed run` line, repo files whose status changed, logs) go to `$LOGS_DIR/feed/<repo>/<stamp>-playbook-<name>.md`, then a guide session reads them with the intent and rewrites that file with what to open first and what needs the owner; a second Ctrl-C skips the guide. The repo is the one whose `.cril/` holds the file on its path as the shell spelled it, else the repo around the cwd.

A job is one `moac.launch` with `unattended_suffix(commit)`, streamed to `$LOGS_DIR/feed/<repo>/<stamp>-<prompt>.jsonl`, its final report to `.md`, one row in `runs.md`; a session that dies on a usage limit is resumed once after that window resets. A wrapped or `--cmd` job has no stream: its console output goes to `.out`, and for a wrapped prompt that output is the report (turns stay 0). A repo is locked with `flock` on `.git/feed.lock` while its job runs and its state is written — the kernel releases the lock when the holder dies, so a crash never leaves a repo busy. The close is `hunks run --extend <dims>`; only when the regroup cache holds no run for those dims does a full `hunks run` follow — a failed extend leaves a curated run as it was. Usage is read once after the close: it measures the job's `cost` (learned only from ok runs, and only when the session window did not reset in between) and seeds the next cycle's gate, so a job costs one usage fetch.

The loop is a library: `feed.schedule(repos: list[RepoQueue], settings, usage=…)` and `feed.run_jobs(repo, jobs, settings, usage=…)`. A `RepoQueue` may carry its own `usage` source and a `wrap` template around `{cmd}` — that is how hypothalamus' `cril queue` runs a sandboxed repo's prompts inside `fleet env <env>` (`moac run --unattended [--commit] --timeout …`) gated on the sandbox identity's windows, so one loop serves both accounts.

## Shared State

- `constants.py` derives the canonical paths from `SYNC_ROOT` (default `$HOME/synced`), each through `env_path` so the matching `.vars` export wins — use these, don't hardcode paths
- `_git.py` holds every git invocation in the ecosystem — `Repo(path)` bound to a repo, module-level `run`/`clone` for the repo-less calls; cril, hyppy and fleet import it rather than reaching for `subprocess`. `setup/` is the exception: it stays dependency-free because it runs before dienpy is installed
- Per-module state files go under the relevant synced directory or `~/.config/`

## Environment

- Managed with `uv`, environment at `.venv`
- Install: `uv tool install -e .`
- Run: `dienpy <module>` (or `python -m dienpy <module>`)

## Conventions

- Modules are single-file unless genuinely complex (like `hunks/`, `feed/`, `nvim/`)
- Let `main`'s signature drive argument parsing; only reach for `argparse` directly when the signature model can't express what you need
- Fail loudly via `raise SystemExit(msg)` for user errors
- Type hints required throughout
