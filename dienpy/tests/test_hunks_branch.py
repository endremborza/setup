"""branch: new commits picked patches, land squashes with archive and note, split, drop, worktree, conflict undo."""

from pathlib import Path

import pytest
from _repo import git, ids, make, write

from dienpy.hunks import _cache, _config, _engine, _hunks
from dienpy.hunks.branch import drop, land, new, show

CONFIG = _config.Config("normal", "sonnet", "bare")


def _seed(repo: Path) -> dict[str, str]:
    """Cache with one patch per hunk of a.txt and b.txt; returns title -> patch id."""
    root = str(repo)
    hunks = _hunks.parse(root)
    a1, a2 = ids(hunks, "a.txt")
    b1 = ids(hunks, "b.txt")[0]
    patches = [
        {"id": "p1", "title": "a first", "message": "body one", "hunks": [a1]},
        {"id": "p2", "title": "a second", "message": "", "hunks": [a2]},
        {"id": "p3", "title": "b edit", "message": "", "hunks": [b1]},
    ]
    _cache.set_entry(root, CONFIG, hunks, patches)
    _cache.touch_last(root, CONFIG)
    return {p["title"]: p["id"] for p in patches}


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


def test_worktree_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    rows = show._branches(str(repo), "main")
    assert rows[0]["name"] == "side" and rows[0]["worktree"] == str(wt)
    land.main("side", message="land side")
    assert not wt.exists()
    assert _log(repo, "main") == ["land side", "init"]
    assert "THIRTYFIVE" not in git(repo, "show", "HEAD:a.txt")
    assert len(ids(_hunks.parse(str(repo)), "a.txt")) == 1  # the unpicked hunk survived


def test_show_json_is_pure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import json

    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    by_title = _seed(repo)
    new.main("feat", by_title["a first"])
    capsys.readouterr()
    show.main(json=True)
    rows = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in rows] == ["feat"]
