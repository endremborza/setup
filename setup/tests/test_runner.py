from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from setup.runner import REGISTRY, Step, run, verify


@pytest.fixture(autouse=True)
def isolated_registry():
    original = REGISTRY.copy()
    REGISTRY.clear()
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


def make_step(
    name: str, profile: str, check: str | None = None
) -> tuple[MagicMock, Step]:
    fn = MagicMock()
    s = Step(fn=fn, name=name, profile=profile, check=check)
    REGISTRY.append(s)
    return fn, s


def test_run_includes_base_implicitly():
    fn_base, _ = make_step("apt", profile="base")
    fn_shell, _ = make_step("tmux", profile="shell")
    fn_dev, _ = make_step("node", profile="dev")

    run(profiles=["shell"])

    fn_base.assert_called_once()
    fn_shell.assert_called_once()
    fn_dev.assert_not_called()


def test_run_multiple_profiles():
    fn_base, _ = make_step("apt", profile="base")
    fn_shell, _ = make_step("tmux", profile="shell")
    fn_dev, _ = make_step("node", profile="dev")

    run(profiles=["shell", "dev"])

    fn_base.assert_called_once()
    fn_shell.assert_called_once()
    fn_dev.assert_called_once()


def test_run_no_profiles_only_base():
    fn_base, _ = make_step("apt", profile="base")
    fn_shell, _ = make_step("tmux", profile="shell")

    run(profiles=None)

    fn_base.assert_called_once()
    fn_shell.assert_not_called()


def test_run_single_step_by_name():
    fn0, _ = make_step("base-step", profile="base")
    fn1, _ = make_step("dev-step", profile="dev")

    run(profiles=None, step_name="dev-step")

    fn0.assert_not_called()
    fn1.assert_called_once()


def test_run_unknown_step_exits():
    with pytest.raises(SystemExit):
        run(profiles=None, step_name="nonexistent")


def test_run_skips_when_check_passes():
    fn, _ = make_step("checked", profile="base", check="true")

    with patch("setup.runner.check_passes", return_value=True):
        run(profiles=None)

    fn.assert_not_called()


def test_run_executes_when_check_fails():
    fn, _ = make_step("checked", profile="base", check="false")

    with patch("setup.runner.check_passes", return_value=False):
        run(profiles=None)

    fn.assert_called_once()


def test_run_force_ignores_check():
    fn, _ = make_step("checked", profile="base", check="true")

    with patch("setup.runner.check_passes", return_value=True):
        run(profiles=None, force=True)

    fn.assert_called_once()


def test_run_dry_run_skips_execution():
    fn, _ = make_step("base-step", profile="base")

    run(profiles=None, dry_run=True)

    fn.assert_not_called()


def test_run_continues_after_failure(capsys):
    fn_fail = MagicMock(side_effect=RuntimeError("boom"))
    fn_ok = MagicMock()
    REGISTRY.append(Step(fn=fn_fail, name="fail", profile="base"))
    REGISTRY.append(Step(fn=fn_ok, name="ok", profile="base"))

    run(profiles=None)

    fn_ok.assert_called_once()
    assert "[FAIL]" in capsys.readouterr().out


def test_verify_returns_true_when_all_pass():
    REGISTRY.append(Step(fn=MagicMock(), name="a", profile="base", verify="true"))
    REGISTRY.append(Step(fn=MagicMock(), name="b", profile="base", verify="true"))

    assert verify(profiles=None) is True


def test_verify_returns_false_on_failure():
    REGISTRY.append(Step(fn=MagicMock(), name="a", profile="base", verify="false"))

    assert verify(profiles=None) is False


def test_verify_skips_steps_without_verify():
    REGISTRY.append(Step(fn=MagicMock(), name="no-verify", profile="base"))

    with patch("setup.runner.run_check") as mock_check:
        verify(profiles=None)
    mock_check.assert_not_called()


def test_verify_respects_profile_set():
    REGISTRY.append(
        Step(fn=MagicMock(), name="base-vfy", profile="base", verify="true")
    )
    REGISTRY.append(
        Step(fn=MagicMock(), name="server-vfy", profile="server", verify="true")
    )

    with patch("setup.runner.run_check", return_value=(True, "")) as mock_check:
        verify(profiles=["shell"])

    # base is implicit, shell has no steps registered, server is excluded
    assert mock_check.call_count == 1
