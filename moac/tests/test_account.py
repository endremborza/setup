"""Which account a call runs on, and what a second login shares with the first."""

from pathlib import Path

import pytest
from moac._backend import Cli, Need, resolve
from moac._transport import cli_env

from moac import _account, _profiles

CONFIG = """
default_account = "work"

[account.work]

[account.personal]
config_dir = "{directory}"
"""


@pytest.fixture
def two_accounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config, directory = tmp_path / "moac.toml", tmp_path / "personal"
    config.write_text(CONFIG.format(directory=directory))
    monkeypatch.setattr(_profiles, "PATH", config)
    return directory


def test_no_config_is_one_implicit_account() -> None:
    assert _account.get().name == _account.IMPLICIT


def test_implicit_account_follows_an_inherited_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_account.CONFIG_DIR_VAR, "/inherited")
    assert cli_env(Cli(model="m"))[_account.CONFIG_DIR_VAR] == "/inherited"
    assert _account.get().credentials.parent == Path("/inherited")


def test_first_declared_account_is_the_default_when_none_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "moac.toml"
    config.write_text("[account.work]\n\n[account.personal]\n")
    monkeypatch.setattr(_profiles, "PATH", config)
    assert _account.get().name == "work"


def test_flag_beats_env_beats_default(
    two_accounts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _account.get().name == "work"
    monkeypatch.setenv(_account.ENV_VAR, "personal")
    assert _account.get().name == "personal"
    assert _account.get("work").name == "work"


def test_default_location_is_never_named_through_the_env_var(
    two_accounts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_account.CONFIG_DIR_VAR, "/inherited")
    env = cli_env(Cli(model="m", account="work"))
    assert _account.CONFIG_DIR_VAR not in env
    assert env[_account.ENV_VAR] == "work"


def test_second_account_gets_its_own_directory(two_accounts: Path) -> None:
    env = cli_env(Cli(model="m", account="personal"))
    assert env[_account.CONFIG_DIR_VAR] == str(two_accounts)
    assert _account.get("personal").credentials.parent == two_accounts


def test_unknown_account_is_refused_before_anything_runs(two_accounts: Path) -> None:
    with pytest.raises(SystemExit, match="unknown account"):
        resolve("x", Need(account="nobody"), profile="sonnet")


def test_account_is_refused_where_the_backend_has_none(
    two_accounts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit, match="account"):
        resolve("x", Need(account="personal"), profile="local")


def test_prepare_links_what_exists_and_keeps_the_rest_apart(
    two_accounts: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    (home / "CLAUDE.md").write_text("global")
    (home / "projects").mkdir()
    monkeypatch.setattr(_account, "_HOME_DIR", home)
    personal = _account.get("personal")
    _account.prepare(personal)
    _account.prepare(personal)
    assert (two_accounts / "CLAUDE.md").read_text() == "global"
    assert (two_accounts / "skills").is_symlink()
    assert not (two_accounts / "AGENTS.md").exists()
    assert not (two_accounts / "projects").exists()
