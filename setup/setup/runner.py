from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

REGISTRY: list[Step] = []


@dataclass
class Step:
    fn: Callable[[], None]
    name: str
    level: int
    check: str | None = None
    verify: str | None = None


def step(
    level: int,
    name: str,
    check: str | None = None,
    verify: str | None = None,
) -> Callable:
    def decorator(fn: Callable[[], None]) -> Callable[[], None]:
        REGISTRY.append(Step(fn=fn, name=name, level=level, check=check, verify=verify))
        return fn

    return decorator


def _check_passes(cmd: str) -> bool:
    return subprocess.run(cmd, shell=True, capture_output=True).returncode == 0


def _steps_for(level: int | None, step_name: str | None) -> list[Step]:
    if step_name is not None:
        matched = [s for s in REGISTRY if s.name == step_name]
        if not matched:
            raise SystemExit(f"No step named {step_name!r}")
        return matched
    return [s for s in REGISTRY if s.level <= (level or 0)]


def run(level: int, dry_run: bool = False, step_name: str | None = None) -> None:
    for s in _steps_for(level, step_name):
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
    for s in _steps_for(None if step_name is None else 99, step_name):
        try:
            s.fn()
            print(f"[ ok ] {s.name}")
        except Exception as e:
            print(f"[FAIL] {s.name}: {e}")


def verify(level: int, step_name: str | None = None) -> bool:
    steps = [s for s in _steps_for(level, step_name) if s.verify]
    if not steps:
        print("No verify commands registered for this level.")
        return True
    all_ok = True
    for s in steps:
        ok = _check_passes(s.verify)
        print(f"{'[ ok ]' if ok else '[FAIL]'} {s.name}")
        if not ok:
            all_ok = False
    return all_ok
