"""Primary-machine gating.

The primary (`PRIMARY_HOSTNAME`, committed in `.vars`) is the canonical
holder of the working set — the only machine allowed to mutate backup
targets. Layer-2 backups are rclone *sync* (extras on the target get
deleted), so running them from any other machine would push its stale view
over the mirrors. Distinct from the wireguard hub (netcup, fleet.toml):
that hub routes packets; the primary owns data.
"""

from __future__ import annotations

import os
import socket


def primary_hostname() -> str | None:
    return os.environ.get("PRIMARY_HOSTNAME") or None


def is_primary() -> bool:
    pri = primary_hostname()
    return pri is not None and socket.gethostname() == pri


def require_primary(action: str) -> bool:
    """Caller-friendly guard. On the primary, returns True (proceed).
    Elsewhere, prints a one-line reason and returns False so the caller can
    `return` cleanly."""
    if is_primary():
        return True
    print(
        f"Skipping {action}: primary-only "
        f"(host={socket.gethostname()}, primary={primary_hostname() or '<unset>'})"
    )
    return False
