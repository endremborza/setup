# diencephalon — agent guide

Public dotfiles, scripts, and tooling. Config files in `dotfiles/` are symlinked to `~` via GNU stow (`dotfiles/.local/bin/restow`). **Public repo** — no secrets, no personal paths.

User-facing docs: [README.md](README.md). Deep reference (profiles, env, testing): [SETUP.md](SETUP.md).

## Repo layout

| Directory   | Purpose                                                                    |
|-------------|----------------------------------------------------------------------------|
| `dotfiles/` | Generic dotfiles stowed to `~` (nvim, alacritty, tmux, leftwm, shell, etc) |
| `setup/`    | Profile-based bootstrap package (`setup` CLI)                              |
| `dienpy/`   | Public Python CLI (`dienpy <module>`) — see `dienpy/AGENTS.md`             |
| `util/`     | Templates (systemd service/socket) used by `create-service`                |

## Boundary rule

Only generalizable, public-safe content. Anything referencing personal paths, secrets, hostnames, or personal services belongs in the private companion repo (`hypothalamus`). Dependency direction: private may depend on public, never the reverse.

`dotfiles/.vars` defines the base env layer (`SYNC_ROOT` and derived paths). `.profile` sources it. `dienpy/dienpy/constants.py` mirrors the same defaults in code for bootstrap.

## Setup architecture

`setup/setup/` is a small profile registry + runner. Each install is a `@brick`-decorated function declaring its profile, an idempotency `check`, and a `verify` smoke test.

```
setup/setup/
├── __main__.py      # argparse: run | list | verify
├── runner.py        # @brick decorator, REGISTRY, run/verify
├── util.py          # run_cmd, apt_install, cargo_install, clone_gh, …
├── versions.py      # load/dump versions.toml; fetch latest from upstream
└── bricks/
    ├── base.py          # apt-base, restow, rust, rclone
    ├── dev.py           # shell + dev profile bricks
    ├── desktop.py       # screen profile
    └── workstation.py   # screen-apps profile
```

### Adding a brick

```python
from setup.runner import brick
from setup.util import apt_install

@brick(
    profile="shell",
    name="my-tool",
    check="my-tool --version",   # passes → brick is skipped
    verify="my-tool --version",  # used by `setup verify`
)
def install_my_tool() -> None:
    apt_install(["my-tool"])
```

Then import the module from `setup/bricks/__init__.py` so the decorator runs at import.

Rules:
- One home per tool. No duplication between `dotfiles/`, `setup/`, `dienpy/`.
- Bricks must be idempotent (the `check` exists so reruns are cheap).
- A package never vendors a file that's already stowed from `dotfiles/`. Read the stowed path instead (`~/rclone_filter.txt`, etc.).
- Brick names must be unique across all profiles — `dienpy versions` keys off the name.

### Versions

Pinned tags live in `setup/versions.toml`. The toml is the source of truth — `setup/setup/versions.py` does load/dump round-trip (no line-level patching). Brick modules import `from setup.versions import get as _v` and read tags at module-load time.

`dienpy versions` (in `dienpy/dienpy/versions/`) is the management front end: list, check upstream, bump, dry-run upgrade, live upgrade. It composes the brick registry — version ownership lives in dienpy, not setup.

## Stow integration

`dotfiles/.local/bin/restow` stows this repo's `dotfiles/` to `~` with `--no-folding`. A private companion (`hypothalamus`) stows alongside — GNU stow merges directories, so both contribute files to `~/.local/bin/` etc. as long as filenames don't collide.

## Three-layer env vars

| Layer | File              | Source                                  | Content                                |
|-------|-------------------|-----------------------------------------|----------------------------------------|
| 1     | `~/.vars`         | diencephalon                            | Base paths, tool config, non-secret    |
| 2     | `~/.secret-vars`  | hypothalamus/secrets                    | API keys, tokens                       |
| 3     | `~/.local-vars`   | hypothalamus/local-dotfiles/host-$(hn)  | Machine-specific (GPU, hardware, port) |

Each layer can reference earlier ones. `.profile` and `.xinitrc` source them in order. `restow` regenerates `~/.config/environment.d/{10,20,30}-*.conf` so systemd user services see the same env.

Full boot-to-desktop propagation flow (including tmux/dbus/import-environment gotchas) is in [SETUP.md](SETUP.md#environment-propagation).

## nvim config

Lives at `dotfiles/.config/nvim/init.lua`. Uses lazy.nvim + mason + mason-lspconfig (v2 API, Neovim 0.11+).

`lua/regroup/` — AI change-group review UI (browse / stage / unstage / revert / commit per group or hunk; bury a group to the graveyard = `regroup:`-tagged git stash, `:RegroupGraveyard` to restore); cheatsheet at `:h regroup` (`doc/regroup.txt`). Analysis runs in the shell via **`dienpy hunks`** (`run|list|drift`, tab-completed) which owns `.git/regroup-cache.json`; nvim only reads the cache (picking an uncached config yanks the engine command instead of running it). The engine groups hunks semantically via `claude -p --json-schema` — the model only references content-hash hunk IDs, never writes patch bytes — across three config dimensions (granularity loose/normal/granular, model, context bare/agents/explore), with incremental updates for new hunks. Hunk-ID parity between `dienpy/hunks/_hunks.py` and `regroup/diff.lua` is pinned by `dienpy/tests/test_hunks_parity.py` — change both together. The claude subprocess drops `ANTHROPIC_API_KEY` to run on claude.ai login auth (`--auth env` keeps it). `regroup/review.lua` owns the review-mode diff windows, shared with `<leader>gf/gr/gb`.

### Key decisions

- **LSP config**: `vim.lsp.config('server', {...})` per-server + `automatic_enable = true`.
- **Non-file buffer guard**: `vim.lsp.start` is wrapped to prevent LSP on `fugitive://`, `gitsigns://`, `term://`.
- **lazydev.nvim** provides `vim` global type info to lua_ls. Must be a dependency of nvim-lspconfig with `ft = 'lua'`.

### Updating nvim or plugins

1. `dienpy nvim release_notes` — fetch recent release notes for all plugins
2. Review for breaking changes
3. `:Lazy update`
4. `dienpy nvim verify --perf` — headless LSP health check
5. `dienpy nvim commit` — commit with plugin version snapshot

### Diagnosing LSP

1. `dienpy nvim verify --perf`
2. `:LspInfo`, `:LspLog`
3. Check mason install: `~/.local/share/nvim/mason/bin/<server>`
4. Check `lazy-lock.json` vs upstream changelogs

### Common pitfalls

- **mason-lspconfig v2**: removed `handlers` API. Use `vim.lsp.config()`.
- **`before_init` cannot change `cmd`**: process already spawned. Use `cmd` in `vim.lsp.config()`.
- **catppuccin lualine theme**: name must include flavour — `catppuccin-mocha`.
- **conform.nvim**: `lsp_fallback` → `lsp_format = "fallback"`. `ruff_fix` → `ruff_format`.
- **Slow rust file opens**: default `root_dir` runs `rustc --print sysroot` synchronously. Fix with custom `root_dir` using `Cargo.lock` + cache.
- **Fugitive diff slowness**: (1) `vim.lsp.start` override, (2) custom `root_dir`, (3) nvim-ufo returns `''` for non-file buffers.
- **diffopt**: `algorithm:patience,linematch:20` — default `linematch:40` is expensive.

### dienpy nvim tools

- `dienpy nvim verify [--perf]` — headless LSP check against test projects. Config at `~/.config/nvim-verify.json`.
- `dienpy nvim commit [--dry-run]` — commit nvim dotfiles with plugin version snapshot.
- `dienpy nvim release_notes` — fetch GitHub release notes for plugins. Needs `GITHUB_TOKEN`.
