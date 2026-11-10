"""List the accounts: signed-in email, plan, login expiry, config directory, the default marked."""

import json
import subprocess
from typing import Any

from dienraw.out import table

from . import _account
from ._transport import account_env

_HEAD = ("account", "email", "plan", "login expires", "directory")


def _status(name: str) -> dict[str, Any]:
    done = subprocess.run(
        ["claude", "auth", "status"],
        env=account_env(name),
        capture_output=True,
        text=True,
    )
    return json.loads(done.stdout or "{}")


def main() -> None:
    default = _account.default_name()
    rows = []
    for name in _account.names():
        status = _status(name)
        rows.append(
            (
                f"{name} (default)" if name == default else name,
                status.get("email", "not signed in"),
                status.get("planTier") or status.get("subscriptionType", ""),
                str(status.get("loginExpiresAt") or "")[:10],
                _account.get(name).directory,
            )
        )
    print(table(rows, _HEAD))
