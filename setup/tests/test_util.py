from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from setup.util import apt_install, cargo_install, check_binary, extended_env, write_system_file


def test_extended_env_prepends_cargo_and_local_bin():
    env = extended_env()
    parts = env["PATH"].split(":")
    assert str(Path.home() / ".cargo/bin") in parts[:3]
    assert str(Path.home() / ".local/bin") in parts[:3]


def test_extended_env_preserves_existing_path():
    with patch.dict(os.environ, {"PATH": "/original/bin"}):
        env = extended_env()
    assert "/original/bin" in env["PATH"]


def test_apt_install_calls_apt_get(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        apt_install(["git", "curl"])
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "apt-get" in cmd
    assert "install" in cmd
    assert "git" in cmd
    assert "curl" in cmd


def test_cargo_install_calls_cargo(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        cargo_install(["ripgrep", "bat"])
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "cargo" in cmd
    assert "install" in cmd
    assert "ripgrep" in cmd


def test_check_binary_found():
    with patch("shutil.which", return_value="/usr/bin/git"):
        assert check_binary("git") is True


def test_check_binary_not_found():
    with patch("shutil.which", return_value=None):
        assert check_binary("nonexistent-tool-xyz") is False


def test_write_system_file(tmp_path):
    target = tmp_path / "testfile.conf"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        write_system_file(target, "content\n")
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "sudo" in cmd
    assert "cp" in cmd
