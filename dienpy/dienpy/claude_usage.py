import json
import requests
import datetime
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table


from pathlib import Path

console = Console()


def find_token():
    path = Path.home() / ".claude" / ".credentials.json"
    with path.open() as f:
        data = json.load(f)
        try:
            return data["claudeAiOauth"]["accessToken"]
        except KeyError:
            pass

    raise RuntimeError("Could not find Claude Code OAuth token.")


def get_usage(token):
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

    token = find_token()
    usage = get_usage(token)

    five = usage["five_hour"]
    seven = usage["seven_day"]

    five_usage = five["utilization"]
    seven_usage = seven["utilization"]

    five_time = percent_time_elapsed(five["resets_at"], 5 * 3600)
    seven_time = percent_time_elapsed(seven["resets_at"], 7 * 24 * 3600)

    console.rule("[bold]Claude Code Usage[/bold]")

    table = Table(show_header=False, pad_edge=False)
    table.add_column("Label", style="bold")
    table.add_column("Bar")

    def progress_bar(pct, color):
        progress = Progress(
            TextColumn("{task.percentage:>5.1f}%"),
            BarColumn(bar_width=40, complete_style=color),
            expand=False,
        )
        task = progress.add_task("", total=100)
        progress.update(task, completed=pct)
        return progress

    table.add_row("5-Hour Usage", progress_bar(five_usage, "cyan"))
    table.add_row("7-Day Usage", progress_bar(seven_usage, "magenta"))
    table.add_row("5-Hour Time", progress_bar(five_time, "green"))
    table.add_row("7-Day Time", progress_bar(seven_time, "yellow"))

    console.print(table)
    console.print()

    # Burn rate signal
    five_delta = five_usage - five_time
    seven_delta = seven_usage - seven_time

    def burn_line(label, delta):
        if delta > 5:
            style = "bold red"
            status = "Over pace"
        elif delta < -5:
            style = "bold green"
            status = "Under pace"
        else:
            style = "bold white"
            status = "On pace"
        console.print(f"{label:<15} {delta:+6.1f}%   [{style}]{status}[/{style}]")

    # burn_line("5-Hour", five_delta)
    # burn_line("7-Day", seven_delta)
    console.print()


if __name__ == "__main__":
    main()
