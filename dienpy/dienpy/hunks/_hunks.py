"""Diff parsing and content-addressed hunk ids.

A hunk id is sha256(path + "\\x1f" + body lines joined by "\\n")[:12], with a "~n"
suffix for the n-th duplicate in parse order; a whole-file entry (new, deleted, binary,
mode-only or purely renamed file) hashes its header, whose full-length `index` line
names the blobs. The `@@` header is not hashed, so a hunk keeps its id while edits
elsewhere shift its line numbers, and the same content in the index and in the
worktree diff yields the same id.

Untracked files join the worktree diff through a scratch copy of the index holding
intent-to-add entries, so one `git diff HEAD` describes everything and their entries
have the shape they will have once staged. Git output is decoded with surrogateescape:
any byte sequence survives the round trip back into `git apply`.
"""

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dienpy._git import Repo

_GIT_CFG = [
    "-c",
    "diff.noprefix=false",
    "-c",
    "diff.mnemonicprefix=false",
    "-c",
    "diff.suppressBlankEmpty=false",
    "-c",
    "core.quotePath=false",
]
# --full-index: an abbreviated blob id would grow with the repo and move whole-file ids
_DIFF = ("diff", "--no-color", "--no-ext-diff", "--no-textconv", "--full-index")

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)")
_ESCAPES = {
    b"n": b"\n",
    b"t": b"\t",
    b"r": b"\r",
    b"a": b"\a",
    b"b": b"\b",
    b"f": b"\f",
    b"v": b"\v",
}


@dataclass
class Hunk:
    id: str
    path: str
    kind: str  # hunk | file | untracked
    header: str  # the file-level diff header, shared by the file's hunks
    text: str  # `@@` header plus body; the file header alone for a whole-file entry
    new_start: int  # `@@ +start`: where the change begins in the current file
    old_span: tuple[
        int, int
    ]  # `@@ -start,len`: the HEAD lines covered; (0, 0) whole-file

    @property
    def display(self) -> str:
        """`text` as valid UTF-8 for JSON and prompts; `text` itself keeps every byte."""
        return utf8(self.text)

    def as_json(self) -> dict:
        return {
            "id": self.id,
            "path": utf8(self.path),
            "kind": self.kind,
            "new_start": self.new_start,
            "text": self.display,
        }


def repo(root: str) -> Repo:
    return Repo(root, cfg=_GIT_CFG)


def encode(s: str) -> bytes:
    return s.encode("utf-8", "surrogateescape")


def utf8(s: str) -> str:
    return encode(s).decode("utf-8", "replace")


def raw(r: Repo, *args: str, stdin: str | None = None) -> str:
    """Bytes both ways, so diff bodies and paths of any encoding survive."""
    res = r.run_bytes(*args, stdin=None if stdin is None else encode(stdin))
    if res.returncode:
        raise SystemExit(
            f"git {' '.join(args)} failed in {r.path.name}: "
            f"{res.stderr.decode('utf-8', 'replace').strip()}"
        )
    return res.stdout.decode("utf-8", "surrogateescape")


def unquote(s: str) -> str:
    """git C-quotes a path holding a control char, a quote or a backslash."""
    if not (len(s) > 1 and s[0] == '"' and s[-1] == '"'):
        return s
    raw = encode(s[1:-1])
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] != 0x5C:  # backslash
            out.append(raw[i])
            i += 1
        elif raw[i + 1 : i + 2].isdigit():  # \ooo
            out.append(int(raw[i + 1 : i + 4], 8))
            i += 4
        else:
            out += _ESCAPES.get(raw[i + 1 : i + 2], raw[i + 1 : i + 2])
            i += 2
    return out.decode("utf-8", "surrogateescape")


def _named(line: str, prefix: str, strip: str) -> str | None:
    """The path a `+++ b/…`, `--- a/…` or `rename to …` line names; git adds a tab
    after a path containing spaces."""
    if not line.startswith(prefix):
        return None
    p = unquote(line[len(prefix) :].rstrip("\t"))
    return p[len(strip) :] if p != "/dev/null" and p.startswith(strip) else None


def _same_path(line: str) -> str | None:
    """`diff --git a/P b/P` splits in the middle when both sides are one path."""
    rest = line[len("diff --git ") :]
    n = len(rest) // 2
    a, b = rest[:n], rest[n + 1 :]
    if len(rest) % 2 == 1 and rest[n] == " " and a.replace("a/", "b/", 1) == b:
        p = unquote(a)
        return p[2:] if p.startswith("a/") else None
    return None


def _file_path(header: list[str]) -> str | None:
    for prefix, strip in (
        ("+++ ", "b/"),
        ("rename to ", ""),
        ("copy to ", ""),
        ("--- ", "a/"),
    ):
        for line in header:
            p = _named(line, prefix, strip)
            if p:
                return p
    return _same_path(header[0])


def _parse_diff(text: str) -> list[dict]:
    files: list[dict] = []
    lines = text.split("\n")
    if lines and lines[-1] == "":  # the output's final newline is not a header line
        lines.pop()
    i, cur = 0, None
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            cur = {"header": [line], "hunks": []}
            files.append(cur)
            i += 1
            while (
                i < len(lines)
                and not lines[i].startswith("@@ ")
                and not lines[i].startswith("diff --git ")
            ):
                cur["header"].append(lines[i])
                i += 1
            cur["path"] = _file_path(cur["header"])
        elif cur is not None and line.startswith("@@ "):
            hunk = {"header": line, "body": []}
            cur["hunks"].append(hunk)
            i += 1
            while i < len(lines) and lines[i][:1] in (" ", "+", "-", "\\"):
                hunk["body"].append(lines[i])
                i += 1
        else:
            i += 1
    return files


def _spans(header: str) -> tuple[tuple[int, int], int]:
    m = _HUNK_HEADER.match(header)
    if not m:
        return (0, 0), 1
    return (int(m[1]), 1 if m[2] is None else int(m[2])), max(1, int(m[3]))


def under(hunks: list[Hunk], path: str) -> list[Hunk]:
    """Hunks touching `path` — a repo-relative file or directory; `""` means everything."""
    prefix = path.strip("/")
    if not prefix:
        return hunks
    return [h for h in hunks if h.path == prefix or h.path.startswith(prefix + "/")]


def _diff_head(r: Repo) -> str:
    res = r.run_bytes(*_DIFF, "HEAD")
    if res.returncode and r.run("rev-parse", "-q", "--verify", "HEAD").returncode:
        # unborn branch: everything differs from the empty tree
        return raw(r, *_DIFF, r.out("hash-object", "-t", "tree", "/dev/null"))
    if res.returncode:
        raise SystemExit(
            f"git diff HEAD failed: {res.stderr.decode('utf-8', 'replace')}"
        )
    return res.stdout.decode("utf-8", "surrogateescape")


def _worktree_diff(r: Repo) -> tuple[str, set[str]]:
    others = raw(r, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    untracked = {
        p for p in others if p and not p.endswith("/")
    }  # a nested repo lists as a dir
    if not untracked:
        return _diff_head(r), untracked
    index = Path(r.out("rev-parse", "--git-path", "index"))
    if not index.is_absolute():
        index = r.path / index
    fd, tmp = tempfile.mkstemp(prefix="regroup-index.", dir=index.parent)
    os.close(fd)
    try:
        if index.exists():
            shutil.copyfile(index, tmp)
        else:
            os.unlink(
                tmp
            )  # git reads a missing index as empty, a zero-length one as corrupt
        scratch = Repo(r.path, cfg=_GIT_CFG, env={"GIT_INDEX_FILE": tmp})
        raw(
            scratch,
            "add",
            "-N",
            "--pathspec-from-file=-",
            "--pathspec-file-nul",
            stdin="\0".join(sorted(untracked)),
        )
        return _diff_head(scratch), untracked
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def parse(root: str, *, staged: bool = False, rev: str = "") -> list[Hunk]:
    """Worktree+index vs HEAD with untracked files; `staged` the index alone; `rev` any
    `git diff` revision argument such as `main...topic` (no untracked scan)."""
    r = repo(root)
    untracked: set[str] = set()
    if staged:
        text = raw(r, *_DIFF, "--cached")
    elif rev:
        text = raw(r, *_DIFF, rev)
    else:
        text, untracked = _worktree_diff(r)

    hunks: list[Hunk] = []
    counts: dict[str, int] = {}

    def register(
        path: str,
        kind: str,
        body: list[str],
        header: str,
        text: str,
        start: int,
        old: tuple[int, int],
    ) -> None:
        base = hashlib.sha256(encode(path + "\x1f" + "\n".join(body))).hexdigest()[:12]
        n = counts.get(base, 0) + 1
        counts[base] = n
        hid = base if n == 1 else f"{base}~{n}"
        hunks.append(Hunk(hid, path, kind, header, text, start, old))

    for f in _parse_diff(text):
        path = f["path"]
        if path is None:
            raise SystemExit(
                f"could not determine path for diff section: {f['header'][0]}"
            )
        header = "\n".join(f["header"])
        new = path in untracked
        if not f["hunks"]:
            kind = "untracked" if new else "file"
            register(path, kind, f["header"], header, header, 1, (0, 0))
        else:
            kind = "untracked" if new else "hunk"
            for h in f["hunks"]:
                old, start = _spans(h["header"])
                text = h["header"] + "\n" + "\n".join(h["body"])
                register(path, kind, h["body"], header, text, start, old)
    return hunks
