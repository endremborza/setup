"""parse: kinds, duplicate-hunk ids, index and worktree views agree on content, range diffs, odd paths and bytes."""

import json
import subprocess
from pathlib import Path

from _repo import git, ids, make, views, write
from dienpy.hunks import _apply, _hunks


def test_kinds_and_positions(tmp_path: Path) -> None:
    repo = make(tmp_path)
    hunks = _hunks.parse(str(repo))
    by_path = {h.path: h for h in hunks}
    assert len(ids(hunks, "a.txt")) == 2
    assert [h.new_start for h in hunks if h.path == "a.txt"] == [2, 32]
    assert by_path["del.txt"].kind == "hunk" and by_path["del.txt"].new_start == 1
    assert by_path["new.txt"].kind == "untracked" and by_path[
        "new.txt"
    ].text.startswith("@@")
    assert (
        by_path["new_bin"].kind == "untracked" and "Binary" in by_path["new_bin"].text
    )
    assert all(len(h.id) == 12 for h in hunks)


def test_duplicate_hunks_get_suffix(tmp_path: Path) -> None:
    repo = make(tmp_path)
    pad = ["pad"] * 16
    pad[3] = pad[12] = "mid"
    write(repo, "dup.txt", pad)
    git(repo, "add", "dup.txt")
    git(repo, "commit", "-qm", "dup")
    pad[3] = pad[12] = "MID"
    write(repo, "dup.txt", pad)
    dup = ids(_hunks.parse(str(repo)), "dup.txt")
    assert len(dup) == 2 and dup[1] == dup[0] + "~2"


def test_index_view_shares_ids(tmp_path: Path) -> None:
    repo = make(tmp_path)
    live = {h.id for h in _hunks.parse(str(repo))}
    git(repo, "add", "b.txt", "new.txt")
    staged = {h.id for h in _hunks.parse(str(repo), staged=True)}
    assert staged and staged <= live


def test_whole_file_ids_agree_across_views(tmp_path: Path) -> None:
    """The last entry of the diff output is as stable as any other, and a binary's id
    follows its content."""
    repo = make(tmp_path)
    root = str(repo)
    (bin_id,) = ids(_hunks.parse(root), "new_bin")
    git(repo, "add", "new_bin")
    assert ids(_hunks.parse(root, staged=True), "new_bin") == [bin_id]
    assert ids(_hunks.parse(root), "new_bin") == [bin_id]
    (repo / "new_bin").write_bytes(b"\x00\x09")
    (edited,) = ids(_hunks.parse(root), "new_bin")
    assert edited != bin_id
    _apply.stage(root, [edited], *views(repo))
    assert ids(_hunks.parse(root, staged=True), "new_bin") == [edited]


def test_odd_paths_and_bytes_round_trip(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    git(repo, "stash", "-u", "-q")
    write(repo, "sp ace.txt", ["one"])
    (repo / "crlf.txt").write_bytes(b"x\r\ny\r\n")
    (repo / "latin1.txt").write_bytes(b"caf\xe9\n")
    live = _hunks.parse(root)
    assert {h.path for h in live} == {"sp ace.txt", "crlf.txt", "latin1.txt"}
    json.dumps([h.as_json() for h in live])  # display text is valid UTF-8
    _apply.stage(root, [h.id for h in live], live, [])
    assert {h.id for h in _hunks.parse(root, staged=True)} == {h.id for h in live}
    blob = subprocess.run(
        ["git", "-C", root, "cat-file", "-p", ":crlf.txt"], capture_output=True
    ).stdout
    assert blob == b"x\r\ny\r\n"
    _apply.discard(root, [h.id for h in live], *views(repo))
    assert not git(repo, "status", "--porcelain", "--untracked-files=all")


def test_unborn_head(tmp_path: Path) -> None:
    repo = tmp_path / "fresh"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo, "f.txt", ["hi"])
    assert [(h.path, h.kind) for h in _hunks.parse(str(repo))] == [
        ("f.txt", "untracked")
    ]
    assert _hunks.parse(str(repo), staged=True) == []


def test_rev_parses_a_range(tmp_path: Path) -> None:
    repo = make(tmp_path)
    git(repo, "stash", "-u", "-q")
    git(repo, "switch", "-q", "-c", "feat")
    write(repo, "c.txt", ["c"])
    git(repo, "add", "c.txt")
    git(repo, "commit", "-qm", "feat")
    hunks = _hunks.parse(str(repo), rev="main...feat")
    assert [h.path for h in hunks] == ["c.txt"]
