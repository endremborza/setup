"""Hub profile — provisions the private git server for the fleet.

Hub is the one machine hosting the bare repos accessed by Members and Guests
over SSH. This profile ensures sshd is running, creates the bare repos at
$SHARE_DIR/git/, and wires Hub's hypothalamus working copy as a `fleet` remote
pointing at the bare. Future commits land in the bare via `git push fleet`.

Auth is SSH public keys in ~/.ssh/authorized_keys; managing those is a
one-time manual step per new fleet machine. Guest entries should be prefixed
with `command="git-shell -c \\"...\\""` to restrict them to ledger.git only.

This profile is only meaningful on the Hub. Declaring it in `SETUP_PROFILES`
is itself the assertion that this is the Hub — like declaring `screen` on a
headless box would be wrong, the user is responsible for getting it right.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from setup.runner import step
from setup.util import run_cmd

_SHARE_DIR = Path(os.environ.get("SHARE_DIR", str(Path.home() / "synced/share")))
_HYPO_ROOT = Path(
    os.environ.get("HYPO_ROOT", str(Path.home() / "synced/composites/pkm/hypothalamus"))
)
_GIT_DIR = _SHARE_DIR / "git"
_HYPOTHALAMUS_BARE = _GIT_DIR / "hypothalamus.git"
_LEDGER_BARE = _GIT_DIR / "ledger.git"
_FLEET_REMOTE = "fleet"


def _bare_verify(path: Path) -> str:
    """Shell command: passes iff `path` exists and is a bare git repo."""
    return (
        f"test -d {path} && "
        f"git -C {path} rev-parse --is-bare-repository 2>/dev/null | grep -q true"
    )


def _ensure_remote(repo: Path, name: str, url: Path) -> None:
    r = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", name],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", name, str(url)], check=True
        )
    elif r.stdout.strip() != str(url):
        subprocess.run(
            ["git", "-C", str(repo), "remote", "set-url", name, str(url)], check=True
        )


def _init_bare(bare: Path) -> None:
    if not bare.exists():
        run_cmd(f"git init --bare {bare}")


_SSHD_RUNNING = "systemctl is-active --quiet ssh && systemctl is-enabled --quiet ssh"


@step(profile="hub", name="sshd", check=_SSHD_RUNNING, verify=_SSHD_RUNNING)
def enable_sshd() -> None:
    run_cmd("sudo systemctl enable --now ssh")


@step(
    profile="hub",
    name="git-server-dir",
    check=f"test -d {_GIT_DIR}",
    verify=f"test -d {_GIT_DIR}",
)
def create_git_dir() -> None:
    _GIT_DIR.mkdir(parents=True, exist_ok=True)


@step(
    profile="hub",
    name="bare-hypothalamus",
    check=f"test -d {_HYPOTHALAMUS_BARE}",
    verify=_bare_verify(_HYPOTHALAMUS_BARE),
)
def init_bare_hypothalamus() -> None:
    _init_bare(_HYPOTHALAMUS_BARE)
    if (_HYPO_ROOT / ".git").exists():
        _ensure_remote(_HYPO_ROOT, _FLEET_REMOTE, _HYPOTHALAMUS_BARE)
        # Initial sync — best-effort. Subsequent pushes are the user's responsibility.
        for refspec in ("--all", "--tags"):
            subprocess.run(
                ["git", "-C", str(_HYPO_ROOT), "push", _FLEET_REMOTE, refspec],
                capture_output=True,
            )


@step(
    profile="hub",
    name="bare-ledger",
    check=f"test -d {_LEDGER_BARE}",
    verify=_bare_verify(_LEDGER_BARE),
)
def init_bare_ledger() -> None:
    _init_bare(_LEDGER_BARE)
