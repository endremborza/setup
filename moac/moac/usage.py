"""Show or watch Claude usage windows (5h session, weekly, weekly per scoped model)."""

import datetime
import os
import select
import sys
import termios
import time
import tty
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import _account
from . import _auth as auth
from ._account import Account, AccountName

if TYPE_CHECKING:
    from rich.console import Console, Group, RenderableType

_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_WEEK = 7 * 24 * 3600
_SPANS = {"session": 5 * 3600, "weekly_all": _WEEK, "weekly_scoped": _WEEK}


@dataclass(frozen=True)
class Window:
    kind: str  # session | weekly_all | weekly_scoped
    percent: float
    resets_at: datetime.datetime | None
    model: str = ""  # scope display name for weekly_scoped, e.g. "Fable"

    @property
    def label(self) -> str:
        if self.kind == "session":
            return "5-Hour"
        return f"7-Day {self.model}" if self.model else "7-Day"

    @property
    def time_percent(self) -> float | None:
        span = _SPANS.get(self.kind)
        if not span or not self.resets_at:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = span - (self.resets_at - now).total_seconds()
        return max(0.0, min(100.0, elapsed / span * 100))


def get_usage(creds_path: Path | None = None) -> dict:
    """Fetch the raw Claude usage payload (``limits``, ``five_hour``, ``seven_day``, ...)."""
    r = auth.request("get", _USAGE_URL, creds_path=creds_path)
    r.raise_for_status()
    return r.json()


def _when(value: str | None) -> datetime.datetime | None:
    return datetime.datetime.fromisoformat(value) if value else None


def parse_windows(usage: dict) -> list[Window]:
    """Typed windows from the payload's ``limits``; the legacy pair when it is absent."""
    limits = usage.get("limits")
    if not limits:
        return [
            Window(
                "session",
                float(usage["five_hour"]["utilization"]),
                _when(usage["five_hour"]["resets_at"]),
            ),
            Window(
                "weekly_all",
                float(usage["seven_day"]["utilization"]),
                _when(usage["seven_day"]["resets_at"]),
            ),
        ]
    out = []
    for lim in limits:
        scope = ((lim.get("scope") or {}).get("model") or {}).get("display_name") or ""
        out.append(
            Window(
                str(lim["kind"]),
                float(lim["percent"]),
                _when(lim.get("resets_at")),
                scope,
            )
        )
    return out


def windows(creds_path: Path | None = None) -> list[Window]:
    return parse_windows(get_usage(creds_path))


def _signed_in(account: str) -> list[Account]:
    """The named account, or every account with a login on this machine; none is an error."""
    chosen = [_account.get(account)] if account else [*_account.accounts().values()]
    found = [a for a in chosen if a.credentials.exists()]
    if not found:
        raise SystemExit("no signed-in account: run `moac login <account>`")
    return found


def _fetch(accounts: Sequence[Account]) -> dict[str, list[Window]]:
    return {a.name: windows(a.credentials) for a in accounts}


def _render(
    by_account: Mapping[str, Sequence[Window]],
    updated: datetime.datetime | None,
    *footer: "RenderableType",
) -> "Group":
    from rich.console import Group
    from rich.progress_bar import ProgressBar
    from rich.rule import Rule
    from rich.table import Table

    grid = Table.grid(padding=(0, 1))
    stamp = updated.strftime("%Y-%m-%d %H:%M:%S") if updated else "never"
    status = [f"Last updated: {stamp}"]
    for name, ws in by_account.items():
        who = f"{name} " if len(by_account) > 1 else ""
        for w in ws:
            for kind, pct in (("Usage", w.percent), ("Time", w.time_percent)):
                if pct is not None:
                    grid.add_row(
                        f"[bold]{who}{w.label} {kind}",
                        f"{pct:>5.1f}%",
                        ProgressBar(total=100, completed=pct, width=40),
                    )
            if w.resets_at:
                fmt = "%H:%M" if w.kind == "session" else "%a %H:%M"
                when = w.resets_at.astimezone().strftime(fmt)
                status.append(f"{who}{w.label} resets {when}")
    return Group(
        Rule("[bold]Claude Code Usage[/bold]"),
        grid,
        "",
        f"[dim]{'  |  '.join(status)}[/dim]",
        *footer,
    )


@contextmanager
def _cbreak(fd: int) -> Iterator[None]:
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _keys(fd: int, timeout: float) -> str:
    ready, _, _ = select.select([fd], [], [], timeout)
    return os.read(fd, 64).decode(errors="ignore") if ready else ""


def _watch(console: "Console", interval: int, accounts: Sequence[Account]) -> None:
    """Alternate-screen view redrawn from home every frame, so a resize cannot leave a stale copy behind.

    The fetch deadline is wall-clock and the key wait is capped at a second, so a resume from suspend refetches at once.
    """
    from rich.live import Live
    from rich.text import Text

    fd = sys.stdin.fileno()
    by_account: dict[str, list[Window]] = {}
    updated: datetime.datetime | None = None
    error = ""
    busy = False
    due = 0.0

    def frame() -> "Group":
        left = max(0, int(due - time.time()))
        state = "refreshing…" if busy else f"next in {left // 60}:{left % 60:02d}"
        keys = f"[dim][bold]r[/bold] refresh  [bold]q[/bold] quit  ·  {state}[/dim]"
        problem = Text(error, style="red", no_wrap=True, overflow="ellipsis")
        return _render(by_account, updated, keys, problem)

    with _cbreak(fd), Live(get_renderable=frame, console=console, screen=True) as live:
        while True:
            if time.time() >= due:
                busy = True
                live.refresh()
                try:
                    by_account = _fetch(accounts)
                    updated, error = datetime.datetime.now(), ""
                except Exception as e:
                    error = f"{type(e).__name__}: {e}"
                busy = False
                due = time.time() + interval
            key = _keys(fd, 1.0)
            if "q" in key:
                return
            if "r" in key:
                due = 0.0


def main(
    *, watch: bool = False, interval: int = 300, account: AccountName = ""
) -> None:
    """Show or watch Claude usage windows (5h session, weekly, weekly per scoped model); r refreshes and q quits the watch."""
    from rich.console import Console

    console = Console()
    accounts = _signed_in(account)
    if not watch:
        console.print(_render(_fetch(accounts), datetime.datetime.now()))
        return
    try:
        _watch(console, interval, accounts)
    except KeyboardInterrupt:
        pass
