from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from setup.runner import run_check
from setup.util import (
    dpkg_check,
    extended_env,
    pinned_check,
    run_shell,
    write_system_file,
)


def test_extended_env_prepends_cargo_and_local_bin():
    env = extended_env()
    parts = env["PATH"].split(":")
    assert str(Path.home() / ".cargo/bin") in parts[:4]
    assert str(Path.home() / ".local/bin") in parts[:4]


def test_extended_env_preserves_existing_path():
    with patch.dict(os.environ, {"PATH": "/original/bin"}):
        env = extended_env()
    assert "/original/bin" in env["PATH"]


@pytest.mark.parametrize(
    ("printed", "tag", "passes"),
    [
        ("tmux 3.7c", "3.7c", True),
        ("jq-1.8.2", "jq-1.8.2", True),
        ("NVIM v0.12.5", "v0.12.5", True),
        ("Tectonic 0.17.0", "tectonic@0.17.0", True),
        ("rustc 1.95.0 (abc 2026-04-14)", "1.95.0", True),
        ("jq-1.8.21", "jq-1.8.2", False),
        ("tmux 3.7", "3.7c", False),
        ("alacritty 0.13.2", "v0.17.0", False),
    ],
)
def test_pinned_check_matches_the_number_only(printed, tag, passes):
    ok, output = run_check(pinned_check(f"echo '{printed}'", tag))
    assert ok is passes
    if passes:
        assert output == printed


def _fake_dpkg_query(tmp_path: Path, statuses: dict[str, str]) -> None:
    script = ["#!/bin/sh", "shift 2", 'for p in "$@"; do case $p in']
    script += [f"{p}) echo '{s}';;" for p, s in statuses.items()]
    script += [
        '*) echo "dpkg-query: no packages found matching $p" >&2; exit 1;;',
        "esac; done",
    ]
    (tmp_path / "dpkg-query").write_text("\n".join(script) + "\n")
    (tmp_path / "dpkg-query").chmod(0o755)


@pytest.mark.parametrize(
    ("statuses", "packages", "passes"),
    [
        ({"git": "ii ", "stow": "ii "}, ("git", "stow"), True),
        ({"git": "ii ", "stow": "un "}, ("git", "stow"), False),
        ({"git": "ii "}, ("git", "unknown-pkg"), False),
    ],
)
def test_dpkg_check_requires_every_package_installed(
    tmp_path, statuses, packages, passes
):
    _fake_dpkg_query(tmp_path, statuses)
    with patch.dict(os.environ, {"PATH": f"{tmp_path}:{os.environ['PATH']}"}):
        ok, _ = run_check(dpkg_check(*packages))
    assert ok is passes


def test_run_shell_fails_on_upstream_pipe_failure():
    with pytest.raises(subprocess.CalledProcessError):
        run_shell("false | cat")
    run_shell("true | cat")


def test_write_system_file(tmp_path):
    target = tmp_path / "testfile.conf"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        write_system_file(target, "content\n")
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "sudo" in cmd
    assert "install" in cmd
