import argparse
import json
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from subprocess import check_output
from typing import Optional

ROOT_DIR = Path("/mnt/alpha-video/archive/night-time/")
LOG_FILE = Path("/mnt/data/logs/nightvid.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)
CONFIG_FILE = Path.home() / ".config" / "nightvid.json"
SERIES_STATE_FNAME = "night-vid.json"
STATE_FILE = ROOT_DIR / SERIES_STATE_FNAME
EXTENSIONS = {"mkv", "mp4"}


@dataclass
class Config:
    current_series: str = ""


@dataclass
class GlobalState:
    d: str = ""
    vlc_pid: int = 0
    timer_pid: int = 0


@dataclass
class SeriesState:
    stopped_at: float = 0
    started_at: float = 0
    offset: float = 0
    durations: list[float] = field(default_factory=list)


def _load(cls, fp: Path):
    try:
        return cls(**json.loads(fp.read_text()))
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return cls()


def load_config() -> Config:
    return _load(Config, CONFIG_FILE)


def save_config(c: Config) -> None:
    CONFIG_FILE.write_text(json.dumps(asdict(c)))


def load_global() -> GlobalState:
    return _load(GlobalState, STATE_FILE)


def save_global(s: GlobalState) -> None:
    STATE_FILE.write_text(json.dumps(asdict(s)))


def load_series(name: str) -> SeriesState:
    return _load(SeriesState, ROOT_DIR / name / SERIES_STATE_FNAME)


def save_series(name: str, s: SeriesState) -> None:
    (ROOT_DIR / name / SERIES_STATE_FNAME).write_text(json.dumps(asdict(s)))


def iter_files(series: str):
    p = ROOT_DIR / series
    for fp in sorted(p.iterdir()):
        if fp.suffix.lstrip(".") in EXTENSIONS:
            yield fp


def list_series() -> list[str]:
    return sorted(d.name for d in ROOT_DIR.iterdir() if d.is_dir())


def get_duration(fp: Path) -> float:
    out = check_output(
        [
            "ffprobe",
            "-i",
            fp.as_posix(),
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
        ]
    )
    return float(re.findall(r"duration=([\d.]+)", out.decode())[0])


def ensure_durations(name: str) -> SeriesState:
    state = load_series(name)
    if not state.durations:
        files = list(iter_files(name))
        state.durations = [get_duration(fp) for fp in files]
        save_series(name, state)
    return state


def resolve_position(name: str, state: SeriesState) -> tuple[list[Path], int, float]:
    files = list(iter_files(name))
    offset = state.offset
    i = 0
    for dur in state.durations:
        if dur > offset:
            break
        i += 1
        offset -= dur
    return files, i, offset


def fmt_ep(files: list[Path], i: int, offset: float) -> str:
    if i >= len(files):
        return "finished"
    name = files[i].name
    ep = next(iter(re.findall(r"S\d+E\d+", name)), f"ep{i + 1}")
    return f"{ep} @ {round(offset / 60, 1)}min"


def cancel_timer(pid: int) -> None:
    if pid:
        try:
            pgid = os.getpgid(pid)
            if pgid != os.getpgrp():
                os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def stop_vlc(state: GlobalState) -> None:
    if state.vlc_pid:
        try:
            os.kill(state.vlc_pid, 15)
        except ProcessLookupError:
            pass


def cmd_start(series: Optional[str], sleep_mins: Optional[float]) -> None:
    cfg = load_config()
    name = series or cfg.current_series
    if not name:
        raise SystemExit(
            "No series specified and no current series set. Use: nightvid set SERIES"
        )

    gstate = load_global()
    stop_vlc(gstate)
    cancel_timer(gstate.timer_pid)
    if gstate.d:
        _save_stop_position(gstate)

    sstate = ensure_durations(name)
    files, i, offset = resolve_position(name, sstate)
    if i >= len(files):
        raise SystemExit(f"Series '{name}' is finished. Use: nightvid reset {name!r}")

    uris = ["file://" + fp.as_posix() for fp in files[i:]]
    proc = subprocess.Popen(
        ["vlc", "--extraintf", "http", "--http-password", "pw", *uris]
    )

    # seek to offset within first file
    if offset > 1:
        url = (
            f"http://localhost:8080/requests/status.xml?command=seek&val={int(offset)}s"
        )
        for _ in range(4):
            time.sleep(1.5)
            try:
                check_output(["curl", "--silent", "--user", ":pw", url])
                break
            except subprocess.CalledProcessError:
                pass

    sstate.started_at = time.time()
    save_series(name, sstate)

    timer_pid = 0
    if sleep_mins:
        seconds = int(sleep_mins * 60)
        timer_proc = subprocess.Popen(
            f"sleep {seconds} && ~/.local/bin/dienpy nightvid stop",
            shell=True,
            start_new_session=True,
        )
        timer_pid = timer_proc.pid
        print(f"Sleep timer set for {sleep_mins:.0f} minutes")

    save_global(GlobalState(d=name, vlc_pid=proc.pid, timer_pid=timer_pid))
    log.info(
        "start series=%s pos=%s pid=%d%s",
        name,
        fmt_ep(files, i, offset),
        proc.pid,
        f" sleep={sleep_mins:.0f}min" if sleep_mins else "",
    )
    print(f"Playing '{name}' from {fmt_ep(files, i, offset)}")
    if cfg.current_series != name:
        cfg.current_series = name
        save_config(cfg)


def _save_stop_position(gstate: GlobalState) -> None:
    name = gstate.d
    sstate = load_series(name)
    if sstate.started_at:
        elapsed = max(time.time() - sstate.started_at - 10, 0)
        sstate.offset += elapsed
        sstate.started_at = 0
        save_series(name, sstate)


def cmd_stop() -> None:
    gstate = load_global()
    if not gstate.d and not gstate.vlc_pid:
        print("Nothing playing.")
        return
    stop_vlc(gstate)
    cancel_timer(gstate.timer_pid)
    if gstate.d:
        _save_stop_position(gstate)
        log.info("stop series=%s", gstate.d)
        print(f"Stopped '{gstate.d}', position saved.")
    save_global(GlobalState())


def cmd_status() -> None:
    gstate = load_global()
    if not gstate.d:
        cfg = load_config()
        if cfg.current_series:
            print(f"Not playing. Current series: {cfg.current_series}")
        else:
            print("Not playing.")
        return
    sstate = load_series(gstate.d)
    files, i, offset = resolve_position(gstate.d, sstate)
    pid_alive = gstate.vlc_pid and _pid_exists(gstate.vlc_pid)
    status = "playing" if pid_alive else "paused/stopped"
    print(f"{gstate.d} [{status}]: {fmt_ep(files, i, offset)}")
    if gstate.timer_pid:
        print(f"Sleep timer active (pid {gstate.timer_pid})")


def cmd_ls() -> None:
    cfg = load_config()
    for name in list_series():
        sstate = load_series(name)
        if sstate.durations:
            files, i, offset = resolve_position(name, sstate)
            pos = fmt_ep(files, i, offset)
        else:
            pos = "(not started)"
        marker = " *" if name == cfg.current_series else ""
        print(f"{name}{marker}: {pos}")


def cmd_reset(series: Optional[str]) -> None:
    cfg = load_config()
    name = series or cfg.current_series
    if not name:
        raise SystemExit("No series specified.")
    sstate = load_series(name)
    sstate.offset = 0
    sstate.started_at = 0
    save_series(name, sstate)
    print(f"Reset '{name}'.")


def cmd_set(series: str) -> None:
    available = list_series()
    if series not in available:
        matches = [s for s in available if series.lower() in s.lower()]
        if len(matches) == 1:
            series = matches[0]
        elif matches:
            raise SystemExit(f"Ambiguous: {matches}")
        else:
            raise SystemExit(f"Not found. Available: {available}")
    cfg = load_config()
    cfg.current_series = series
    save_config(cfg)
    print(f"Current series set to '{series}'.")


def cmd_rewind(minutes: float, series: Optional[str]) -> None:
    cfg = load_config()
    name = series or cfg.current_series
    if not name:
        raise SystemExit("No series specified and no current series set.")
    sstate = load_series(name)
    seconds = minutes * 60
    sstate.offset = max(sstate.offset - seconds, 0)
    sstate.started_at = 0
    save_series(name, sstate)
    files, i, offset = resolve_position(name, sstate)
    log.info(
        "rewind series=%s by=%.1fmin new_pos=%s",
        name,
        minutes,
        fmt_ep(files, i, offset),
    )
    print(f"Rewound '{name}' by {minutes:.1f} min → {fmt_ep(files, i, offset)}")


def cmd_fwd(minutes: float, series: Optional[str]) -> None:
    cfg = load_config()
    name = series or cfg.current_series
    if not name:
        raise SystemExit("No series specified and no current series set.")
    sstate = load_series(name)
    seconds = minutes * 60
    sstate.offset += seconds
    sstate.started_at = 0
    save_series(name, sstate)
    files, i, offset = resolve_position(name, sstate)
    log.info(
        "fwd series=%s by=%.1fmin new_pos=%s",
        name,
        minutes,
        fmt_ep(files, i, offset),
    )
    print(f"Fast-forwarded '{name}' by {minutes:.1f} min → {fmt_ep(files, i, offset)}")


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


SUBCOMMANDS = ["start", "stop", "status", "ls", "reset", "set", "rewind", "fwd"]


def get_completions(args: list[str]) -> list[str]:
    if len(args) <= 1:
        return SUBCOMMANDS
    cmd = args[0]
    if cmd in ("start", "reset", "set") and len(args) == 2:
        try:
            series = list_series()
        except (FileNotFoundError, PermissionError):
            series = []
        if cmd == "start":
            return series + ["--sleep"]
        return series
    if cmd == "start" and len(args) == 3 and args[1] == "--sleep":
        return []
    return []


def main() -> None:
    p = argparse.ArgumentParser(prog="nightvid")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Start playback")
    sp.add_argument("series", nargs="?")
    sp.add_argument("--sleep", type=float, metavar="MINS", help="Stop after N minutes")

    sub.add_parser("stop", help="Stop playback and save position")
    sub.add_parser("status", help="Show current status")
    sub.add_parser("ls", help="List all series with current position")

    rp = sub.add_parser("reset", help="Reset progress for a series")
    rp.add_argument("series", nargs="?")

    setp = sub.add_parser("set", help="Set current series")
    setp.add_argument("series")

    rwp = sub.add_parser("rewind", help="Rewind current series by N minutes")
    rwp.add_argument("minutes", type=float, metavar="MINS")
    rwp.add_argument("series", nargs="?")

    fwp = sub.add_parser("fwd", help="Fast-forward current series by N minutes")
    fwp.add_argument("minutes", type=float, metavar="MINS")
    fwp.add_argument("series", nargs="?")

    args = p.parse_args()

    match args.cmd:
        case "start":
            cmd_start(args.series, args.sleep)
        case "stop":
            cmd_stop()
        case "status":
            cmd_status()
        case "ls":
            cmd_ls()
        case "reset":
            cmd_reset(args.series)
        case "set":
            cmd_set(args.series)
        case "rewind":
            cmd_rewind(args.minutes, args.series)
        case "fwd":
            cmd_fwd(args.minutes, args.series)
