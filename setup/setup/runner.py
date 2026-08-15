from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Callable

REGISTRY: list[Brick] = []

BASE_PROFILE = "base"


@dataclass
class Brick:
    fn: Callable[[], None]
    name: str
    profile: str | tuple[str, ...]
    check: str | None = None
    verify: str | None = None

    @property
    def profiles(self) -> tuple[str, ...]:
        return (self.profile,) if isinstance(self.profile, str) else self.profile

    @property
    def profile_label(self) -> str:
        return "/".join(self.profiles)


def brick(
    profile: str | tuple[str, ...],
    name: str,
    check: str | None = None,
    verify: str | None = None,
) -> Callable:
    def decorator(fn: Callable[[], None]) -> Callable[[], None]:
        REGISTRY.append(
            Brick(fn=fn, name=name, profile=profile, check=check, verify=verify)
        )
        return fn

    return decorator


def run_check(cmd: str) -> tuple[bool, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def check_passes(cmd: str) -> bool:
    return run_check(cmd)[0]


def _resolve_profiles(profiles: Iterable[str] | None) -> set[str]:
    return {BASE_PROFILE, *(profiles or ())}


def _bricks_for(profiles: Iterable[str] | None, brick_name: str | None) -> list[Brick]:
    if brick_name is not None:
        matched = [b for b in REGISTRY if b.name == brick_name]
        if not matched:
            raise SystemExit(f"No brick named {brick_name!r}")
        return matched
    wanted = _resolve_profiles(profiles)
    return [b for b in REGISTRY if wanted & set(b.profiles)]


def _invoke(b: Brick) -> None:
    try:
        b.fn()
        print(f"[ ok ] {b.name}")
    except Exception as e:
        print(f"[FAIL] {b.name}: {e}")


def run(
    profiles: Iterable[str] | None,
    dry_run: bool = False,
    brick_name: str | None = None,
    force: bool = False,
) -> None:
    for b in _bricks_for(profiles, brick_name):
        if dry_run:
            print(f"[dry ] {b.name}")
        elif not force and b.check and check_passes(b.check):
            print(f"[skip] {b.name}")
        else:
            _invoke(b)


def verify(profiles: Iterable[str] | None, brick_name: str | None = None) -> bool:
    bricks = [b for b in _bricks_for(profiles, brick_name) if b.verify]
    if not bricks:
        print("No verify commands registered for this profile set.")
        return True
    all_ok = True
    for b in bricks:
        ok, output = run_check(b.verify)
        if ok:
            summary = output.splitlines()[0] if output else ""
            print(f"[ ok ] {b.name}  {summary}")
        else:
            print(f"[FAIL] {b.name}  cmd={b.verify!r}")
            for line in output.splitlines()[:8]:
                print(f"       {line}")
            all_ok = False
    return all_ok
