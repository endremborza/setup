"""Sign an account in: create its config directory, link the shared files, run `claude auth login`."""

import subprocess
import sys

from . import _account
from ._account import AccountName
from ._transport import account_env


def main(account: AccountName) -> None:
    """Open the browser sign-in for ACCOUNT; its login is kept apart from every other account's."""
    _account.prepare(_account.get(account))
    sys.exit(
        subprocess.run(["claude", "auth", "login"], env=account_env(account)).returncode
    )
