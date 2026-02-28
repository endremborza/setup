import json
import requests
import datetime
import argparse
import time

from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.rule import Rule
from rich.progress import Progress, BarColumn, TextColumn

console = Console()


def find_token():
    path = Path.home() / ".claude" / ".credentials.json"
    with path.open() as f:
        data = json.load(f)
        return data["claudeAiOauth"]["accessToken"]


def get_usage():
    token = find_token()
    url = "https://api.anthropic.com/api/oauth/usage"
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


def percent_time_elapsed(resets_at, total_seconds):
    reset = datetime.datetime.fromisoformat(resets_at)
    now = datetime.datetime.now(datetime.timezone.utc)
    elapsed = total_seconds - (reset - now).total_seconds()
    pct = max(0, min(100, (elapsed / total_seconds) * 100))
    return pct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--w", "--watch", action="store_true", dest="watch")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    token = find_token()

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

    def render():
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Group(
            Rule("[bold]Claude Code Usage[/bold]"),
            progress,
            "",
            f"[dim]Last updated: {timestamp}[/dim]",
        )

    def update_values():
        usage = get_usage()
        five = usage["five_hour"]
        seven = usage["seven_day"]

        five_usage = five["utilization"]
        seven_usage = seven["utilization"]

        five_time = percent_time_elapsed(five["resets_at"], 5 * 3600)
        seven_time = percent_time_elapsed(seven["resets_at"], 7 * 24 * 3600)

        progress.update(five_usage_task, completed=five_usage)
        progress.update(seven_usage_task, completed=seven_usage)
        progress.update(five_time_task, completed=five_time)
        progress.update(seven_time_task, completed=seven_time)

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


if __name__ == "__main__":
    main()
