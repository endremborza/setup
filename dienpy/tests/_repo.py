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
