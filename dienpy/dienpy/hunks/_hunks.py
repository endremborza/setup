"""Diff parsing + stable hunk IDs.

PARITY CONTRACT: IDs must match nvim's regroup/diff.lua byte-for-byte —
sha256(path + "\\x1f" + body_lines_joined_by_newline)[:12], "~n" suffix for
duplicates in parse order, whole-file entries hash their header minus `index `
lines. Change both implementations together; tests/test_group_parity.py pins
this. A mismatch is safe but visible: the nvim side reads the cache as fully
stale.
"""

import hashlib
import subprocess
from dataclasses import dataclass

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
    text: str


def git_root() -> str:
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if res.returncode != 0:
        raise SystemExit("not in a git repository")
    return res.stdout.strip()


def _git(root: str, args: list[str], ok_codes: tuple[int, ...] = (0,)) -> str:
    res = subprocess.run(
        ["git", *_GIT_CFG, *args], capture_output=True, text=True, cwd=root
    )
    if res.returncode not in ok_codes:
        raise SystemExit(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


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


def parse(root: str) -> list[Hunk]:
    files = _parse_diff(_git(root, ["diff", "--no-ext-diff", "--no-color", "HEAD"]))
    for path in _git(root, ["ls-files", "--others", "--exclude-standard"]).splitlines():
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

    def register(path: str, kind: str, body: list[str], text: str) -> None:
        base = hashlib.sha256(
            (path + "\x1f" + "\n".join(body)).encode()
        ).hexdigest()[:12]
        n = counts.get(base, 0) + 1
        counts[base] = n
        hunks.append(Hunk(base if n == 1 else f"{base}~{n}", path, kind, text))

    for f in files:
        path = f["path"]
        if path is None:
            raise SystemExit(
                f"could not determine path for diff section: {f['header'][0]}"
            )
        if not f["hunks"]:
            body = [ln for ln in f["header"] if not ln.startswith("index ")]
            kind = "untracked" if f["untracked"] else "file"
            register(path, kind, body, "\n".join(f["header"]))
        else:
            kind = "untracked" if f["untracked"] else "hunk"
            for h in f["hunks"]:
                register(path, kind, h["body"], h["header"] + "\n" + "\n".join(h["body"]))
    return hunks
