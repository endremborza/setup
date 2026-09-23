"""branch: new commits picked patches, land squashes with archive and note, split, drop, worktree, conflict undo, checkout."""

import json
from pathlib import Path

import pytest
from _repo import git, ids, make, write
from _repo import seed as _seed
from dienpy.hunks import _engine, _hunks
from dienpy.hunks.branch import checkout, drop, land, new, show


def _log(repo: Path, rng: str) -> list[str]:
    out = git(repo, "log", "--format=%s", rng)
    return out.split("\n") if out else []


def test_new_then_land(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("feat", "p1", "p2")
    assert git(repo, "branch", "--show-current") == "feat"
    assert _log(repo, "main..feat") == ["a second", "a first"]
    assert git(repo, "log", "-1", "--format=%b", "feat~1") == "body one"
    assert ids(_hunks.parse(str(repo)), "a.txt") == []  # committed
    assert ids(_hunks.parse(str(repo)), "b.txt")  # leftover stays dirty
    tip = git(repo, "rev-parse", "feat")

    land.main(message="land feat")
    assert git(repo, "branch", "--show-current") == "main"
    assert _log(repo, "main") == ["land feat", "init"]
    assert git(repo, "rev-parse", "HEAD^{tree}") == git(
        repo, "rev-parse", f"{tip}^{{tree}}"
    )
    assert git(repo, "rev-parse", "refs/landed/feat") == tip
    assert "branch: feat" in git(repo, "notes", "--ref=landed", "show", "HEAD")
    assert "feat" not in git(repo, "branch", "--list", "feat")
    assert ids(_hunks.parse(str(repo)), "b.txt")  # leftovers popped
    assert (repo / "new.txt").exists()
    assert "landed feat onto main" in capsys.readouterr().out


def test_land_split(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("feat", "p1", "p2")
    git(repo, "stash", "-u", "-q")  # a clean tree, so the split sees only the branch

    def fake_partition(root, hunks, config, backend):
        a1, a2 = ids(hunks, "a.txt")
        return [
            {"title": "split one", "message": "", "hunks": [a1]},
            {"title": "split two", "message": "", "hunks": [a2]},
        ]

    monkeypatch.setattr(_engine, "partition", fake_partition)
    monkeypatch.setattr(_engine, "backend_for", lambda config, auth: None)
    land.main(split="granular", message="unused when split")
    assert _log(repo, "main") == ["split two", "split one", "init"]
    assert git(repo, "rev-parse", "refs/landed/feat")
    assert git(repo, "notes", "--ref=landed", "show", "HEAD~1")


def test_conflict_is_undone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("feat", "p1")
    git(repo, "stash", "-u", "-q")
    git(repo, "switch", "-q", "main")
    a = (repo / "a.txt").read_text().splitlines()
    a[4] = "CONFLICT"
    write(repo, "a.txt", a)
    git(repo, "commit", "-qam", "main moved")
    git(repo, "switch", "-q", "feat")
    git(repo, "stash", "pop", "-q")
    with pytest.raises(SystemExit, match="conflicts"):
        land.main(message="x")
    assert git(repo, "branch", "--show-current") == "feat"
    assert git(repo, "status", "--porcelain") and not git(repo, "stash", "list")
    assert _log(repo, "main") == ["main moved", "init"]


def test_drop_archives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("junk", "p3")
    tip = git(repo, "rev-parse", "junk")
    git(repo, "stash", "-u", "-q")
    drop.main("junk")
    assert git(repo, "branch", "--show-current") == "main"
    assert git(repo, "rev-parse", "refs/dropped/junk") == tip
    assert not git(repo, "branch", "--list", "junk")


def test_worktree_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("side", "p1", "p3", worktree=True)
    wt = tmp_path / "repo-side"
    assert wt.is_dir() and git(repo, "branch", "--show-current") == "main"
    assert _log(repo, "main..side") == ["b edit", "a first"]
    left = _hunks.parse(str(repo))
    assert len(ids(left, "a.txt")) == 1 and not ids(left, "b.txt")
    assert not git(repo, "status", "--porcelain", "--", "b.txt")
    capsys.readouterr()
    show.main(json=True)
    (row,) = json.loads(capsys.readouterr().out)
    assert row["name"] == "side" and row["worktree"] == str(wt)
    write(wt, "stray.txt", ["not committed"])
    with pytest.raises(SystemExit, match="uncommitted"):
        land.main("side", message="land side")
    assert wt.exists() and git(repo, "branch", "--list", "side")
    (wt / "stray.txt").unlink()
    land.main("side", message="land side")
    assert not wt.exists()
    assert _log(repo, "main") == ["land side", "init"]
    assert "THIRTYFIVE" not in git(repo, "show", "HEAD:a.txt")
    assert len(ids(_hunks.parse(str(repo)), "a.txt")) == 1  # the unpicked hunk survived


def test_show_json_is_pure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    by_title = _seed(repo)
    new.main("feat", by_title["a first"])
    git(repo, "branch", "aside")  # sorts first and is not checked out
    capsys.readouterr()
    show.main(json=True)
    rows = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in rows] == ["aside", "feat"]
    assert not rows[0]["current"] and rows[0]["commits"] == 1
    assert rows[1]["current"] and rows[1]["commits"] == 1 and not rows[1]["worktree"]


def test_checkout_and_refusals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("side", "p3", worktree=True)
    with pytest.raises(SystemExit, match="checked out in"):
        checkout.main("side")
    with pytest.raises(SystemExit, match="default branch"):
        drop.main("main")
    git(repo, "branch", "empty")
    with pytest.raises(SystemExit, match="no commits beyond"):
        land.main("empty")
    with pytest.raises(SystemExit, match="no branch"):
        checkout.main("nope")
    drop.main("side")
    assert not (tmp_path / "repo-side").exists()
    checkout.main("empty")
    assert git(repo, "branch", "--show-current") == "empty"
    assert ids(_hunks.parse(str(repo)), "a.txt")  # dirty files carried along


def test_reused_branch_name_archives_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    _seed(repo)
    new.main("feat", "p1")
    land.main(message="one")
    new.main("feat", "p2")
    land.main(message="two")
    refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/landed").split()
    assert refs == ["refs/landed/feat", "refs/landed/feat-2"]
    assert _log(repo, "main") == ["two", "one", "init"]
