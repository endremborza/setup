# diencephalon

Public dotfiles, scripts, and tooling. Config files in `dotfiles/` are symlinked to `~` via GNU stow (see `dotfiles/.local/bin/restow`). **Public repo** — generalizable config and tools that others could draw inspiration from. No secrets, no personal paths.

## Repository structure

| Directory | Purpose |
|-----------|---------|
| `dienpy/` | Public Python CLI toolkit (`dienpy <module> [args]`). See `dienpy/AGENTS.md`. |
| `dotfiles/` | Generic dotfiles stowed to `~` via GNU stow (nvim, alacritty, tmux, leftwm, shell config, utility scripts). |
| `setup/` | Leveled system bootstrap package. See `setup/docs/`. |
| `util/` | Templates (systemd service/socket) used by `create-service`. |

## Boundary rule

This repo must contain **only** generalizable, public-safe content. Anything referencing personal paths (`/home/<user>/...`), secrets, specific hostnames, or personal services belongs in a private companion repo. The dependency direction: private repos may depend on this one, never the reverse.

## Stow integration

`dotfiles/.local/bin/restow` stows this repo's `dotfiles/` to `~` with `--no-folding`. A private companion can stow additional dotfiles alongside — GNU stow merges directories, so both repos can contribute files to `~/.local/bin/` without conflict as long as no filename appears in both.

## Environment variables

`dotfiles/.vars` defines the base env layer: `SYNC_ROOT` and all derived paths. Shell startup (`.profile`) sources this file. `dienpy/dienpy/constants.py` mirrors these with hardcoded defaults for bootstrap.

## nvim config

Lives at `dotfiles/.config/nvim/init.lua`. Uses lazy.nvim + mason + mason-lspconfig (v2 API, Neovim 0.11+).

### Key decisions

- **LSP config**: `vim.lsp.config('server', {...})` per-server + `automatic_enable = true`.
- **Non-file buffer guard**: `vim.lsp.start` is wrapped to prevent LSP on non-file buffers (`fugitive://`, `gitsigns://`, `term://`).
- **lazydev.nvim**: Provides `vim` global type info to lua_ls. Must be a dependency of nvim-lspconfig with `ft = 'lua'`.

### Workflows

#### Updating nvim or plugins

1. `dienpy nvim release_notes` — fetch recent release notes for all plugins
2. Review for breaking changes
3. `:Lazy update`
4. `dienpy nvim verify --perf` — headless LSP health check
5. `dienpy nvim commit` — commit with plugin version snapshot

#### Diagnosing LSP issues

1. `dienpy nvim verify --perf`
2. `:LspInfo`, `:LspLog`
3. Check mason install: `~/.local/share/nvim/mason/bin/<server>`
4. Check lazy-lock.json vs upstream changelogs

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
