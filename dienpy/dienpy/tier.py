"""Fleet identity helpers.

Hub = the one machine that runs primary-only operations (rclone offsite sync,
git-bare backups) and holds logos. `PRIMARY_HOSTNAME` is committed in `.vars`;
`MACHINE_TIER` is declared per-host in `.local-vars`.
"""

from __future__ import annotations

import os
import socket

HUB = "hub"
MEMBER = "member"
GUEST = "guest"

_VALID_TIERS = frozenset({HUB, MEMBER, GUEST})


def primary_hostname() -> str | None:
    return os.environ.get("PRIMARY_HOSTNAME") or None


def machine_tier() -> str:
    """Tier as declared in env; defaults to `guest` (least-privileged)."""
    tier = os.environ.get("MACHINE_TIER", GUEST)
    return tier if tier in _VALID_TIERS else GUEST


def is_hub() -> bool:
    """True iff this is the designated primary host AND it claims tier=hub."""
    pri = primary_hostname()
    return pri is not None and socket.gethostname() == pri and machine_tier() == HUB


def require_hub(action: str) -> bool:
    """Caller-friendly guard. On hub, returns True (proceed).
    On non-hub, prints a one-line reason and returns False so the caller can
    `return` cleanly — the same cron entry can run on every host and just no-op
    off the hub."""
    if is_hub():
        return True
    pri = primary_hostname() or "<unset>"
    host = socket.gethostname()
    tier = machine_tier()
    print(f"Skipping {action}: hub-only (host={host}, tier={tier}, primary={pri})")
    return False
