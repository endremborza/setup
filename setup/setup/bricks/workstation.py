from __future__ import annotations

import os
import subprocess
from pathlib import Path

from setup.runner import brick
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

# Block Ubuntu's snap-shim transitional firefox (1:1snap1-0ubuntuN). Its epoch
# (1:) outranks any Mozilla version, so unattended-upgrades silently swaps real
# firefox for the snap shim. Priority -1 makes it uninstallable, leaving
# Mozilla's apt build as the only candidate.
_FIREFOX_NEGATIVE_PIN = """\
Package: firefox*
Pin: release o=Ubuntu
Pin-Priority: -1
"""

# Mozilla version starts "DDD.D..." (e.g. 150.0.3~build1). The snap shim starts
# with an epoch ("1:1snap1-..."), so an unanchored "starts with digits-dot" check
# distinguishes them.
_FIREFOX_CHECK = (
    r"dpkg-query -W -f='${Version}' firefox 2>/dev/null | grep -qE '^[0-9]+\.[0-9]+'"
)


@brick(profile=("screen-apps", "media"), name="firefox-apt", check=_FIREFOX_CHECK)
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
    write_system_file(
        Path("/etc/apt/preferences.d/no-firefox-from-ubuntu"), _FIREFOX_NEGATIVE_PIN
    )
    subprocess.run(["sudo", "snap", "remove", "--purge", "firefox"], check=False)
    installed = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", "firefox"], capture_output=True, text=True
    ).stdout
    if "snap" in installed:
        subprocess.run(["sudo", "apt-get", "purge", "-y", "firefox"], check=True)
    run_cmd("sudo apt-get update")
    apt_install(["firefox"])


@brick(profile="screen-apps", name="logseq", check=f"test -L ~/.local/bin/Logseq")
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


_BT_CHECK = (
    "grep -q '^AutoEnable=true' /etc/bluetooth/main.conf"
    " && systemctl is-enabled -q rfkill-unblock.service"
)


@brick(profile="screen-apps", name="bluetooth-autoenable", check=_BT_CHECK, verify=_BT_CHECK)
def configure_bluetooth() -> None:
    bt_conf = Path("/etc/bluetooth/main.conf")
    if bt_conf.exists():
        text = bt_conf.read_text()
        if "AutoEnable=true" not in text:
            text = text.replace("#AutoEnable=true", "AutoEnable=true")
            if "AutoEnable=true" not in text:
                text += "\nAutoEnable=true\n"
            write_system_file(bt_conf, text)
    write_system_file(
        Path("/etc/systemd/system/rfkill-unblock.service"), _RFKILL_SERVICE
    )
    subprocess.run(
        ["sudo", "systemctl", "enable", "rfkill-unblock.service"], check=True
    )


_AUTOLOGIN_CHECK = (
    "grep -q autologin /etc/systemd/system/getty@tty1.service.d/override.conf"
    " 2>/dev/null"
)


@brick(
    profile="screen-apps",
    name="autologin",
    check=_AUTOLOGIN_CHECK,
    verify=_AUTOLOGIN_CHECK,
)
def configure_autologin() -> None:
    user = os.environ.get("USER", os.getlogin())
    override_dir = Path("/etc/systemd/system/getty@tty1.service.d")
    subprocess.run(["sudo", "mkdir", "-p", str(override_dir)], check=True)
    write_system_file(
        override_dir / "override.conf", _AUTOLOGIN_OVERRIDE.format(user=user)
    )


# wait-online prints "masked" on stderr with exit 1; NetworkManager itself
# must be enabled. Netplan files must be root-only (0600) or netplan warns.
_NM_CHECK = (
    "systemctl is-enabled -q NetworkManager"
    " && systemctl is-enabled NetworkManager-wait-online.service 2>&1"
    " | grep -q masked"
)


@brick(profile="screen-apps", name="network-nm", check=_NM_CHECK, verify=_NM_CHECK)
def configure_network() -> None:
    write_system_file(
        Path("/etc/netplan/00-installer-config.yaml"), _NETPLAN, mode="600"
    )
    run_cmd("sudo netplan apply")
    subprocess.run(
        ["sudo", "systemctl", "disable", "--now", "NetworkManager-wait-online.service"]
    )
    subprocess.run(
        ["sudo", "systemctl", "mask", "NetworkManager-wait-online.service"], check=True
    )
    subprocess.run(
        ["sudo", "systemctl", "mask", "systemd-networkd.service"], check=True
    )
