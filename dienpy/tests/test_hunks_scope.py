"""scope: `under` selects a subtree; a partial analysis records only the coverage it has."""

from pathlib import Path

from dienpy.hunks import _cache
from dienpy.hunks._config import Config
from dienpy.hunks._hunks import Hunk, under

HEAD = "deadbeef"
CONFIG = Config("normal", "sonnet", "bare")


def _h(hid: str, path: str) -> Hunk:
    return Hunk(hid, path, "hunk", "", 10, 6)


def test_under_matches_subtree_not_name_prefix() -> None:
    hunks = [
        _h("a", "data/stock/cril/report.md"),
        _h("b", "data/stock/crilx/notes.md"),
        _h("c", "data/stock/cril"),
        _h("d", "logseq-notes/pages/x.md"),
    ]
    assert [h.id for h in under(hunks, "data/stock/cril")] == ["a", "c"]
    assert [h.id for h in under(hunks, "data/stock/cril/")] == ["a", "c"]
    assert under(hunks, "") == hunks


def test_entry_records_grouped_ids_and_full_anchors(tmp_path: Path) -> None:
    """A scoped run writes anchors for the whole diff, ids for the grouped subset only."""
    (tmp_path / ".git").mkdir()
    root = str(tmp_path)
    all_hunks = [_h("a", "data/stock/cril/report.md"), _h("b", "logseq-notes/x.md")]
    groups = [{"title": "cril notes", "message": "", "hunks": ["a"]}]

    _cache.set_entry(root, CONFIG, all_hunks, groups, HEAD)
    entry = _cache.entry(root, CONFIG)

    assert entry is not None
    assert entry["ids"] == ["a"]
    assert set(entry["anchors"]) == {"a", "b"}


def test_partial_entry_survives_prune(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    root = str(tmp_path)
    all_hunks = [_h("a", "data/stock/cril/report.md"), _h("b", "logseq-notes/x.md")]
    _cache.set_entry(
        root, CONFIG, all_hunks, [{"title": "t", "message": "", "hunks": ["a"]}], HEAD
    )

    _cache.prune(root, all_hunks, HEAD)

    data = _cache.load(root)
    assert data is not None
    assert list(data["analyses"]) == [CONFIG.key]


if __name__ == "__main__":
    import tempfile

    test_under_matches_subtree_not_name_prefix()
    for fn in (
        test_entry_records_grouped_ids_and_full_anchors,
        test_partial_entry_survives_prune,
    ):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    print("SCOPE PASS")
