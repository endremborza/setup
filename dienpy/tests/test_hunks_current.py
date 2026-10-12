"""current run: patch ids outlive commits of other patches; commits of several patches follow each other."""

from pathlib import Path

import pytest
from _repo import git, make, seed
from dienpy.hunks import use
from dienpy.hunks.patch import commit


def test_ids_outlive_a_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    seed(repo)
    commit.main("1")
    capsys.readouterr()
    use.main()
    lines = capsys.readouterr().out.splitlines()
    assert [ln.split()[0] for ln in lines[1:]] == ["2", "3"]
    commit.main("3")
    assert git(repo, "log", "-1", "--format=%s") == "b edit"
    with pytest.raises(SystemExit, match="no patch '1'"):
        commit.main("1")


def test_commit_several(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    seed(repo)
    commit.main("1", "2", "3")
    assert git(repo, "log", "--format=%s", "-3").split("\n") == [
        "b edit",
        "a second",
        "a first",
    ]
    with pytest.raises(SystemExit, match="single patch"):
        commit.main("1", "2", message="x")
