"""Pin the hunk-ID parity contract between dienpy.hunks._hunks and nvim's regroup/diff.lua.

Runnable without pytest: `uv run python tests/test_group_parity.py`.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from dienpy.hunks import _hunks

_NVIM_CFG = Path(__file__).resolve().parents[2] / "dotfiles" / ".config" / "nvim"

_LUA = """\
local diff = require('regroup.diff')
local p = diff.parse(vim.env.PARITY_REPO)
local out = {}
for _, h in ipairs(p.hunks) do
  table.insert(out, h.id .. ':' .. h.kind .. ':' .. h.path)
end
io.write(table.concat(out, '\\n'))
os.exit(0)
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _mk_repo(base: Path) -> Path:
    repo = base / "parity-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("".join(f"{i}\n" for i in range(1, 41)))
    # two identical blocks far enough apart to stay separate hunks -> exercises ~n dedup
    dup = ["pad"] * 16
    dup[3] = dup[12] = "mid"
    (repo / "dup.txt").write_text("".join(f"{ln}\n" for ln in dup))
    (repo / "del.txt").write_text("one\ntwo\n")
    (repo / "sub").mkdir()
    (repo / "sub" / "b.txt").write_text("".join(f"b{i}\n" for i in range(1, 11)))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")

    a = (repo / "a.txt").read_text().splitlines()
    a[4], a[34] = "FIVE", "THIRTYFIVE"
    (repo / "a.txt").write_text("".join(f"{ln}\n" for ln in a))
    d = (repo / "dup.txt").read_text().splitlines()
    d[3] = d[12] = "MID"
    (repo / "dup.txt").write_text("".join(f"{ln}\n" for ln in d))
    b = (repo / "sub" / "b.txt").read_text().splitlines()
    b[0] = "B1"
    (repo / "sub" / "b.txt").write_text("".join(f"{ln}\n" for ln in b))
    (repo / "del.txt").unlink()
    (repo / "new.txt").write_text("brand new\ncontents\n")
    (repo / "new_bin").write_bytes(b"\x00\x01\x02")
    return repo


def test_parity() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = _mk_repo(Path(td))
        py_ids = [f"{h.id}:{h.kind}:{h.path}" for h in _hunks.parse(str(repo))]
        assert len(py_ids) >= 7, py_ids
        assert any(id_.split(":")[0].endswith("~2") for id_ in py_ids), (
            "duplicate-hunk ~n dedup not exercised"
        )

        lua_file = Path(td) / "parity.lua"
        lua_file.write_text(_LUA)
        res = subprocess.run(
            [
                "nvim",
                "--headless",
                "-u",
                "NONE",
                "--cmd",
                f"set rtp+={_NVIM_CFG}",
                "-l",
                str(lua_file),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PARITY_REPO": str(repo)},
        )
        assert res.returncode == 0, res.stderr
        assert res.stdout.splitlines() == py_ids, (
            f"ID PARITY BROKEN\nlua:\n{res.stdout}\npython:\n" + "\n".join(py_ids)
        )


if __name__ == "__main__":
    test_parity()
    print("PARITY PASS")
