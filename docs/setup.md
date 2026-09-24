# Setup

Deep reference for the `setup` package: profile catalog, bootstrap, environment propagation, testing. User-facing quickstart is in [README.md](../README.md); architectural conventions are in [AGENTS.md](../AGENTS.md).

## Profiles

A profile is an independent feature group. `base` is always implicit. Profiles compose freely — a workstation runs `shell + dev + screen + screen-apps`, a headless dev box runs `shell + dev`, a minimal server runs `shell` only. Bricks are idempotent: if `check` passes, the brick is skipped (unless `--force`).

| Profile | Bricks | Target | Test gate |
| --- | --- | --- | --- |
| `base` | apt-base, restow, rust, rclone | any Linux | Docker (real) |
| `shell` | cargo-tools (rg/dust/fd/bat/tree-sitter), lua, luarocks, jq, sc-im, neovim, fzf, tmux, tpm | any interactive box | Docker (dry; full in `Dockerfile.full`) |
| `dev` | tectonic, node, bun | dev workstation | Docker (dry) |
| `screen` | apt-desktop, user-groups, leftwm, alacritty, nerd-fonts, x11-config, timezone, grub-quiet | graphical workstation | (QEMU — not implemented) |
| `screen-apps` | firefox-apt, logseq, bluetooth-autoenable, autologin, network-nm | full workstation | (QEMU — not implemented) |
| `wg` | wireguard | every fleet machine | Docker (dry) |
| `web` | caddy | web-serving machine | manual (fleet push) |
| `docker` | docker | machine hosting fleet apps | manual (fleet update) |
| `edge` | nftables-deny, unattended-upgrades | public-facing server | manual (live VPS) |
| `media` | hwe-kernel, media-stack (mpv/cage/alsa/edid-decode), firefox-apt + autologin (shared); tty1 execs `tv-session` | media playback box | manual (bench) |

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
- **shell** — all base checks plus `nvim`, `fzf`, `tmux`, `lua`, `luarocks`, `jq`, `rg`, `sc-im` respond at their pinned versions; `~/.tmux/plugins/tpm` is linked.
- **dev** — shell checks plus `tectonic`, `node` and `bun`.
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

| Layer | File | Source | Content |
| --- | --- | --- | --- |
| 1 | `~/.vars` | diencephalon | Base paths, tool config |
| 2 | `~/.secret-vars` | hypothalamus/secrets | API keys, tokens |
| 3 | `~/.local-vars` | hypothalamus/local-dotfiles/host-$(hn) | Machine-specific (GPU, ports, hw, `TIMEZONE`, `TTY1_SESSION`) |

Each layer can reference earlier ones. `.profile` loads them in order; everything a login starts (X, tmux, services) inherits them from there. `~/synced` is the one root — symlink it where the tree lives elsewhere, since every derived path and the generated `environment.d` come from it.

### Boot-to-desktop flow

```
tty1 login
  └─ .profile
       ├─ sources .bashrc (unmanaged; uv's ~/.local/bin/env lives there)
       ├─ prepends ~/bin, ~/.local/bin, ~/.elan/bin (guarded: tmux logins source this again), sources ~/.cargo/env
       ├─ sources .vars → .secret-vars → .local-vars
       └─ if no DISPLAY on tty1: exec $TTY1_SESSION (default startx; "none" stays in the console; a kiosk names its launcher)
            └─ .xinitrc
                 ├─ xrdb, setxkbmap, xset
                 ├─ exports XDG_SESSION_TYPE=x11, XDG_CURRENT_DESKTOP=LeftWM, DBUS_SESSION_BUS_ADDRESS (the systemd user bus)
                 ├─ dbus-update-activation-environment --systemd DISPLAY XAUTHORITY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP
                 ├─ starts graphical-session{-pre,}.target
                 └─ leftwm
                      └─ themes/current/up: loads the theme, starts polybar
```

### systemd integration

**environment.d (static).** `restow` generates `~/.config/environment.d/{10,20,30}-*.conf` from the three layers in a clean shell, so their content depends on the files alone; a literal `$` is written `$$` because environment.d expands `$VAR` itself. The stowed `99-path.conf` puts `~/.local/bin` and `~/.cargo/bin` on the manager's PATH. `restow` ends with `systemctl --user daemon-reload`, which re-reads them; a running service sees changes on restart.

**Display access (dynamic).** `.xinitrc` runs `dbus-update-activation-environment --systemd` with the four display variables: bus-activated apps and (`--systemd`) user services started afterwards see them. Nothing imports the whole shell environment.

**One bus.** The X session runs on the systemd user bus (`$XDG_RUNTIME_DIR/bus`). dunst is a bus-activated user service (`dunst.service`, `PartOf=graphical-session.target`), so nothing starts or kills it by hand.

### tmux gotcha

tmux captures env when its **server** starts (first session). `update-environment` (`DISPLAY` and `XAUTHORITY` are in its default) propagates from the **attaching client** on `attach-session`/`new-session`; `new-window` does not trigger it. A launcher that creates a session without an attached client and then adds windows has to `tmux set-environment -g DISPLAY … XAUTHORITY …` itself.

### XDG_SESSION_TYPE

logind sets `XDG_SESSION_TYPE=tty` when logging in via tty1 + `startx`, and never updates it. Some apps (including snap-confined ones) check this. `.xinitrc` exports `XDG_SESSION_TYPE=x11` and pushes it to systemd with the display variables. Only affects the env, not the actual logind session type (`loginctl` still reports `tty`).

### Headless stations

- `.profile` sources vars but does not exec a session (no tty1 or DISPLAY already set, or `TTY1_SESSION=none` in `.local-vars`).
- Services rely solely on `environment.d`.
- No `DISPLAY`/`XAUTHORITY`/`XDG_SESSION_TYPE`. tmux has no display vars.

Run `restow` after any `.vars/.secret-vars/.local-vars` change; a running service picks it up on restart.

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

| Recipe | Dockerfile | What |
| --- | --- | --- |
| `make docker-ci` | `setup/tests/Dockerfile` | base real + shell/dev dry-run (fast CI gate) |
| `make docker-test` | `setup/tests/Dockerfile.full` | base + shell + dev real + verify (~30 min, nightly) |
| `make docker-bootstrap` | `setup/tests/Dockerfile.bootstrap` | End-to-end: clones from file://, runs `bootstrap.sh` |

### Pins and upgrades

`setup/versions.toml` pins one tag per tool. A pinned brick's `check` is `pinned_check(cmd, tag)` (`setup/util.py`): it passes only when the tool prints the pinned number, so `dienpy versions bump <tool> <tag>` fails that check on every machine and the next `setup run` (or `fleet update`) rebuilds the tool at the new pin. There is no separate upgrade path — a bump is applied by the same idempotent run as a fresh install. `dienpy versions check` reports which pins are behind upstream.

### QEMU (screen / screen-apps)

Graphical and system-level profiles can't run in Docker. Not yet implemented — Docker is the CI gate. The intended sketch:

1. boot Ubuntu cloud image with cloud-init seeded user + SSH key
2. `ssh qemu-target 'setup run -p screen -p screen-apps' | tee log`
3. `ssh qemu-target 'setup verify -p screen -p screen-apps'`
4. shut down, delete ephemeral disk

### check vs verify

- `check` decides whether to *skip* a brick (already-installed guard). Cheap. After an install the runner re-runs it, and a brick whose check still fails is reported as failed.
- `verify` confirms the result of a completed install. Run by `setup verify`. Exit code 0 iff all verify commands pass. It defaults to `check`; a brick declares its own only when the install guard is not the right smoke test (e.g. `media-stack` checks packages, verifies binaries).
