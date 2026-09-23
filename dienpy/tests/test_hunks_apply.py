"""apply: stage/unstage/discard/commit by hunk id across file kinds, the foreign-index guard, staged renames, clashing views."""

from pathlib import Path

import pytest
from _repo import git, ids, make, views, write
from dienpy.hunks import _apply, _hunks


def _staged(repo: Path) -> set[str]:
    return {h.id for h in _hunks.parse(str(repo), staged=True)}


def test_stage_unstage_by_id(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    a1, a2 = ids(_hunks.parse(root), "a.txt")
    new = ids(_hunks.parse(root), "new.txt")[0]
    assert _apply.stage(root, [a1, new], *views(repo)) == 2
    assert _staged(repo) == {a1, new}
    assert _apply.stage(root, [a1], *views(repo)) == 0  # already held
    assert _apply.unstage(root, [a1, new], *views(repo)) == 2
    assert _staged(repo) == set()
    assert a2 in {h.id for h in _hunks.parse(root)}


def test_discard_each_kind(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    hunks = _hunks.parse(root)
    a1, a2 = ids(hunks, "a.txt")
    dele = ids(hunks, "del.txt")[0]
    new = ids(hunks, "new.txt")[0]
    _apply.stage(root, [a2], *views(repo))  # staged hunks are discarded too
    _apply.discard(root, [a2, dele, new], *views(repo))
    left = _hunks.parse(root)
    assert ids(left, "a.txt") == [a1]
    assert not (repo / "new.txt").exists() and (repo / "del.txt").exists()
    assert _staged(repo) == set()


def test_commit_only_the_patch(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    a1, a2 = ids(_hunks.parse(root), "a.txt")
    short = _apply.commit(root, [a1], "first hunk\n", *views(repo))
    assert git(repo, "log", "-1", "--format=%s") == "first hunk"
    assert git(repo, "rev-parse", "--short", "HEAD") == short
    assert ids(_hunks.parse(root), "a.txt") == [a2]
    assert "FIVE" in git(repo, "show", "HEAD:a.txt")


def test_commit_refuses_foreign_index(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    a1, a2 = ids(_hunks.parse(root), "a.txt")
    _apply.stage(root, [a2], *views(repo))
    with pytest.raises(SystemExit, match="outside the patch"):
        _apply.commit(root, [a1], "x\n", *views(repo))
    assert _staged(repo) == {a2}  # the refusal changed nothing


def test_identical_hunks_move_as_a_family(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    block = list("abcdefg")
    write(repo, "dup.txt", block * 3)
    git(repo, "add", "dup.txt")
    git(repo, "commit", "-qm", "dup")
    lines = block * 3
    lines[3], lines[17] = "D", "D"
    write(repo, "dup.txt", lines)
    first, second = ids(_hunks.parse(root), "dup.txt")
    assert second == first + "~2"
    with pytest.raises(SystemExit, match="identical"):
        _apply.stage(root, [second], *views(repo))
    assert _staged(repo) == set()
    assert _apply.stage(root, [first, second], *views(repo)) == 2
    assert ids(_hunks.parse(root, staged=True), "dup.txt") == [first, second]


def test_staged_rename_is_rebased_and_skipped(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    git(repo, "stash", "-u", "-q")
    git(repo, "mv", "b.txt", "c.txt")
    lines = (repo / "c.txt").read_text().splitlines()
    lines[0], lines[9] = "C1", "C10"
    write(repo, "c.txt", lines)
    hunks = _hunks.parse(root)
    assert [h.path for h in hunks] == ["c.txt", "c.txt"]
    first, second = ids(hunks, "c.txt")
    index = _hunks.parse(root, staged=True)
    assert _apply.staged_renames(index) == {"c.txt"}
    _apply.commit(root, [first], "rename plus first edit\n", *views(repo))
    assert "C1" in git(repo, "show", "HEAD:c.txt")
    assert not git(repo, "ls-tree", "HEAD", "b.txt")
    assert ids(_hunks.parse(root), "c.txt") == [second]


def test_discard_pure_staged_rename(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    git(repo, "stash", "-u", "-q")
    git(repo, "mv", "b.txt", "c.txt")
    (rename,) = _hunks.parse(root, staged=True)
    assert _apply.rename_source(rename) == "b.txt"
    _apply.discard(root, [rename.id], *views(repo))
    assert not git(repo, "status", "--porcelain", "--untracked-files=all")
    assert (repo / "b.txt").exists() and not (repo / "c.txt").exists()


def test_unstaged_edit_next_to_staged_hunk(tmp_path: Path) -> None:
    """The worktree view merges both into one hunk the index does not hold: staging,
    unstaging and discarding that hunk address the staged part through it."""
    repo = make(tmp_path)
    root = str(repo)
    git(repo, "stash", "-u", "-q")
    a = (repo / "a.txt").read_text().splitlines()
    a[4] = "FIVE"
    write(repo, "a.txt", a)
    git(repo, "add", "a.txt")
    a[6] = "SEVEN"
    write(repo, "a.txt", a)
    (merged,) = _hunks.parse(root)
    (staged,) = _hunks.parse(root, staged=True)
    assert merged.id != staged.id
    assert _apply.unstage(root, [merged.id], *views(repo)) == 1
    assert _staged(repo) == set()
    assert _apply.stage(root, [merged.id], *views(repo)) == 1
    assert _staged(repo) == {merged.id}
    git(repo, "restore", "--staged", "a.txt")
    git(repo, "apply", "--cached", "-", stdin=staged.header + "\n" + staged.text + "\n")
    assert _staged(repo) == {staged.id}
    _apply.stage(root, [merged.id], *views(repo))
    assert _staged(repo) == {merged.id}
    _apply.discard(root, [merged.id], *views(repo))
    assert not git(repo, "status", "--porcelain")


def test_staged_new_file_then_edited(tmp_path: Path) -> None:
    repo = make(tmp_path)
    root = str(repo)
    git(repo, "add", "new.txt")
    write(repo, "new.txt", ["brand new", "contents", "more"])
    (live,) = ids(_hunks.parse(root), "new.txt")
    assert _apply.stage(root, [live], *views(repo)) == 1
    assert ids(_hunks.parse(root, staged=True), "new.txt") == [live]
