"""Diff parsing and content-addressed hunk ids.

A hunk id is sha256(path + "\\x1f" + body lines joined by "\\n")[:12], with a "~n"
suffix for the n-th duplicate in parse order; a whole-file entry (new, deleted, binary
or purely renamed file) hashes its header minus the `index ` line. The `@@` header is
not hashed, so a hunk keeps its id while edits elsewhere shift its line numbers, and
the same content in the index and in the worktree diff yields the same id.
"""

import hashlib
import re
from dataclasses import dataclass

from dienpy._git import Repo, find_root

_GIT_CFG = [
    "-c",
    "diff.noprefix=false",
    "-c",
    "diff.mnemonicprefix=false",
    "-c",
    "core.quotePath=false",
]


@dataclass
class Hunk:
    id: str
    path: str
    kind: str  # hunk | file | untracked
    header: str  # the file-level diff header, shared by the file's hunks
    text: str  # `@@` header plus body; the file header alone for a whole-file entry
    new_start: int  # `@@ +start`: where the change begins in the current file

    def as_json(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "kind": self.kind,
            "new_start": self.new_start,
            "text": self.text,
        }


def git_root() -> str:
    return find_root()


def _git(
    root: str,
    args: list[str],
    ok_codes: tuple[int, ...] = (0,),
    stdin: str | None = None,
) -> str:
    return Repo(root, cfg=_GIT_CFG).raw(*args, ok_codes=ok_codes, stdin=stdin)


def head_sha(root: str) -> str:
    return _git(root, ["rev-parse", "HEAD"], ok_codes=(0, 128)).strip()


def _new_start(header: str) -> int:
    m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", header)
    return max(1, int(m[1])) if m else 1


def _file_path(header: list[str]) -> str | None:
    for line in header:
        if line.startswith("+++ b/") and len(line) > 6:
            return line[6:]
    for line in header:
        if line.startswith("--- a/") and len(line) > 6:
            return line[6:]
    idx = header[0].find(" b/")
    return header[0][idx + 3 :] if idx != -1 and len(header[0]) > idx + 3 else None


def _parse_diff(text: str) -> list[dict]:
    files: list[dict] = []
    lines = text.split("\n")
    i, cur = 0, None
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            cur = {"header": [line], "hunks": [], "untracked": False}
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


def under(hunks: list[Hunk], path: str) -> list[Hunk]:
    """Hunks touching `path` — a repo-relative file or directory; `""` means everything."""
    prefix = path.strip("/")
    if not prefix:
        return hunks
    return [h for h in hunks if h.path == prefix or h.path.startswith(prefix + "/")]


def parse(root: str, *, staged: bool = False, rev: str = "") -> list[Hunk]:
    """Worktree+index vs HEAD with untracked files; `staged` the index alone; `rev` any
    `git diff` revision argument such as `main...topic` (no untracked scan)."""
    target = "--cached" if staged else rev or "HEAD"
    files = _parse_diff(_git(root, ["diff", "--no-ext-diff", "--no-color", target]))
    untracked = (
        _git(root, ["ls-files", "--others", "--exclude-standard"]).splitlines()
        if not staged and not rev
        else []
    )
    for path in untracked:
        if not path:
            continue
        d = _git(
            root,
            ["diff", "--no-color", "--no-index", "--", "/dev/null", path],
            ok_codes=(0, 1),
        )
        parsed = _parse_diff(d)
        if parsed:
            parsed[0]["path"] = path
            parsed[0]["untracked"] = True
            files.append(parsed[0])

    hunks: list[Hunk] = []
    counts: dict[str, int] = {}

    def register(
        path: str, kind: str, body: list[str], header: str, text: str, start: int
    ) -> None:
        base = hashlib.sha256((path + "\x1f" + "\n".join(body)).encode()).hexdigest()[
            :12
        ]
        n = counts.get(base, 0) + 1
        counts[base] = n
        hid = base if n == 1 else f"{base}~{n}"
        hunks.append(Hunk(hid, path, kind, header, text, start))

    for f in files:
        path = f["path"]
        if path is None:
            raise SystemExit(
                f"could not determine path for diff section: {f['header'][0]}"
            )
        header = "\n".join(f["header"])
        kind = "untracked" if f["untracked"] else "hunk"
        if not f["hunks"]:
            body = [ln for ln in f["header"] if not ln.startswith("index ")]
            register(
                path, "untracked" if f["untracked"] else "file", body, header, header, 1
            )
        else:
            for h in f["hunks"]:
                text = h["header"] + "\n" + "\n".join(h["body"])
                register(path, kind, h["body"], header, text, _new_start(h["header"]))
    return hunks
