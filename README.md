# diencephalon

Public dotfiles, scripts, and bootstrap tooling. No secrets, no personal paths - generalizable config

| Directory | Purpose |
|-----------|---------|
| `dotfiles/` | Generic dotfiles stowed to `~` via GNU stow |
| `setup/`    | Profile-based system bootstrap (Python CLI: `setup`) |
| `dienpy/`   | Public Python CLI toolkit (`dienpy <module>`) |
| `util/`     | systemd service/socket templates |

## Quick start

### Fresh machine

```bash
curl -fsSL https://raw.githubusercontent.com/endremborza/setup/main/setup/bootstrap.sh | bash
```

Installs `uv`, clones the repo to `$SYNC_ROOT/composites/pkm/diencephalon`, stows dotfiles, runs `setup run` (base profile only).

Bootstrap also takes `--tier {hub,member,guest}` — see [SETUP.md](SETUP.md#bootstrap-tiers). Set `PROFILES="shell dev"` env to push further in one shot.

### Existing machine

```bash
git clone https://github.com/endremborza/setup diencephalon
cd diencephalon
make install
```

## Setup profiles

A profile is an independent feature group. `base` is always implicit; layer others as needed.

| Profile        | Installs                                                          |
|----------------|-------------------------------------------------------------------|
| `base`         | apt-base, restow, rust, rclone                                    |
| `shell`        | cargo-tools, nushell, lua, luarocks, jq, sc-im, neovim, fzf, tmux |
| `dev`          | tectonic, node                                                    |
| `screen`       | xorg, leftwm, alacritty, nerd-fonts, X11 config                   |
| `screen-apps`  | firefox-apt, logseq, bluetooth, autologin, network-nm             |
| `wg`           | wireguard (interface config is the enroller's job)                |
| `web`          | caddy (Caddyfile + service state are the fleet controller's job)  |
| `edge`         | nftables default-deny input, unattended-upgrades                  |
| `media`        | HWE kernel, mpv, gamescope, cage, firefox — HDR playback box      |

```bash
setup run                                # base only
setup run -p shell -p dev                # base + shell + dev
setup verify -p shell                    # check installed bricks respond
setup list                               # all registered bricks
SETUP_PROFILES="shell dev" setup run     # env-driven equivalent
```

Bricks are idempotent: if a brick's `check` command passes, it's skipped. Use `--force` to rerun anyway. Full profile reference, env propagation, and testing recipes live in [SETUP.md](SETUP.md).

## Makefile

| Target | Description |
|--------|-------------|
| `make install`              | Install `dienpy` as a uv tool (drags in `setup` editable) |
| `make setup-run`            | `uv run setup run` for `$PROFILES` (default: `shell`)     |
| `make setup-verify`         | Verify bricks in `$PROFILES`                               |
| `make setup-list`           | List all registered bricks                                 |
| `make test`                 | Pytest suite for the `setup` package                      |
| `make docker-ci`            | Fast CI gate: base real + shell/dev dry-run               |
| `make docker-test`          | Full real build + verify (~30 min)                        |
| `make docker-bootstrap`     | End-to-end test of `bootstrap.sh`                         |

## Version management

Pinned versions live in `setup/versions.toml`. Managed via `dienpy versions`:

```bash
dienpy versions list                    # show pinned + installed
dienpy versions check                   # fetch latest tags from upstream
dienpy versions bump <tool> <tag>       # pin a specific tag
dienpy versions upgrade-system          # dry-run preview
dienpy versions upgrade-system --live   # install where pinned ≠ installed
```

## dienpy CLI

See [`dienpy/AGENTS.md`](dienpy/AGENTS.md) for the full module list.

```bash
dienpy nvim release_notes      # plugin changelog digest
dienpy nvim verify --perf      # headless LSP health check
dienpy ai commit               # AI-assisted commit message
```

## Further reading

- [AGENTS.md](AGENTS.md) — repo conventions, how to add a brick, nvim internals
- [SETUP.md](SETUP.md) — full profile reference, bootstrap, environment propagation, testing
