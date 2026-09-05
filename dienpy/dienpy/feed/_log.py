"""Per-run artifacts under <log_dir>: the raw stream-json (or console text), the final report, and runs.md."""

import datetime
from pathlib import Path
from typing import IO

from ..ai import Outcome

_HEADER = (
    "| when | prompt | profile | outcome | hunks | turns | minutes | cost | usage after | report |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)


def stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d-%H%M")


class RunLog:
    def __init__(self, log_dir: Path, name: str):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.dir = log_dir
        self.base = log_dir / f"{stamp()}-{name}"

    def stream(self, suffix: str = "") -> IO[str]:
        return open(f"{self.base}{suffix}.jsonl", "w")

    def console(self) -> IO[str]:
        return open(f"{self.base}.out", "w")

    def report(self, outcome: Outcome, header: str) -> Path:
        path = Path(f"{self.base}.md")
        path.write_text(f"# {header}\n\n{outcome.result.strip()}\n")
        return path


def append_run(log_dir: Path, line: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "runs.md"
    new = not path.exists()
    with path.open("a") as f:
        if new:
            f.write(_HEADER)
        f.write(line + "\n")
