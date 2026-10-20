"""feed playbook: the file parses past its shebang, and its repo is the one whose `.cril` holds it, however the path is spelled."""

from pathlib import Path

import pytest

from dienpy.feed.playbook import load, repo_root


def _night(tmp_path: Path) -> tuple[Path, Path]:
    """A repo whose `.cril` links into a PKM; (repo root, its playbook reached through the link)."""
    pkm = tmp_path / "pkm" / "repo"
    (pkm / "playbooks").mkdir(parents=True)
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / ".cril").symlink_to(pkm)
    path = root / ".cril" / "playbooks" / "night.md"
    path.write_text(
        "#!/usr/bin/env -S dienpy feed playbook\n---\njobs: scan, pitch, pitch\nuntil: weekly-reset\n---\nWhy.\n"
    )
    return root, path


def test_load_skips_the_shebang_and_finds_its_repo(tmp_path: Path) -> None:
    root, path = _night(tmp_path)
    book = load(path)
    assert book.jobs == ("scan", "pitch", "pitch")
    assert book.until == "weekly-reset"
    assert book.body == "Why.\n"
    assert repo_root(book.path) == root


def test_relative_paths_keep_the_link_the_shell_went_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path = _night(tmp_path)
    for cwd, rel in (
        (path.parent, "night.md"),
        (root / "src", "../.cril/playbooks/night.md"),
    ):
        monkeypatch.chdir(cwd)
        monkeypatch.setenv("PWD", str(cwd))
        assert repo_root(load(Path(rel)).path) == root
