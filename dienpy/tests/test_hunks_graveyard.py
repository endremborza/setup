"""graveyard: bury lists an entry by hash, restore pops it back with its index state, drop removes it."""

import json
from pathlib import Path

import pytest
from _repo import git, ids, make, seed
from dienpy.hunks import _hunks
from dienpy.hunks.graveyard import drop, restore
from dienpy.hunks.graveyard import list as glist
from dienpy.hunks.patch import bury


def _entries(capsys) -> list[dict]:
    capsys.readouterr()
    glist.main(json=True)
    return json.loads(capsys.readouterr().out)


def test_bury_list_restore_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    root = str(repo)
    seed(repo)
    a1, a2 = ids(_hunks.parse(root), "a.txt")
    bury.main("p1")
    (row,) = _entries(capsys)
    assert row["title"] == "a first" and row["ref"] == "stash@{0}"
    assert ids(_hunks.parse(root), "a.txt") == [a2]
    restore.main(row["hash"][:7])
    assert ids(_hunks.parse(root, staged=True), "a.txt") == [a1]
    assert _entries(capsys) == []
    bury.main("p1")
    (row,) = _entries(capsys)
    drop.main(row["hash"])
    assert not git(repo, "stash", "list")
    with pytest.raises(SystemExit, match="no graveyard entry"):
        restore.main("deadbeef")
