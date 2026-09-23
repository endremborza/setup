"""A scratch git repository with the diff shapes the hunks tests need."""

from pathlib import Path

from dienpy._git import Repo

_IDENT = ("-c", "user.email=t@t", "-c", "user.name=t")


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    return Repo(repo, cfg=_IDENT).out(*args, stdin=stdin)


def write(repo: Path, rel: str, lines: list[str]) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text("".join(f"{ln}\n" for ln in lines))


def make(base: Path) -> Path:
    """HEAD: a.txt (40 numbered lines), b.txt, del.txt. Worktree: a.txt edited at lines 5 and
    35 (two hunks), b.txt edited, del.txt deleted, new.txt untracked, new_bin untracked binary."""
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    write(repo, "a.txt", [str(i) for i in range(1, 41)])
    write(repo, "b.txt", [f"b{i}" for i in range(1, 11)])
    write(repo, "del.txt", ["one", "two"])
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    dirty(repo)
    return repo


def dirty(repo: Path) -> None:
    a = (repo / "a.txt").read_text().splitlines()
    a[4], a[34] = "FIVE", "THIRTYFIVE"
    write(repo, "a.txt", a)
    b = (repo / "b.txt").read_text().splitlines()
    b[0] = "B1"
    write(repo, "b.txt", b)
    (repo / "del.txt").unlink()
    write(repo, "new.txt", ["brand new", "contents"])
    (repo / "new_bin").write_bytes(b"\x00\x01\x02")


def ids(hunks: list, path: str) -> list[str]:
    return [h.id for h in hunks if h.path == path]


def views(repo: Path) -> tuple[list, list]:
    """The worktree and index views `_apply` entry points take."""
    from dienpy.hunks import _hunks

    return _hunks.parse(str(repo)), _hunks.parse(str(repo), staged=True)


def seed(repo: Path) -> dict[str, str]:
    """A current run with one patch per hunk of a.txt and b.txt; returns title -> patch id."""
    from dienpy.hunks import _cache, _config, _hunks

    root = str(repo)
    hunks = _hunks.parse(root)
    a1, a2 = ids(hunks, "a.txt")
    b1 = ids(hunks, "b.txt")[0]
    patches = [
        {"id": "p1", "title": "a first", "message": "body one", "hunks": [a1]},
        {"id": "p2", "title": "a second", "message": "", "hunks": [a2]},
        {"id": "p3", "title": "b edit", "message": "", "hunks": [b1]},
    ]
    config = _config.Config("normal", "sonnet", "bare")
    _cache.set_entry(root, config, hunks, patches)
    _cache.touch_last(root, config)
    return {p["title"]: p["id"] for p in patches}
