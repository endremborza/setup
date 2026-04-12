import argparse
import datetime
import os
import time

from rich.console import Console, Group
from rich.live import Live
from rich.progress import BarColumn, Progress, TextColumn
from rich.rule import Rule

from . import auth


class Http429(Exception):
    pass


console = Console()
_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def _get_usage() -> dict:
    r = auth.request("get", _USAGE_URL)
    if r.status_code == 429:
        raise Http429()
    r.raise_for_status()
    return r.json()


def _percent_time_elapsed(resets_at: str, total_seconds: int) -> float:
    reset = datetime.datetime.fromisoformat(resets_at)
    now = datetime.datetime.now(datetime.timezone.utc)
    elapsed = total_seconds - (reset - now).total_seconds()
    return max(0.0, min(100.0, (elapsed / total_seconds) * 100))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", "-w", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    os.system("clear")

    progress = Progress(
        TextColumn("[bold]{task.fields[label]}"),
        TextColumn("{task.percentage:>5.1f}%"),
        BarColumn(bar_width=40),
        expand=False,
    )
    five_usage_task = progress.add_task("", total=100, label="5-Hour Usage")
    five_time_task = progress.add_task("", total=100, label="5-Hour Time")
    seven_usage_task = progress.add_task("", total=100, label="7-Day Usage")
    seven_time_task = progress.add_task("", total=100, label="7-Day Time")

    five_resets_at = [""]
    week_resets_at = [""]

    def render() -> Group:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Group(
            Rule("[bold]Claude Code Usage[/bold]"),
            progress,
            "",
            f"[dim]Last updated: {timestamp}  |  5h resets: {five_resets_at[0]} | 1w resets: {week_resets_at[0]}[/dim]",
        )

    def update_values() -> None:
        usage = _get_usage()
        five = usage["five_hour"]
        seven = usage["seven_day"]

        five_resets_at[0] = (
            datetime.datetime.fromisoformat(five["resets_at"])
            .astimezone()
            .strftime("%H:%M")
        )
        week_resets_at[0] = (
            datetime.datetime.fromisoformat(seven["resets_at"])
            .astimezone()
            .strftime("%a, %H")
        )

        progress.update(five_usage_task, completed=five["utilization"])
        progress.update(
            five_time_task, completed=_percent_time_elapsed(five["resets_at"], 5 * 3600)
        )
        progress.update(seven_usage_task, completed=seven["utilization"])
        progress.update(
            seven_time_task,
            completed=_percent_time_elapsed(seven["resets_at"], 7 * 24 * 3600),
        )

    if args.watch:
        try:
            with Live(render(), refresh_per_second=4, console=console) as live:
                while True:
                    try:
                        update_values()
                    except Exception as e:
                        print(type(e).__name__)
                    live.update(render())
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopped watching.[/bold yellow]")
    else:
        update_values()
        console.print(render())


def get_completions(args: list[str]) -> list[str]:
    return ["--watch", "--interval"]
