"""moac tmux: the windows prompt files open and the tmux calls that open them."""

import subprocess
from pathlib import Path

import pytest
from moac.tmux import MOAC, PREFIX, commands, session_name, sessions, window

from moac import _account, _profiles, tmux


def test_two_files_open_two_windows_in_their_own_directories(
    tmp_path: Path, monkeypatch
) -> None:
    briefs, work = tmp_path / "briefs", tmp_path / "work"
    briefs.mkdir()
    work.mkdir()
    monkeypatch.setenv("WORK", str(work))
    fix = briefs / "fix.md"
    fix.write_text("---\nname: bugfix\ncwd: $WORK\nprofile: opux\n---\nfix it\n")
    plain = briefs / "plain.md"
    plain.write_text("just a brief\n")
    monkeypatch.chdir(tmp_path)

    first, second = (
        window(f, account=_account.IMPLICIT, auto=True) for f in (fix, plain)
    )

    assert (first.name, first.cwd) == ("bugfix", work)
    assert first.argv == (
        *MOAC,
        *(
            "run",
            "opux",
            str(fix),
            "--interactive",
            "--account",
            _account.IMPLICIT,
            "--auto",
        ),
    )
    assert session_name([fix, plain]) == PREFIX + "briefs"
    new_session, new_window = commands("s", [first, second])
    assert new_session == [
        *("tmux", "new-session", "-d", "-s", "s", "-n", "bugfix", "-c", str(work)),
        *("--", *first.argv),
    ]
    assert new_window[:5] == ["tmux", "new-window", "-d", "-t", "=s:"]
    assert new_window[5:] == ["-n", "plain", "-c", str(tmp_path), "--", *second.argv]


def test_frontmatter_defaults_and_a_missing_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    brief = tmp_path / "brief.md"
    brief.write_text("no frontmatter\n")
    w = window(brief)
    assert (w.name, w.cwd) == ("brief", tmp_path)
    assert w.argv == (
        *MOAC,
        "run",
        _profiles.default_name(),
        str(brief),
        "--interactive",
    )
    assert session_name([brief], "my.session") == PREFIX + "my_session"
    assert session_name([brief], PREFIX + "again") == PREFIX + "again"
    brief.write_text("---\ncwd: ~/nowhere\n---\nbody\n")
    with pytest.raises(SystemExit, match="not a directory"):
        window(brief)


def test_sessions_lists_only_moac_ones_without_the_prefix(monkeypatch) -> None:
    listed = subprocess.CompletedProcess(
        [], 0, stdout=f"{PREFIX}review\nwork\n{PREFIX}other\n", stderr=""
    )
    monkeypatch.setattr(tmux.shutil, "which", lambda _: "/usr/bin/tmux")
    monkeypatch.setattr(tmux.subprocess, "run", lambda *a, **k: listed)
    assert sessions() == ["review", "other"]
    failed = subprocess.CompletedProcess([], 1, stdout="", stderr="no server")
    monkeypatch.setattr(tmux.subprocess, "run", lambda *a, **k: failed)
    assert sessions() == []
