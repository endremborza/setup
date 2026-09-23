"""current run: `use` and `patch <position>` share one sanitized listing; commits of several patches follow each other."""

from pathlib import Path

import pytest
from _repo import git, make, seed
from dienpy.hunks import use
from dienpy.hunks.patch import commit


def test_positions_follow_the_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    seed(repo)
    commit.main("p1")
    capsys.readouterr()
    use.main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith(" 1 p2") and lines[2].startswith(" 2 p3")
    commit.main("2")
    assert git(repo, "log", "-1", "--format=%s") == "b edit"


def test_commit_several(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    seed(repo)
    commit.main("p1", "p2", "p3")
    assert git(repo, "log", "--format=%s", "-3").split("\n") == [
        "b edit",
        "a second",
        "a first",
    ]
    with pytest.raises(SystemExit, match="single patch"):
        commit.main("p1", "p2", message="x")
