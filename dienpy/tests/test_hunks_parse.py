"""parse: kinds, duplicate-hunk ids, index and worktree views agree on content, range diffs."""

from pathlib import Path

from _repo import git, ids, make, write

from dienpy.hunks import _hunks


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


def test_rev_parses_a_range(tmp_path: Path) -> None:
    repo = make(tmp_path)
    git(repo, "stash", "-u", "-q")
    git(repo, "switch", "-q", "-c", "feat")
    write(repo, "c.txt", ["c"])
    git(repo, "add", "c.txt")
    git(repo, "commit", "-qm", "feat")
    hunks = _hunks.parse(str(repo), rev="main...feat")
    assert [h.path for h in hunks] == ["c.txt"]
