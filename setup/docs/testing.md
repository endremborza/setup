# Testing

## Unit tests

`setup/tests/` contains pytest tests for `runner.py` and `util.py`. These mock subprocess calls and test the step registration, skip logic, and runner behaviour. Run with:

```
cd setup && uv run pytest
```

## Docker (base / shell / dev)

### `tests/Dockerfile`

Standard CI target. Runs the `base` profile for real (installs rust, rclone) and `shell + dev` as a dry-run (validates step registration and import paths without the expensive builds).

```
docker build -f tests/Dockerfile .
```

`base` executes real installs. `apt-base` is skipped if `build-essential` is already present in the base image.

### `tests/Dockerfile.level1`

Full `base + shell + dev` execution followed by `setup verify --profile shell --profile dev`. Includes neovim build from source, lua, tmux — takes 20–40 minutes. Run manually or in nightly CI only. (File name is historical; phase F will rename / replace it.)

```
docker build -f tests/Dockerfile.level1 .
```

### `dienpy versions upgrade-system --test`

Driven by `dienpy`, not directly by this package. Bumps `versions.toml` to latest upstream tags, builds a fresh image from `tests/Dockerfile.level1`, then runs `setup verify --profile shell --profile dev` inside the container to confirm each tool works. Results are written to `docs/upgrade-report.md`.

## QEMU (screen / screen-apps)

Graphical and system-level profiles cannot be tested in Docker. See `tests/qemu/README.md` for the intended workflow. Not yet implemented — Docker tests are the CI gate.

## Verify step

After any setup run, `setup verify --profile ...` executes the `verify` command registered on each step and reports pass/fail. This is distinct from `check` (which decides whether to skip installation) — `verify` confirms the result of a completed install.

```
setup run --profile shell
setup verify --profile shell
```

Exit code is 0 if all verify commands pass, 1 otherwise.
