# Setup Profiles

Each profile is an independent feature group. A machine declares which profiles it wants; `base` is always implicit. Profiles compose freely — a workstation might run `shell + dev + screen + screen-apps`, a headless dev box runs `shell + dev`, a minimal server runs just `shell`. Steps are idempotent: if the `check` command passes, the step is skipped.

> Phase G will replace this file with `profiles.md` + `paths.md` + `tiers.md` + `ledger.md`. Until then, this is the single doc.

| Profile | Steps | Target env | Test method |
|---------|-------|------------|-------------|
| `base` | apt-base, restow, rust, rclone | any Linux | Docker (actual run) |
| `shell` | cargo-tools (rg/dust/fd/bat/tree-sitter), nushell, lua, luarocks, jq, sc-im, neovim, fzf, tmux | any interactive box | Docker (dry-run; full in `Dockerfile.level1`) |
| `dev` | tectonic, node | dev workstation | Docker (dry-run) |
| `server` | (placeholder; cron/systemd is currently user-managed) | server | — |
| `screen` | apt-desktop, user-groups, leftwm, alacritty, nerd-fonts, x11-config, timezone, grub-quiet | graphical workstation | QEMU (TODO) |
| `screen-apps` | firefox-apt, logseq, bluetooth-autoenable, autologin, network-nm | full workstation | QEMU (TODO) |

`base` runs `restow` between `apt-base` and `rust` so the `.profile` stow symlink is in place before `rust` calls `append_to_profile`.

## Invocation

```
setup run                              # base only
setup run --profile shell              # base + shell
setup run --profile shell --profile dev  # base + shell + dev
SETUP_PROFILES="shell dev" setup run   # equivalent to above (env-driven)
setup verify --profile shell           # verify base + shell steps
setup list                             # all registered steps, grouped by profile
```

`make setup-run PROFILES="shell dev"` and `make setup-verify PROFILES="shell dev"` are equivalent.

## What "success" looks like per profile

**base** — `setup verify` (no flag) passes: `rustc`, `rclone` respond to `--version`; `~/.config/environment.d/10-vars.conf` exists (restow ran).

**shell** — `setup verify --profile shell` passes: all base checks plus `nvim`, `fzf`, `tmux`, `lua`, `luarocks`, `jq`, `rg`, `nu`, `sc-im` respond.

**dev** — all shell checks plus `tectonic` and `node` respond.

**screen** — `startx` launches leftwm; alacritty opens; nerd fonts are listed by `fc-list`.

**screen-apps** — Firefox installed from Mozilla APT (not snap); Logseq binary is linked in `~/.local/bin`; Bluetooth auto-enables on boot.

## Bootstrap path

Fresh-machine flow:

1. `bash bootstrap.sh` — installs `curl`, `git`, `stow`, then `uv` if missing, clones `diencephalon` into `$SYNC_ROOT/composites/pkm/diencephalon`, runs `restow` once so PATH and env vars are live, then calls `make setup-run PROFILES="$PROFILES"` (defaulting to base only).
2. `make setup-run PROFILES="..."` → `uv run setup run --profile ...` — walks the registry and executes each step in the requested profile set (`base` always included), skipping any whose `check` already passes.

Override `PROFILES` env to go further in one shot: `PROFILES="shell dev" bash bootstrap.sh`.

## Prerequisites (not managed by setup)

`uv` must be installed before running any setup command. On a fresh machine, use `bootstrap.sh` which handles this. See `docs/testing.md` for how this is handled in Docker.
