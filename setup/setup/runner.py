from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Callable

REGISTRY: list[Step] = []

BASE_PROFILE = "base"


@dataclass
class Step:
    fn: Callable[[], None]
    name: str
    profile: str
    check: str | None = None
    verify: str | None = None


def step(
    profile: str,
    name: str,
    check: str | None = None,
    verify: str | None = None,
) -> Callable:
    def decorator(fn: Callable[[], None]) -> Callable[[], None]:
        REGISTRY.append(
            Step(fn=fn, name=name, profile=profile, check=check, verify=verify)
        )
        return fn

    return decorator


def _check_passes(cmd: str) -> bool:
    return subprocess.run(cmd, shell=True, capture_output=True).returncode == 0


def _run_check(cmd: str) -> tuple[bool, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def _resolve_profiles(profiles: Iterable[str] | None) -> set[str]:
    """`base` is always implicit; add anything else the caller asked for."""
    return {BASE_PROFILE, *(profiles or ())}


def _steps_for(profiles: Iterable[str] | None, step_name: str | None) -> list[Step]:
    if step_name is not None:
        matched = [s for s in REGISTRY if s.name == step_name]
        if not matched:
            raise SystemExit(f"No step named {step_name!r}")
        return matched
    wanted = _resolve_profiles(profiles)
    return [s for s in REGISTRY if s.profile in wanted]


def run(
    profiles: Iterable[str] | None,
    dry_run: bool = False,
    step_name: str | None = None,
) -> None:
    for s in _steps_for(profiles, step_name):
        if not dry_run and s.check and _check_passes(s.check):
            print(f"[skip] {s.name}")
            continue
        if dry_run:
            print(f"[dry ] {s.name}")
            continue
        try:
            s.fn()
            print(f"[ ok ] {s.name}")
        except Exception as e:
            print(f"[FAIL] {s.name}: {e}")


def update(step_name: str | None = None) -> None:
    if step_name is None:
        targets = list(REGISTRY)
    else:
        targets = [s for s in REGISTRY if s.name == step_name]
        if not targets:
            raise SystemExit(f"No step named {step_name!r}")
    for s in targets:
        try:
            s.fn()
            print(f"[ ok ] {s.name}")
        except Exception as e:
            print(f"[FAIL] {s.name}: {e}")


def verify(profiles: Iterable[str] | None, step_name: str | None = None) -> bool:
    steps = [s for s in _steps_for(profiles, step_name) if s.verify]
    if not steps:
        print("No verify commands registered for this profile set.")
        return True
    all_ok = True
    for s in steps:
        ok, output = _run_check(s.verify)
        if ok:
            summary = output.splitlines()[0] if output else ""
            print(f"[ ok ] {s.name}  {summary}")
        else:
            print(f"[FAIL] {s.name}  cmd={s.verify!r}")
            for line in output.splitlines()[:8]:
                print(f"       {line}")
        if not ok:
            all_ok = False
    return all_ok
