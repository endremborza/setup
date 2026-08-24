"""Every git call in the ecosystem, repo-bound (`Repo`) or bare (module `run`).

Failure policy is decided here rather than at each call site: `run` reports and
never raises, `raw`/`out` abort with git's own stderr, `maybe` yields None for
the best-effort probes (a missing binary and a hung call read as failure too).
Timeouts belong to the `Repo`; None means no limit, so pollers set one and
commands that legitimately block (push, clone) do not.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path


class Repo:
    """`git -C <path>`, so callers never repeat the path."""

    def __init__(
        self,
        path: Path | str,
        *,
        cfg: Sequence[str] = (),
        timeout: float | None = None,
    ) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self._base = ["git", "-C", str(path), *cfg]

    def run(
        self, *args: str, capture: bool = True, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Nonzero exits come back as `.returncode`, not as an exception."""
        return _exec(
            [*self._base, *args],
            capture,
            self.timeout if timeout is None else timeout,
        )

    def raw(
        self, *args: str, ok_codes: tuple[int, ...] = (0,), timeout: float | None = None
    ) -> str:
        """stdout verbatim -- diff bodies carry significant trailing whitespace."""
        res = self.run(*args, timeout=timeout)
        if res.returncode not in ok_codes:
            raise SystemExit(
                f"git {' '.join(args)} failed in {self.path.name}: {res.stderr.strip()}"
            )
        return res.stdout

    def out(
        self, *args: str, ok_codes: tuple[int, ...] = (0,), timeout: float | None = None
    ) -> str:
        return self.raw(*args, ok_codes=ok_codes, timeout=timeout).strip()

    def maybe(self, *args: str, timeout: float | None = None) -> str | None:
        """Stripped stdout, or None if git fails, hangs or is missing."""
        try:
            res = self.run(*args, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            return None
        return res.stdout.strip() if res.returncode == 0 else None

    def add(self, *paths: str) -> None:
        self._write("add", *paths)

    def commit(self, message: str, *paths: str) -> None:
        """Commit `paths` only; without them, whatever is staged."""
        self._write("commit", "-m", message, *(["--", *paths] if paths else []))

    def push(self) -> None:
        self._write("push")

    def has_staged(self, *paths: str) -> bool:
        return self.run("diff", "--cached", "--quiet", "--", *paths).returncode != 0

    def commit_paths(self, paths: list[str], message: str) -> bool:
        """Stage paths and commit only those, if they changed. True if a commit was made."""
        self.add(*paths)
        if not self.has_staged(*paths):
            return False
        self.commit(message, *paths)
        return True

    def _write(self, *args: str) -> None:
        """Git's own output is the user feedback for a write, so it streams."""
        res = self.run(*args, capture=False, timeout=self.timeout)
        if res.returncode:
            raise SystemExit(res.returncode)


def _exec(
    argv: list[str],
    capture: bool,
    timeout: float | None,
    cwd: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, capture_output=capture, text=True, timeout=timeout, cwd=cwd
    )


def run(
    *args: str,
    cwd: Path | str | None = None,
    capture: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Git with no repo in hand -- `clone`, `init`, `config --file`."""
    return _exec(["git", *args], capture, timeout, cwd)


def find_root(cwd: Path | str | None = None) -> str:
    res = run("rev-parse", "--show-toplevel", cwd=cwd)
    if res.returncode:
        raise SystemExit("not in a git repository")
    return res.stdout.strip()


def clone(url: str, dest: Path | str) -> Repo:
    """Clone into `dest`; progress streams, since clones are slow."""
    if run("clone", url, str(dest), capture=False).returncode:
        raise SystemExit(f"git clone {url} failed")
    return Repo(dest)
