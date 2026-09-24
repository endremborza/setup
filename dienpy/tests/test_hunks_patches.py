"""patches: sanitize prunes dead ids and merges same titles keeping the first id; selection by id, position and hunk id."""

import pytest
from dienpy.hunks._patches import hunk_ids, mint, sanitize, select


def test_sanitize_prunes_and_merges() -> None:
    patches = [
        {
            "id": "p1",
            "title": "a",
            "message": "first",
            "hunks": ["x", "dead"],
            "mixed": [{"hunk": "x", "note": "n1"}, {"hunk": "dead", "note": "n2"}],
        },
        {"id": "p2", "title": "b", "message": "", "hunks": ["dead2"]},
        {"id": "p3", "title": "a", "message": "dup", "hunks": ["z"]},
    ]
    out = sanitize(patches, {"x", "z"})
    assert out == [
        {
            "id": "p1",
            "title": "a",
            "message": "first",
            "hunks": ["x", "z"],
            "mixed": [{"hunk": "x", "note": "n1"}],
        }
    ]
    assert patches[0]["hunks"] == ["x", "dead"]  # input untouched


def test_mint_and_select() -> None:
    patches = mint(
        [{"title": "a", "hunks": ["b" * 12]}, {"title": "b", "hunks": ["1" * 12]}]
    )
    assert all(len(p["id"]) == 6 for p in patches)
    assert select(patches, ("2", patches[0]["id"])) == [patches[1], patches[0]]
    with pytest.raises(SystemExit, match="no patch"):
        select(patches, ("nope",))
    digits = [{"id": "p1", "hunks": []}, {"id": "000001", "hunks": []}]
    assert select(digits, ("000001", "1")) == [digits[1], digits[0]]
    live = {"b" * 12, "1" * 12}
    assert hunk_ids(patches, ("1", "1" * 12, "b" * 12), live, live) == [
        "b" * 12,
        "1" * 12,
    ]
    with pytest.raises(SystemExit, match="not in the current diff"):
        hunk_ids(patches, ("a" * 12,), live, live)
    assert hunk_ids(patches, ("a" * 12,), live, live | {"a" * 12}) == ["a" * 12]
