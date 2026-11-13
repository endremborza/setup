from pathlib import Path

import pytest

from dienpy._git import Repo
from _repo import _IDENT, git, make


def test_commits_text_leaving_worktree_and_other_entries(tmp_path: Path) -> None:
    repo = make(tmp_path)
    git(repo, "add", "b.txt")
    worktree = (repo / "a.txt").read_text()

    assert Repo(repo, cfg=_IDENT).commit_text("a.txt", "only this\n", "replace a")

    assert git(repo, "show", "HEAD:a.txt") == "only this"
    assert git(repo, "log", "-1", "--format=%s") == "replace a"
    assert (repo / "a.txt").read_text() == worktree
    assert git(repo, "diff", "--cached", "--name-only") == "b.txt"


def test_unchanged_text_makes_no_commit(tmp_path: Path) -> None:
    repo = make(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    text = Repo(repo).raw("show", "HEAD:a.txt")

    assert not Repo(repo, cfg=_IDENT).commit_text("a.txt", text, "noop")
    assert git(repo, "rev-parse", "HEAD") == head


def test_refuses_a_staged_path(tmp_path: Path) -> None:
    repo = make(tmp_path)
    git(repo, "add", "a.txt")

    with pytest.raises(SystemExit):
        Repo(repo, cfg=_IDENT).commit_text("a.txt", "x\n", "replace a")
