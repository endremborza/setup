# Setup Levels

Each level is a strictly additive group of steps. Running level N also runs all levels below it. Steps are idempotent: if the `check` command passes, the step is skipped.

| Level | Steps | Target env | Test method |
|-------|-------|------------|-------------|
| 0 | apt-base, rust, rclone | any Linux | Docker (actual run) |
| 1 | tectonic, cargo-tools, nushell, lua, luarocks, jq, sc-im, neovim, fzf, tmux, node, restow | headless dev | Docker (dry-run; full in `Dockerfile.level1`) |
| 2 | systemd services, cron jobs | server | Docker-systemd or QEMU |
| 3 | xorg, leftwm, alacritty, nerd-fonts, x11-config, timezone, grub | workstation | QEMU |
| 4 | firefox, logseq, bluetooth, autologin, network-nm | workstation-full | QEMU |

## What "success" looks like per level

**Level 0** — `setup verify --level 0` passes: `rustc`, `rclone` respond to `--version`.

**Level 1** — `setup verify --level 1` passes: all level-0 checks plus `nvim`, `fzf`, `tmux`, `lua`, `luarocks`, `jq`, `node`, `rg` all respond; `~/.config/environment.d/10-vars.conf` exists (restow ran).

**Level 2** — systemd user services are enabled and active; cron jobs are present in crontab.

**Level 3** — `startx` launches leftwm; alacritty opens; nerd fonts are listed by `fc-list`.

**Level 4** — Firefox installed from Mozilla APT (not snap); Logseq binary is linked in `~/.local/bin`; Bluetooth auto-enables on boot.

## Prerequisites (not managed by setup)

`uv` must be installed before running any setup level. On a fresh machine, use `bootstrap.sh` which handles this. See `docs/testing.md` for how this is handled in Docker.
