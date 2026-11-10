# moac

Models, options, accounts, capabilities: the one place an AI call is configured and made. Every tool here goes through it (`dienpy`'s hunks and feed, `cril`, `deckard` over the CLI). It imports nothing from `dienpy`, which imports it; shared helpers come from [`dienraw`](../dienraw/README.md). No personal paths or machine-specific config.

## Layout

```
moac/        Python package; each public module is a CLI command (protocli Dispatcher.from_package), helpers are underscore-prefixed
tests/       synthetic fixtures only
```

`uv run moac ...`, `uv run pytest`. Installed with `make install-moac` from the repo root.

## Accounts

An account is one claude config directory, so several logins stay signed in side by side. They live in `~/.config/moac/moac.toml`; with no `[account]` table there is one implicit account: the claude command's own default location, or wherever an inherited `CLAUDE_CONFIG_DIR` points.

```toml
default_account = "work"

[account.work]

[account.personal]
config_dir = "/path/to/.claude-personal"
```

- The account a call runs on: `--account`, then `MOAC_ACCOUNT`, then `default_account`, then the first account declared. `Need(account=...)` is the same choice from Python; a backend without accounts refuses it. A session exports `MOAC_ACCOUNT`, so what it starts stays on the same login.
- A declared account without `config_dir` leaves `CLAUDE_CONFIG_DIR` unset, because naming the default location through that variable moves claude's global state file into the directory.
- `moac login <account>` creates the directory, symlinks what every account shares from the default one (`_account._SHARED`), and runs `claude auth login` there. Everything else, memory and history included, is the account's own.
- `moac who` lists the accounts with email, plan, login expiry and directory.
- `moac usage [--watch] [--account NAME]` shows the usage windows of every signed-in account, or the named one. `usage.windows()` reads the current account.

## Backends

A backend is a tagged union of kinds, because backends differ in capability, not just in fields:

| kind | transport | auth | schema output | repo tools | thinking effort |
| --- | --- | --- | --- | --- | --- |
| `openai` | HTTP chat-completions (llama-server, vLLM, an SSH-tunneled remote) | none | `response_format` json_schema | no | no |
| `api` | anthropic / google SDK by model prefix | `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | not yet | no | `output_config.effort` under adaptive thinking (anthropic), thinking budget (gemini) |
| `cli` | `claude` subprocess: `send` captures a `-p --output-format json` call, `launch` runs a session with inherited stdio | `login` (the claude command's own claude.ai credentials; the subprocess drops `ANTHROPIC_*` vars) or `env` | `--json-schema` | `--tools` | `--effort` |

Effort is one open vocabulary (`low|medium|high|xhigh|max`, empty = backend default), interpreted per kind: anthropic api sends it as `output_config.effort` under adaptive thinking, gemini api maps it to a thinking budget, cli passes it to `claude --effort`, openai refuses it. It comes from the caller's `Need` or the profile's `effort` field, and completion is advisory — an invalid value is refused at resolution with the valid set.

Callers declare a `Need(schema, tools, effort, timeout, account)` and call `moac.resolve(tool, need, profile=...)`; resolution is capability-checked and refuses loudly before any tokens are spent or state is written. `moac.send(backend, system, user, *, schema=..., cwd=...)` is the captured call — with a schema it returns the parsed object, without one the reply text. `moac.launch(cli_backend, prompt, *, interactive, safe, system, resume, log, cwd)` is the session shape for cli backends: interactive inherits the terminal; non-interactive runs `-p` with the prompt on stdin, `--permission-mode auto` unless the profile sets one, and the backend's timeout; with `log` it streams `stream-json` there, prints one progress line per turn, and returns an `Outcome(session_id, result, subtype, is_error, returncode, turns)`. Both build argv from `cli_argv`, so model/effort/permission flags exist in one place. Every child process (`send`, `launch`, feed's shell jobs) runs under `moac.supervise`: the child leads its own process group, a timeout kills the whole group (outcome `subtype == moac.TIMEOUT`), SIGTERM/SIGHUP/Ctrl-C on the launcher take the child down first, and pipes decode with replacement. An interactive session is the exception — it stays in the terminal's foreground group so it owns the tty.

Timeout precedence: an explicit `--timeout` beats the profile's `timeout`, which beats the caller's `Need.timeout` (`moac.run.backend` layers them; the unattended default is `run._UNATTENDED_TIMEOUT`).

Profiles live in `~/.config/moac/moac.toml` layered over `_profiles.BUILTIN`, which is the one model table in the ecosystem: the tier ids (`HAIKU`, `SONNET`, `OPUS`, `FABLE` — exact, pinned) and the shortcut profiles over them (`soh|som`, `opuh|opux|opum`, `fabx`: tier + effort). A new model version is a one-line bump there; the shell aliases (`clopux`, `pipecl`, …) name profiles and carry no ids. A missing toml is a working config; `default` names the fallback profile, `[tool]` binds tool keys (`hunks`, `commit`, `run`, `feed`) to profiles, a cli profile may set `permission_mode`, and an unknown profile name resolves as a bare claude CLI model so ad-hoc model ids keep working.

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

- `moac profiles` — list profiles: kind, config, default marker, tool bindings.
- `moac check [profile]` — smoke test: endpoint reachable, key present, claude installed and logged in.
- `moac models [--provider P] [--refresh]` — the model-id cache (`~/.config/moac/models.json`, one list per API provider): lists it, re-fetching any provider's list older than `_cache.TTL` (`--refresh`: now). `moac.models.Target` completes `moac run`'s first argument from the profile names plus the cached anthropic ids — a read of the file, never a fetch, so tab stays instant; the feed scheduler calls `models.update(quiet=True)` at every cycle start, which keeps the cache fresh on a machine that runs it.
- `moac ask [profile] [file] [--tool KEY] [--raw TEXT] [--system TEXT] [--schema JSON|FILE] [--tools T,…] [--effort E] [--timeout S] [--cwd DIR] [--envelope] [--account NAME]` — the captured call (`moac.send`) as a command, for callers outside Python: the prompt from `--raw`, the file or stdin; the profile from the `[tool]` binding of `--tool` (default `ask`), then `default`, so each caller names its own key and each machine binds it; `--schema` returns one JSON object; `--tools Read` with `--cwd` lets a cli profile look at an image there; `--envelope` prints the profile, backend kind, effort and the call's `Usage` fields beside the reply, for callers that index their tools by speed or cost. The module is `ask`, not `send`, because `moac.send` is the library function.
- `moac run [profile] [file] [--interactive] [--safe] [--raw TEXT] [--auto] [--unattended] [--commit] [--timeout S] [--account NAME]` — the launcher behind every shell shortcut: a prompt from `--raw`, the file (frontmatter stripped, `_prompt_file`), or piped stdin runs non-interactively (auto permissions) and prints the reply; the profile defaults to the `[tool] run` binding, then `default`; `--interactive` opens a session instead (a piped prompt becomes its first message); `--unattended` appends the queue rules (`moac.run.unattended_suffix`: no questions, take the recommended default, never commit, final report) and `--commit` lifts their never-commit rule. A failed run prints its synthesized result (`timed out after …`, `claude exited before reading the prompt`) to stderr and exits non-zero. `pipecl`/`pipeclf` and `cl*` are aliases onto it.
