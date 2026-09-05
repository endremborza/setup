"""Show or watch Claude usage windows (5h session, weekly, weekly per scoped model)."""

import datetime
import os
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.progress import BarColumn, Progress, TextColumn
from rich.rule import Rule

from . import _auth as auth


class Http429(Exception):
    pass


console = Console()
_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_SPANS = {"session": 5 * 3600, "weekly_all": 7 * 24 * 3600, "weekly_scoped": 7 * 24 * 3600}


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
    if r.status_code == 429:
        raise Http429()
    r.raise_for_status()
    return r.json()


def _when(value: str | None) -> datetime.datetime | None:
    return datetime.datetime.fromisoformat(value) if value else None


def parse_windows(usage: dict) -> list[Window]:
    """Typed windows from the payload's ``limits``; the legacy pair when it is absent."""
    limits = usage.get("limits")
    if not limits:
        return [
            Window("session", float(usage["five_hour"]["utilization"]), _when(usage["five_hour"]["resets_at"])),
            Window("weekly_all", float(usage["seven_day"]["utilization"]), _when(usage["seven_day"]["resets_at"])),
        ]
    out = []
    for lim in limits:
        scope = ((lim.get("scope") or {}).get("model") or {}).get("display_name") or ""
        out.append(Window(str(lim["kind"]), float(lim["percent"]), _when(lim.get("resets_at")), scope))
    return out


def windows(creds_path: Path | None = None) -> list[Window]:
    return parse_windows(get_usage(creds_path))


def main(*, watch: bool = False, interval: int = 300) -> None:
    """Show or watch Claude usage windows (5h session, weekly, weekly per scoped model)."""
    os.system("clear")
    progress = Progress(
        TextColumn("[bold]{task.fields[label]}"),
        TextColumn("{task.percentage:>5.1f}%"),
        BarColumn(bar_width=40),
        expand=False,
    )
    tasks: dict[str, tuple[int, int]] = {}
    resets: list[str] = []

    def render() -> Group:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Group(
            Rule("[bold]Claude Code Usage[/bold]"),
            progress,
            "",
            f"[dim]Last updated: {timestamp}  |  {'  |  '.join(resets)}[/dim]",
        )

    def update_values() -> None:
        resets.clear()
        for w in windows():
            if w.label not in tasks:
                tasks[w.label] = (
                    progress.add_task("", total=100, label=f"{w.label} Usage"),
                    progress.add_task("", total=100, label=f"{w.label} Time"),
                )
            usage_task, time_task = tasks[w.label]
            progress.update(usage_task, completed=w.percent)
            progress.update(time_task, completed=w.time_percent or 0.0)
            if w.resets_at:
                fmt = "%H:%M" if w.kind == "session" else "%a %H:%M"
                resets.append(f"{w.label} resets {w.resets_at.astimezone().strftime(fmt)}")

    if watch:
        try:
            with Live(render(), refresh_per_second=4, console=console) as live:
                while True:
                    try:
                        update_values()
                    except Exception as e:
                        print(type(e).__name__)
                    live.update(render())
                    time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopped watching.[/bold yellow]")
    else:
        update_values()
        console.print(render())
