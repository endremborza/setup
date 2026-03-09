import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from multiprocessing import Process, Queue
from pathlib import Path
from subprocess import Popen, check_output

import requests
from flask import Flask, request

META_FNAME = "night-vid.json"
OWN_PID = os.getpid()
PORT = 5699


FRAME1 = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Night Vid</title>
</head>
<body>
"""
FRAME2 = """
<script>
function sendRequest(ep) {
    var xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && xhr.status === 200) {
            console.log(xhr.responseText);
        }
    };
    xhr.open("GET", "/" + ep, true);
    xhr.send();
}
</script>

<style>

button { margin-left: 10px; }

body { background-color: #151515; }

h1,h2,h3,h4,p {color: #75A5A5; }

</style>

</body>
</html>
"""

extensions = ["mkv", "mp4"]

root_dir = Path("/mnt/alpha-video/archive/night-time/")
try:
    roots = sorted(root_dir.iterdir())
    print(f"got {len(roots)} roots")
except:
    print("device not mounted")
    roots = []

main_js = root_dir / META_FNAME

GLOB_PROC = None
GLOB_SHUTOFF_TIME = None
TIME_Q = Queue()


def shutoff_check(q: Queue):
    shutoff_time = None
    while True:
        try:
            shutoff_time = q.get(timeout=3)
        except:
            pass
        remaining = (shutoff_time or float("inf")) - time.time()
        # print(round(remaining / 60, 3), "until kill")
        if remaining <= 0:
            requests.get(f"http://localhost:{PORT}/kill")


proc = Process(target=shutoff_check, args=(TIME_Q,), daemon=True)

app = Flask(__name__)


@dataclass
class GlobalState:
    d: str = ""


@dataclass
class DirState:
    stopped_at: float = 0
    started_at: float = 0
    offset: float = 0
    durations: list[float] = field(default_factory=list)


@app.route("/")
def home():

    dir_buttons = map(get_dir_block, idirs())
    sleep_buttons = [
        get_button(f"setsleep?mins={n}", f"{n} minutes") for n in [5, 15, 30, 40, 45]
    ]

    return page(
        f"""
<h1>Night Vid</h1>
        {get_button("volplus", "Vol +")}
        {get_button("volminus", "Vol -")}
        <hr>
        {"<hr>".join(dir_buttons)}
        <hr>
        {get_button("kill", "Stop")}
        <hr>
        <h3>Sleep In</h3>
        {"".join(sleep_buttons)}
"""
    )


@app.route("/setsleep")
def set_sleep_ep():
    n = float(request.args.get("mins", "20"))
    set_sleep(n)
    return "OK"


@app.route("/kill")
def kill():
    try:
        print(pre_kill())
    except:
        pass
    os.kill(OWN_PID, 15)
    return ""


def pre_kill():
    global GLOB_PROC
    if GLOB_PROC is None:
        return "NOTHING TO KILL"
    GLOB_PROC.kill()
    GLOB_PROC = None
    state = load_m()
    if not state.d:
        return "NO LOGGED DIR"
    dstate = load_d(state.d)
    dstate.stopped_at = time.time() - 10
    dstate.offset += max(dstate.stopped_at - dstate.started_at, 0)
    write_d(state.d, dstate)
    state.d = ""
    write_m(state)
    return "OK"


@app.route("/start")
def start():
    global GLOB_PROC
    if GLOB_PROC is not None:
        kill()
    dname = request.args.get("d", "")
    if not dname:
        return "OK"
    dstate = load_d(dname)
    if not dstate.durations:
        calc_dir(dname)
        dstate = load_d(dname)
    recs, i, offset = get_rio(dname, dstate)
    GLOB_PROC = get_run_proc(i, offset, recs)
    url = f"http://localhost:8080/requests/status.xml?command=seek&val={int(offset)}s"
    for _ in range(4):
        time.sleep(1.5)
        try:
            check_output(["curl", "--user", ":pw", url])
            break
        except:
            pass
    dstate.started_at = time.time()
    write_d(dname, dstate)
    state = load_m()
    state.d = dname
    write_m(state)
    return "OK"


@app.route("/volplus")
def volctl():
    # check_output(["xte", "key 0x1008ff13"])
    check_output(["hw-volchange", "5"])
    return "OK"


@app.route("/volminus")
def volctlm():
    # check_output(["xte", "key 0x1008ff11"])
    check_output(["hw-volchange", "-5"])
    return "OK"


@app.route("/shift")
def shift():
    state = load_m()
    if not state.d:
        return "Nothing"
    mins = float(request.args.get("m", "0"))
    dstate = load_d(state.d)
    dstate.offset += mins * 60
    write_d(state.d, dstate)
    return "OK"


@app.route("/reset")
def reset():
    dname = request.args.get("d", "")
    if not dname:
        return "NONE"
    dstate = load_d(dname)
    dstate.offset = 0
    write_d(dname, dstate)
    return "DONE"


def _load(cls, fp: Path):
    try:
        return cls(**json.loads(fp.read_text()))
    except FileNotFoundError:
        return cls()


def load_m():
    return _load(GlobalState, main_js)


def load_d(d: str):
    return _load(DirState, root_dir / d / META_FNAME)


def write_d(d: str, state: DirState):
    return (root_dir / d / META_FNAME).write_text(json.dumps(asdict(state)))


def write_m(state: GlobalState):
    return main_js.write_text(json.dumps(asdict(state)))


def calc_dir(dirname: str):
    t = 0
    durs = []
    for fp in iter_files(root_dir / dirname):
        dur = getd(fp)
        t += dur
        durs.append(dur)
    state = load_d(dirname)
    state.durations = durs
    write_d(dirname, state)
    return f"{dirname}: {len(durs)} files, {round(t / 60, 2)} minutes"


def iter_files(p: Path):
    for fp in sorted(p.iterdir()):
        if any(map(fp.name.endswith, extensions)):
            yield fp


def idirs():
    return filter(lambda f: f.is_dir(), root_dir.iterdir())


def set_sleep(mins):
    TIME_Q.put(time.time() + mins * 60)


def get_run_proc(rind: int, stime: float, fps):
    uris = ["file://" + fp.as_posix() for fp in fps[rind:]]
    # "--intf", "dummy",
    return Popen(["vlc", "--extraintf", "http", "--http-password", "pw", *uris])


def getd(fp):
    opts = ["-show_entries", "format=duration", "-v", "quiet"]
    co = check_output(["ffprobe", "-i", fp.as_posix(), *opts])
    return float(re.findall("duration=(.*)", co.decode())[0])


def get_button(endpoint, txt):
    return f"""<button onclick="sendRequest('{endpoint}')">{txt}</button>"""


def get_rio(dname: str, dstate: DirState):
    recs = list(iter_files(root_dir / dname))
    i = 0
    offset = dstate.offset
    for dur in dstate.durations:
        if dur > offset:
            break
        i += 1
        offset -= dur
    return recs, i, offset


def page(s):
    return FRAME1 + s + FRAME2


def get_dir_block(fp: Path):
    dstate = load_d(fp.name)
    recs, i, offset = get_rio(fp.name, dstate)
    ename = "?"
    if res := re.findall(r"S\d+E\d+", recs[i].name):
        ename = res[0]

    return (
        f"<h3>{fp.name}</h3>"
        + get_button(f"start?d={fp.name}", "Start playing")
        + get_button("shift?m=10", "+10 mins")
        + get_button("shift?m=-10", "-10 mins")
        + get_button(f"reset?d={fp.name}", "Reset")
        + f"<p>Starting from {ename} episode {i + 1} ({round(offset / 60, 1)} minutes)</p>"
    )


def main():
    proc.start()
    app.run("0.0.0.0", PORT, debug=False)
