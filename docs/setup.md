# Setup

Deep reference for the `setup` package: profile catalog, bootstrap, environment propagation, testing. User-facing quickstart is in [README.md](../README.md); architectural conventions are in [AGENTS.md](../AGENTS.md).

## Profiles

A profile is an independent feature group. `base` is always implicit. Profiles compose freely — a workstation runs `shell + dev + screen + screen-apps`, a headless dev box runs `shell + dev`, a minimal server runs `shell` only. Bricks are idempotent: if `check` passes, the brick is skipped (unless `--force`).

| Profile        | Bricks                                                                         | Target                | Test gate            |
|----------------|--------------------------------------------------------------------------------|-----------------------|----------------------|
| `base`         | apt-base, restow, rust, rclone                                                 | any Linux             | Docker (real)        |
| `shell`        | cargo-tools (rg/dust/fd/bat/tree-sitter), nushell, lua, luarocks, jq, sc-im, neovim, fzf, tmux | any interactive box | Docker (dry; full in `Dockerfile.full`) |
| `dev`          | tectonic, node                                                                 | dev workstation       | Docker (dry)         |
| `screen`       | apt-desktop, user-groups, leftwm, alacritty, nerd-fonts, x11-config, timezone, grub-quiet | graphical workstation | (QEMU — not implemented) |
| `screen-apps`  | firefox-apt, logseq, bluetooth-autoenable, autologin, network-nm               | full workstation      | (QEMU — not implemented) |
| `wg`           | wireguard                                                                       | every fleet machine   | Docker (dry)         |
| `web`          | caddy                                                                           | web-serving machine   | manual (fleet push)  |
| `docker`       | docker                                                                          | machine hosting fleet apps | manual (fleet update) |
| `edge`         | nftables-deny, unattended-upgrades                                              | public-facing server  | manual (live VPS)    |
| `media`        | hwe-kernel, media-stack (mpv/gamescope/cage/alsa), firefox-apt (shared)         | media playback box    | manual (bench)       |

`base` runs `restow` between `apt-base` and `rust` so the `.profile` stow symlink is in place before `rust` calls `append_to_profile` (otherwise that creates a conflicting real file).

### Invocation

```bash
setup run                                # base only
setup run -p shell                       # base + shell
setup run -p shell -p dev                # base + shell + dev
setup run -p shell --force               # rerun even if check passes
setup run -b neovim                      # one named brick
setup run -n -p shell                    # dry-run
setup verify -p shell                    # exit 0 iff all verify cmds pass
setup list                               # registered bricks, grouped by profile
SETUP_PROFILES="shell dev" setup run     # env-driven
```

`make setup-run PROFILES="shell dev"` and `make setup-verify PROFILES="shell dev"` are equivalent wrappers.

### Success criteria per profile

- **base** — `rustc`, `rclone` respond to `--version`; `~/.config/environment.d/10-vars.conf` exists (restow ran).
- **shell** — all base checks plus `nvim`, `fzf`, `tmux`, `lua`, `luarocks`, `jq`, `rg`, `nu`, `sc-im` respond.
- **dev** — shell checks plus `tectonic` and `node`.
- **screen** — `startx` launches leftwm; alacritty opens; nerd fonts listed by `fc-list`.
- **screen-apps** — Firefox installed from Mozilla APT (not snap); Logseq linked in `~/.local/bin`; Bluetooth auto-enables on boot.
- **wg** — `wg` responds; interface config/keys are the fleet controller's job (`/etc/wireguard` stays empty until enrollment).
- **web** — `caddy` responds; `/etc/caddy/Caddyfile` and service state are the fleet controller's job (rendered from its inventory, deployed on update).
- **edge** — nftables active with a default-deny input policy (lo, established, icmp, 22/80/443, 51820/udp excepted); unattended-upgrades enabled. The forward chain is deliberately left to `/etc/nftables.d/*.conf` includes, pushed by the fleet controller on wg-hub machines.

## Bootstrap

`setup/bootstrap.sh` is the fresh-machine entry point. It installs `curl/git/stow/make/uv`, clones `diencephalon`, moves any real file that would block a stow symlink (distro skeleton rc files, previous hand-managed configs) to `~/pre-stow-backup/` preserving paths, runs `restow`, then `make setup-run PROFILES="$PROFILES"`. This makes it safe on previously-lived-in machines, not just fresh installs.

It is public-only: diencephalon alone, which is what every leaf and edge machine needs. Remote machines are normally driven by the private fleet controller (hypothalamus `fleet init/update/verify`), which pushes this script over SSH, composes profiles per machine, and places private repos where a machine's identity calls for them.

Env knobs:

- `SYNC_ROOT` — default `$HOME/synced`
- `PROFILES` — default empty (base only); space-separated, e.g. `"shell dev"`
- `DIENCEPHALON_URL` — default `https://github.com/endremborza/setup`; override for tests/file:// clones

Push further in one shot: `PROFILES="shell dev" bash bootstrap.sh`.

`uv` is the only prerequisite. `bootstrap.sh` installs it if missing; the Docker test images install it via `make install-uv`.

## Environment propagation

### Three layers

| Layer | File              | Source                                  | Content                            |
|-------|-------------------|-----------------------------------------|------------------------------------|
| 1     | `~/.vars`         | diencephalon                            | Base paths, tool config            |
| 2     | `~/.secret-vars`  | hypothalamus/secrets                    | API keys, tokens                   |
| 3     | `~/.local-vars`   | hypothalamus/local-dotfiles/host-$(hn)  | Machine-specific (GPU, ports, hw)  |

Each layer can reference earlier ones. Loaded in order by `.profile` and `.xinitrc`.

### Boot-to-desktop flow

```
tty1 login
  └─ .profile
       ├─ sources .bashrc
       ├─ adds ~/bin, ~/.local/bin to PATH
       ├─ sources ~/.local/bin/env (uv), ~/.cargo/env
       ├─ sources .vars → .secret-vars → .local-vars
       └─ if no DISPLAY on tty1: exec startx
            └─ .xinitrc
                 ├─ xrdb, setxkbmap, xset
                 ├─ sources .vars → .secret-vars → .local-vars (again, for X)
                 ├─ exports XDG_SESSION_TYPE=x11, XDG_CURRENT_DESKTOP=LeftWM
                 ├─ systemctl --user import-environment    # shell env → systemd
                 ├─ dbus-update-activation-environment --systemd DISPLAY XAUTHORITY
                 ├─ starts graphical-session{-pre,}.target
                 └─ dbus-run-session leftwm
                      └─ themes/current/up
                           ├─ sources .profile
                           ├─ starts dunst, polybar
                           └─ user runs lwup
```

### systemd integration

**environment.d (static).** `restow` auto-generates `~/.config/environment.d/{10,20,30}-*.conf` by shell-expanding each layer. Loaded once by `systemd --user` at manager startup. Changes require `systemctl --user daemon-reload` + service restart, or a full re-login.

**import-environment (dynamic).** `.xinitrc` runs `systemctl --user import-environment` after X starts, pushing the live shell env (including `DISPLAY`, `XAUTHORITY`, XDG overrides) into systemd so subsequently-started services see them.

**dbus.** `.xinitrc` also runs `dbus-update-activation-environment --systemd DISPLAY XAUTHORITY` so dbus-activated services get display access.

### tmux gotcha

tmux captures env when its **server** starts (first session). The `update-environment` option propagates from the **attaching client** to the session on `attach-session` or `new-session`.

Problem: `lwup` creates `main-bg` before/without a client that has `DISPLAY` set, so the tmux server inherits an env without it, and `new-window` does *not* trigger `update-environment` — only attach does.

Fix: `.tmux.conf` adds session-level vars via `update-environment`, and `lwup` sets the global tmux env explicitly after session creation:

```bash
tmux set-environment -g DISPLAY "$DISPLAY"
tmux set-environment -g XAUTHORITY "$XAUTHORITY"
```

### XDG_SESSION_TYPE

logind sets `XDG_SESSION_TYPE=tty` when logging in via tty1 + `startx`, and never updates it. Some apps (including snap-confined ones) check this. `.xinitrc` exports `XDG_SESSION_TYPE=x11` before `import-environment`. Only affects the env, not the actual logind session type (`loginctl` still reports `tty`).

### Headless stations

- `.profile` sources vars but does not `exec startx` (no tty1 or DISPLAY already set).
- Services rely solely on `environment.d` files generated by `restow`.
- No `DISPLAY`/`XAUTHORITY`/`XDG_SESSION_TYPE`. tmux has no display vars.

Run `restow` after any `.vars/.secret-vars/.local-vars` change, then `systemctl --user daemon-reload`.

### Debugging

```bash
# What does the systemd user manager see?
systemctl --user show-environment | grep -E 'DISPLAY|XDG_|DBUS_|XAUTH'

# What does the shell see?
echo "DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY XDG_SESSION_TYPE=$XDG_SESSION_TYPE"

# What does tmux server see?
tmux show-environment | grep -E 'DISPLAY|XAUTH'

# Login session type
loginctl show-session $(loginctl --no-legend | awk '{print $1}') -p Type

# environment.d files
ls -la ~/.config/environment.d/ && head -5 ~/.config/environment.d/10-vars.conf
```

## Testing

### Unit tests

```bash
make test                # or: cd setup && uv run pytest
```

Mocks `subprocess` and tests the brick registration, skip logic, profile resolution, and verify behaviour.

### Docker

| Recipe                           | Dockerfile                              | What                                                    |
|----------------------------------|-----------------------------------------|---------------------------------------------------------|
| `make docker-ci`                 | `setup/tests/Dockerfile`                | base real + shell/dev dry-run (fast CI gate)            |
| `make docker-test`               | `setup/tests/Dockerfile.full`           | base + shell + dev real + verify (~30 min, nightly)     |
| `make docker-bootstrap`          | `setup/tests/Dockerfile.bootstrap`      | End-to-end: clones from file://, runs `bootstrap.sh`    |

### `dienpy versions upgrade-system`

Bumps `versions.toml` to latest upstream tags, builds a fresh image from `Dockerfile.full`, runs `setup verify -p shell -p dev` inside. Driven by dienpy, not setup directly.

### QEMU (screen / screen-apps)

Graphical and system-level profiles can't run in Docker. Not yet implemented — Docker is the CI gate. The intended sketch:

1. boot Ubuntu cloud image with cloud-init seeded user + SSH key
2. `ssh qemu-target 'setup run -p screen -p screen-apps' | tee log`
3. `ssh qemu-target 'setup verify -p screen -p screen-apps'`
4. shut down, delete ephemeral disk

### check vs verify

- `check` decides whether to *skip* a brick (already-installed guard). Cheap.
- `verify` confirms the result of a completed install. Run by `setup verify`. Exit code 0 iff all verify commands pass.
