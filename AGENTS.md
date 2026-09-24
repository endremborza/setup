# diencephalon — agent guide

Public dotfiles, scripts, and tooling. Config files in `dotfiles/` are symlinked to `~` via GNU stow (`dotfiles/.local/bin/restow`). **Public repo** — no secrets, no personal paths.

User-facing docs: [README.md](README.md). Deep reference (profiles, env, testing): [docs/setup.md](docs/setup.md).

## Repo layout

| Directory | Purpose |
| --- | --- |
| `dotfiles/` | Generic dotfiles stowed to `~` (nvim, alacritty, tmux, leftwm, shell, etc) |
| `setup/` | Profile-based bootstrap package (`setup` CLI) |
| `dienpy/` | Public Python CLI (`dienpy <module>`) — see `dienpy/AGENTS.md` |
| `util/` | Templates (systemd service/socket) used by `create-service` |

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
    check="my-tool --version",   # passes → brick is skipped; re-run after the install, and doubles as `verify`
)
def install_my_tool() -> None:
    apt_install(["my-tool"])
```

A pinned tool uses `check=pinned_check("my-tool --version", _v("my-tool"))`, which passes only at the pinned version, so a bump re-runs the brick. Pass `verify=` only when the install guard is not the right smoke test.

Then import the module from `setup/bricks/__init__.py` so the decorator runs at import.

Rules:
- One home per tool. No duplication between `dotfiles/`, `setup/`, `dienpy/`.
- Bricks must be idempotent (the `check` exists so reruns are cheap).
- A package never vendors a file that's already stowed from `dotfiles/`. Read the stowed path instead (`~/rclone_filter.txt`, etc.).
- Brick names must be unique across all profiles — `dienpy versions` keys off the name.

### Versions

Pinned tags live in `setup/versions.toml`. The toml is the source of truth — `setup/setup/versions.py` does load/dump round-trip (no line-level patching). Brick modules import `from setup.versions import get as _v` and read tags at module-load time; URLs that want the bare number use `number(tag)`.

`dienpy versions` (in `dienpy/dienpy/versions/`) is the management front end: list, check upstream, bump. Applying a bump is `setup run`: the pinned checks fail and the bricks rebuild — the toml is the only upgrade state, nothing per machine.

## Stow integration

`dotfiles/.local/bin/restow` stows this repo's `dotfiles/` to `~` with `--no-folding` (`dotfiles/.claude/` separately, to `$SHARE_DIR/.claude`). A private companion (`hypothalamus`) stows alongside — GNU stow merges directories, so both contribute files to `~/.local/bin/` etc. as long as filenames don't collide.

## Three-layer env vars

| Layer | File | Source | Content |
| --- | --- | --- | --- |
| 1 | `~/.vars` | diencephalon | Base paths, tool config, non-secret |
| 2 | `~/.secret-vars` | hypothalamus/secrets | API keys, tokens |
| 3 | `~/.local-vars` | hypothalamus/local-dotfiles/host-$(hn) | Machine-specific (GPU, hardware, port) |

Each layer can reference earlier ones. `.profile` sources them in order; everything a login starts inherits them. `restow` regenerates `~/.config/environment.d/{10,20,30}-*.conf` from the files alone so systemd user services see the same env (`$` escaped as `$$`); the stowed `99-path.conf` puts `~/.local/bin` and `~/.cargo/bin` on their PATH.

Full boot-to-desktop propagation flow (including the tmux and dbus gotchas) is in [docs/setup.md](docs/setup.md#environment-propagation).

## nvim config

Lives at `dotfiles/.config/nvim/init.lua`. Uses lazy.nvim + mason + mason-lspconfig (v2 API, Neovim 0.11+).

`lua/regroup/` — patch review and landing UI over the `dienpy hunks` engine; architecture, commands and cache schema in [docs/regroup.md](docs/regroup.md), keybinding cheatsheet at `:h regroup` (`doc/regroup.txt`). What an agent editing this repo must not break: nvim parses no diff and writes no git state — it reads `dienpy hunks list --json` and acts through `hunks patch …`, `hunks branch …`, `hunks use` and `hunks run --extend`, forwarding a config read from the listing, so the analysis vocabulary lives in dienpy alone; the claude subprocess drops `ANTHROPIC_API_KEY` to run on claude.ai login auth. `regroup/review.lua` owns the review-mode diff windows and `regroup/commit.lua` the commit buffer, both shared with the `<leader>gf/gr/gb` pickers in `init.lua`.

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
