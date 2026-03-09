import datetime as dt
import json
import re
import socket
from pathlib import Path
from subprocess import check_output, Popen, PIPE

import pandas as pd
import requests
from lxml import etree

# sudo vim /etc/systemd/system/tv-tcpdump.service
# sudo tcpdump -i eth1 'src host 192.168.1.236 and tcp[13] & 8 != 0 and tcp[13] & 16 != 0' -U  -w /var/services/homes/borza/tv-capture.pcap


NAS_ADDR = "home-nas-alpha"
NAS_IP = socket.gethostbyname(NAS_ADDR)
CONTENT_URL = f"http://{NAS_IP}:50001/ContentDirectory/control"

NS = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "u": "urn:schemas-upnp-org:service:ContentDirectory:1",
    "didl": "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "upnp": "urn:schemas-upnp-org:metadata-1-0/upnp/",
}

SOAP_TEMPLATE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <ObjectID>{oid}</ObjectID>
      <BrowseFlag>BrowseChildren</BrowseFlag>
      <Filter>*</Filter>
      <StartingIndex>0</StartingIndex>
      <RequestedCount>5000</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Browse>
  </s:Body>
</s:Envelope>
"""


ifile = "/volume2/homes/borza/tv-capture.pcap"
ifile = "/var/services/homes/borza/tv-capture.pcap"


session = requests.Session()
session.headers.update(
    {
        "Connection": "close",
    }
)


def getd(oid):
    soap_body = SOAP_TEMPLATE.format(oid=oid)

    resp = session.post(
        CONTENT_URL,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
        },
        data=soap_body.encode("utf-8"),
        timeout=10,
    )
    resp.raise_for_status()
    root = etree.fromstring(resp.content)

    result_nodes = root.xpath(
        '//*[local-name()="BrowseResponse"]/*[local-name()="Result"]/text()'
    )

    if not result_nodes:
        return {"container": [], "item": []}

    didl_root = etree.fromstring(result_nodes[0].encode())

    containers = []
    items = []

    # Extract containers
    for c in didl_root.xpath('//*[local-name()="container"]'):
        containers.append(
            {
                "@id": c.get("id"),
                "dc:title": (
                    c.xpath('*[local-name()="title"]/text()')[0]
                    if c.xpath('*[local-name()="title"]/text()')
                    else ""
                ),
                "upnp:class": (
                    c.xpath('*[local-name()="class"]/text()')[0]
                    if c.xpath('*[local-name()="class"]/text()')
                    else ""
                ),
            }
        )

    # Extract items
    for i in didl_root.xpath('//*[local-name()="item"]'):
        title = i.xpath('*[local-name()="title"]/text()')
        res = i.xpath('*[local-name()="res"]/text()')
        items.append(
            {
                "dc:title": title[0] if title else "",
                "res": {"#text": res[0] if res else ""},
            }
        )

    return {
        "container": containers,
        "item": items,
    }


def tol(ml):
    return ml if isinstance(ml, list) else [ml]


def dump_watches():
    idf = dt.date.today().isoformat()
    get_watch_history().assign(date=idf).to_csv(
        f"/mnt/data/logs/watches/{idf}.csv", index=False
    )
    check_output(["ssh", "home-nas-alpha", f"rm {ifile}"])
    check_output(["ssh", "home-nas-alpha", "sudo systemctl restart tv-tcpdump"])


def show_watches(use_cache: bool = False):
    print(get_watch_history(use_cache).to_markdown(index=False))


def build_upnp_tree():
    dirs = []
    nondirs = []

    def rec(oid):
        try:
            d = getd(oid)
        except Exception as e:
            raise e
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

    ssh = Popen(
        ["ssh", "-C", "home-nas-alpha", f"cat {ifile}"],
        stdout=PIPE,
    )

    ostr = check_output(
        ["tcpdump", "-r", "-", "-A"],
        stdin=ssh.stdout,
    ).decode()

    ssh.wait()

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


def main():
    # show_watches(True)
    dump_watches()
