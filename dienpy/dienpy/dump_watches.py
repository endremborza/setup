import datetime as dt
import json
import os
import re
from pathlib import Path
from subprocess import check_output

import pandas as pd

# sudo vim /etc/systemd/system/tv-tcpdump.service
# sudo tcpdump -i eth1 'src host 192.168.1.236 and tcp[13] & 8 != 0 and tcp[13] & 16 != 0' -U  -w /var/services/homes/borza/tv-capture.pcap

scp = f"{os.environ['SETUP_REPO']}/bash-scripts/upnpd.sh"
ifile = "/volume2/homes/borza/tv-capture.pcap"
NAS_ADDR = "home-nas-alpha"


def getd(oid):
    return json.loads(check_output([scp, oid]))["DIDL-Lite"]


def tol(ml):
    return ml if isinstance(ml, list) else [ml]


def dump_watches():
    idf = dt.date.today().isoformat()
    get_watch_history().assign(date=idf).to_csv(
        f"~/logs/watches/{idf}.csv", index=False
    )
    check_output(["ssh", "home-nas-alpha", f"rm {ifile}"])
    check_output(["ssh", "home-nas-alpha", f"sudo systemctl restart tv-tcpdump"])


def show_watches(use_cache: bool = False):
    print(get_watch_history(use_cache).to_markdown(index=False))


def build_upnp_tree():
    dirs = []
    nondirs = []

    def rec(oid):
        try:
            d = getd(oid)
        except:
            return
        for c in tol(d.get("container", [])):
            if c.get("upnp:class") == "object.container.storageFolder":
                dirs.append(c)
                rec(c["@id"])
        for c in tol(d.get("item", [])):
            nondirs.append(c)

    rec("0")
    return nondirs


def load_upnp_tree(use_cache: bool):
    _cache_path = Path("/tmp/nas-upnp-cache.json")
    if use_cache and _cache_path.exists():
        return json.loads(_cache_path.read_text())
    else:
        nondirs = build_upnp_tree()
        _cache_path.write_text(json.dumps(nondirs))
        return nondirs


def get_watch_history(use_cache=False):
    nondirs = load_upnp_tree(use_cache)

    # dirdic = {d["@id"]: d["dc:title"] for d in dirs}
    file_recs = [d["res"] | {"title": d["dc:title"]} for d in nondirs]
    file_map = {d["#text"].split("/v/")[-1]: d["title"] for d in file_recs}

    ofile = "/tmp/tvtcp-dumpfile"
    check_output(["scp", f"home-nas-alpha:{ifile}", ofile])
    ostr = check_output(["tcpdump", "-r", ofile, "-A"]).decode()
    Path(ofile).unlink()

    sub_base = set(re.findall(r"(NDLNA/\d+\.[a-z|0-9|A-Z]+)", ostr))
    sub_map = {k: file_map.get(k, "") for k in sub_base}

    runs = []
    ctime = ""
    for i, l in enumerate(ostr.split("\n")):
        if trex := re.findall(r"(\d\d:\d\d:\d\d)\.\d+ IP", l):
            ctime = trex[0]
        for k, v in sub_map.items():
            if k in l:
                runs.append({"l": i, "title": v, "time": ctime})

    return pd.DataFrame(runs).drop_duplicates(subset=["title"])


if __name__ == "__main__":
    show_watches()
    # dump_watches()
