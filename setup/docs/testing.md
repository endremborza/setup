# Testing

## Unit tests

`setup/tests/` contains pytest tests for `runner.py` and `util.py`. These mock subprocess calls and test the step registration, skip logic, and runner behaviour. Run with:

```
cd setup && uv run pytest
```

## Docker (levels 0–1)

### `tests/Dockerfile`

Standard CI target. Runs level 0 for real (installs rust, rclone) and level 1 as a dry-run (validates step registration and import paths without the expensive builds).

```
docker build -f tests/Dockerfile .
```

Level 0 executes real installs. `apt-base` is skipped if `build-essential` is already present in the base image.

### `tests/Dockerfile.level1`

Full level-0 + level-1 execution followed by `setup verify --level 1`. Includes neovim build from source, lua, tmux — takes 20–40 minutes. Run manually or in nightly CI only.

```
docker build -f tests/Dockerfile.level1 .
```

### `dienpy versions upgrade-system --test`

Driven by `dienpy`, not directly by this package. Bumps `versions.toml` to latest upstream tags, builds a fresh image from `tests/Dockerfile.level1`, then runs `setup verify --level 1` inside the container to confirm each tool works. Results are written to `docs/upgrade-report.md`.

## QEMU (levels 3–4)

Graphical and system-level steps cannot be tested in Docker. See `tests/qemu/README.md` for the intended workflow. Not yet implemented — Docker tests are the CI gate.

## Verify step

After any level run, `setup verify --level N` executes the `verify` command registered on each step and reports pass/fail. This is distinct from `check` (which decides whether to skip installation) — `verify` confirms the result of a completed install.

```
setup run --level 1
setup verify --level 1
```

Exit code is 0 if all verify commands pass, 1 otherwise.
