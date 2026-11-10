"""Accounts: one claude config directory each, so several logins stay signed in side by side."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from protocli import Complete

from . import _profiles

ENV_VAR = "MOAC_ACCOUNT"
CONFIG_DIR_VAR = "CLAUDE_CONFIG_DIR"
IMPLICIT = "default"
_HOME_DIR = Path.home() / ".claude"
_CREDENTIALS = ".credentials.json"
_SHARED = ("CLAUDE.md", "AGENTS.md", "settings.json", "skills", "plugins")


@dataclass(frozen=True)
class Account:
    name: str
    # None is the claude command's own location: naming that location through the env var
    # would move its global state file into the directory
    config_dir: Path | None = None

    @property
    def directory(self) -> Path:
        return self.config_dir or _HOME_DIR

    @property
    def credentials(self) -> Path:
        return self.directory / _CREDENTIALS

    def env(self, base: Mapping[str, str]) -> dict[str, str]:
        """`base` with this account selected, for claude and whatever it starts."""
        out = {**base, ENV_VAR: self.name}
        if self.config_dir:
            out[CONFIG_DIR_VAR] = str(self.config_dir)
        else:
            out.pop(CONFIG_DIR_VAR, None)
        return out


def _directory(spec: dict[str, Any]) -> Path | None:
    raw = spec.get("config_dir")
    return Path(raw).expanduser() if raw else None


def _implicit() -> Account:
    """With no account declared, claude's location is whatever the environment already says."""
    inherited = os.environ.get(CONFIG_DIR_VAR)
    return Account(IMPLICIT, Path(inherited) if inherited else None)


def accounts() -> dict[str, Account]:
    declared = _profiles.config().get("account", {})
    found = {name: Account(name, _directory(s)) for name, s in declared.items()}
    return found or {IMPLICIT: _implicit()}


def names() -> list[str]:
    return sorted(accounts())


AccountName = Annotated[str, Complete(names)]


def default_name() -> str:
    """`default_account`, else the first account declared."""
    return str(_profiles.config().get("default_account") or next(iter(accounts())))


def get(name: str = "") -> Account:
    """`name`, else `MOAC_ACCOUNT`, else the configured default; an unknown one is refused."""
    chosen = name or os.environ.get(ENV_VAR) or default_name()
    known = accounts()
    if chosen not in known:
        raise SystemExit(
            f"unknown account '{chosen}' (known: {', '.join(sorted(known))})"
        )
    return known[chosen]


def prepare(account: Account) -> None:
    """Create the account's directory and link what every account shares; the rest is its own."""
    if account.config_dir is None:
        return
    account.config_dir.mkdir(parents=True, exist_ok=True)
    for name in _SHARED:
        source, link = _HOME_DIR / name, account.config_dir / name
        if source.exists() and not link.exists() and not link.is_symlink():
            link.symlink_to(source)
