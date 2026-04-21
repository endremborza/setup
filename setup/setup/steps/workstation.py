from __future__ import annotations

import os
import subprocess
from pathlib import Path

from setup.runner import step
from setup.util import apt_install, run_cmd, write_system_file, ONSET_PATH
from setup.versions import get as _v

_LOGSEQ_VERSION = _v("logseq")

_RFKILL_SERVICE = """\
[Unit]
Description=Unblock all rfkill devices on boot
Before=bluetooth.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock all

[Install]
WantedBy=multi-user.target
"""

_AUTOLOGIN_OVERRIDE = """\
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin {user} --noclear %I $TERM
"""

_NETPLAN = """\
network:
  version: 2
  renderer: NetworkManager
"""


@step(level=4, name="firefox-apt", check="dpkg -s firefox 2>/dev/null | grep -q 'Status: install ok'")
def setup_firefox_apt() -> None:
    run_cmd("sudo install -d -m 0755 /etc/apt/keyrings")
    run_cmd(
        "sh -c 'wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O-"
        " | sudo tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null'"
    )
    sources = "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main"
    write_system_file(Path("/etc/apt/sources.list.d/mozilla.list"), sources + "\n")
    write_system_file(
        Path("/etc/apt/preferences.d/mozilla"),
        "Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n",
    )
    run_cmd("sudo apt-get update")
    apt_install(["firefox"])


@step(level=4, name="logseq", check=f"test -L ~/.local/bin/Logseq")
def install_logseq() -> None:
    zip_name = f"Logseq-linux-x64-{_LOGSEQ_VERSION}.zip"
    url = f"https://github.com/logseq/logseq/releases/download/{_LOGSEQ_VERSION}/{zip_name}"
    ONSET_PATH.mkdir(parents=True, exist_ok=True)
    run_cmd(f"curl -ROL {url}", cwd=ONSET_PATH)
    dest_dir = f"Logseq-linux-x64-{_LOGSEQ_VERSION}"
    run_cmd(f"unzip -o {zip_name} -d {dest_dir}", cwd=ONSET_PATH)
    app = ONSET_PATH / dest_dir / "Logseq-linux-x64" / "Logseq"
    link = Path.home() / ".local/bin/Logseq"
    link.unlink(missing_ok=True)
    link.symlink_to(app)


@step(level=4, name="bluetooth-autoenable")
def configure_bluetooth() -> None:
    bt_conf = Path("/etc/bluetooth/main.conf")
    if bt_conf.exists():
        text = bt_conf.read_text()
        if "AutoEnable=true" not in text:
            text = text.replace("#AutoEnable=true", "AutoEnable=true")
            if "AutoEnable=true" not in text:
                text += "\nAutoEnable=true\n"
            write_system_file(bt_conf, text)
    write_system_file(Path("/etc/systemd/system/rfkill-unblock.service"), _RFKILL_SERVICE)
    subprocess.run(["sudo", "systemctl", "enable", "rfkill-unblock.service"], check=True)


@step(level=4, name="autologin")
def configure_autologin() -> None:
    user = os.environ.get("USER", os.getlogin())
    override_dir = Path("/etc/systemd/system/getty@tty1.service.d")
    subprocess.run(["sudo", "mkdir", "-p", str(override_dir)], check=True)
    write_system_file(override_dir / "override.conf", _AUTOLOGIN_OVERRIDE.format(user=user))


@step(level=4, name="network-nm")
def configure_network() -> None:
    write_system_file(Path("/etc/netplan/00-installer-config.yaml"), _NETPLAN)
    run_cmd("sudo netplan apply")
    subprocess.run(["sudo", "systemctl", "disable", "--now", "NetworkManager-wait-online.service"])
    subprocess.run(["sudo", "systemctl", "mask", "NetworkManager-wait-online.service"], check=True)
    subprocess.run(["sudo", "systemctl", "mask", "systemd-networkd.service"], check=True)
