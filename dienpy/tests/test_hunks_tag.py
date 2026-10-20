"""tag: only commits after the last tag reach the model; the suggestion is a pasteable branb command."""

import shlex
from pathlib import Path

import pytest
from _repo import git
from dienpy.hunks import tag


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-qm", f"add {name}")


def test_suggests_command_for_commits_since_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    _commit(repo, "released.txt")
    git(repo, "tag", "-a", "v1.2.3", "-m", "old")
    _commit(repo, "fresh.txt")

    notes = "- adds fresh.txt\n- it's quoted"
    prompts: list[str] = []
    monkeypatch.chdir(repo)
    monkeypatch.setattr(tag.ai, "resolve", lambda *a, **k: None)
    monkeypatch.setattr(
        tag.ai,
        "send",
        lambda backend, system, user, **k: (
            prompts.append(user)
            or {"bump": "minor", "reason": "new file", "notes": notes}
        ),
    )
    tag.main()

    assert "add fresh.txt" in prompts[0] and "add released.txt" not in prompts[0]
    out = capsys.readouterr().out
    assert "minor v1.2.3 → v1.3.0: new file" in out
    assert shlex.split(out[out.index("branb tag ") :]) == [
        "branb",
        "tag",
        notes,
        "minor",
    ]
