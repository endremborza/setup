"""Test support for code that goes through moac; a package's conftest imports the fixture."""

import os
from pathlib import Path

import pytest

from . import _account, _profiles


@pytest.fixture(autouse=True)
def no_host_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No moac.toml and no inherited account, whatever the machine or session running the tests."""
    monkeypatch.setattr(_profiles, "PATH", tmp_path / "moac.toml")
    monkeypatch.delenv(_account.ENV_VAR, raising=False)
    monkeypatch.delenv(_account.CONFIG_DIR_VAR, raising=False)


def fake_claude(tmp_path: Path, monkeypatch, script: str) -> Path:
    """A `claude` on PATH that runs `script` (sh) instead; its argv arrives as "$@"."""
    fake = tmp_path / "claude"
    fake.write_text(f"#!/bin/sh\n{script}\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return fake
