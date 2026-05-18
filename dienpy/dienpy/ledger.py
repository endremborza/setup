"""Fleet ledger — update this machine's entry in the shared ledger repo.

The Hub hosts a private bare repo at $SHARE_DIR/git/ledger.git. Every fleet
machine (Hub, Members, Guests) clones it to $SYNC_ROOT/composites/pkm/ledger
and writes a one-file-per-host entry on each `dienpy ledger` invocation.

`cril housekeeping` reads the local ledger clone and surfaces a Fleet section
in its report.
"""

from __future__ import annotations

import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dienpy._toml import fmt_entry
from dienpy.cli import handle_help
from dienpy.constants import SYNC_ROOT

LEDGER_DIR = SYNC_ROOT / "composites" / "pkm" / "ledger"
_HUB_LEDGER_REL = "synced/share/git/ledger.git"


def _ledger_url() -> str:
    primary = os.environ.get("PRIMARY_HOSTNAME", "")
    if not primary:
        raise SystemExit("PRIMARY_HOSTNAME not set; cannot locate ledger.")
    if socket.gethostname() == primary:
        return str(SYNC_ROOT / "share/git/ledger.git")
    hub_user = os.environ.get("HUB_USER") or os.environ.get("USER", "")
    if not hub_user:
        raise SystemExit("HUB_USER or USER must be set.")
    return f"{hub_user}@{primary}:{_HUB_LEDGER_REL}"


def _git_head(repo: Path) -> str:
    if not (repo / ".git").exists():
        return "n/a"
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()[:12] if r.returncode == 0 else "n/a"


def _build_entry() -> str:
    dien_root = Path(
        os.environ.get("DIEN_ROOT", str(SYNC_ROOT / "composites/pkm/diencephalon"))
    )
    hypo_root = Path(
        os.environ.get("HYPO_ROOT", str(SYNC_ROOT / "composites/pkm/hypothalamus"))
    )
    return fmt_entry(
        {
            "hostname": socket.gethostname(),
            "tier": os.environ.get("MACHINE_TIER", "guest"),
            "profiles": os.environ.get("SETUP_PROFILES", "").split(),
            "diencephalon_head": _git_head(dien_root),
            "hypothalamus_head": _git_head(hypo_root),
            "kernel": subprocess.run(
                ["uname", "-r"], capture_output=True, text=True
            ).stdout.strip(),
            "last_checkin": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )


def main() -> None:
    """Update this machine's row in the fleet ledger."""
    if handle_help(
        "dienpy ledger",
        "Clone the fleet ledger if missing, write/refresh this host's entry, push.",
    ):
        return
    if not LEDGER_DIR.exists():
        LEDGER_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", _ledger_url(), str(LEDGER_DIR)], check=True)

    subprocess.run(["git", "-C", str(LEDGER_DIR), "pull", "--ff-only"], check=False)

    machines = LEDGER_DIR / "machines"
    machines.mkdir(exist_ok=True)
    host = socket.gethostname()
    entry_path = machines / f"{host}.toml"
    entry_path.write_text(_build_entry())

    subprocess.run(["git", "-C", str(LEDGER_DIR), "add", str(entry_path)], check=True)
    subprocess.run(
        ["git", "-C", str(LEDGER_DIR), "commit", "-m", f"checkin: {host}"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(LEDGER_DIR), "push", "-u", "origin", "HEAD"],
        check=False,
    )
    print(f"Checked in {host}")
