import getpass
import os
from pathlib import Path

from setup.runner import brick
from setup.util import (
    ONSET_PATH,
    apt_install,
    download,
    pinned_check,
    run_cmd,
    write_system_file,
)
from setup.versions import get as _v
from setup.versions import number

# Input-only hardening: default-deny inbound except lo, established, icmp,
# ssh/http/https and the wireguard port. The forward chain is deliberately not
# declared here — a wg hub gets its forward policy pushed into /etc/nftables.d/
# by fleet (hypothalamus), which this file includes.
_NFTABLES_CONF = """\
#!/usr/sbin/nft -f
flush ruleset

include "/etc/nftables.d/*.conf"

table inet filter {
	chain input {
		type filter hook input priority 0; policy drop;
		iif "lo" accept
		ct state established,related accept
		ip protocol icmp accept
		meta l4proto ipv6-icmp accept
		tcp dport { 22, 80, 443 } accept
		udp dport 51820 accept
	}
}
"""

_AUTO_UPGRADES = """\
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
"""


@brick(profile="wg", name="wireguard", check="command -v wg")
def install_wireguard() -> None:
    apt_install(["wireguard"])


# Config (/etc/caddy/Caddyfile) and service state are the fleet controller's
# job — `fleet caddy` renders from its inventory and deploys on update.
#
# Upstream's own .deb, not the distro package: noble froze caddy at 2.6.2,
# which predates the `basic_auth` directive the render emits. The vendor
# package carries the same unit, `caddy` user and /etc/caddy layout, so this
# is a straight upgrade of the distro one. --force-confold keeps the rendered
# Caddyfile, a conffile in both packages (fleet rewrites it later in the same
# update anyway); the prompt it suppresses would otherwise hang the run.
_CADDY_TAG = _v("caddy")
_CADDY_VERSION = number(_CADDY_TAG)
_CADDY_BIN = "/usr/bin/caddy"


# The check reads the package: on a web-dns box `caddy` is the custom build.
@brick(
    profile="web",
    name="caddy",
    check=pinned_check("dpkg-query -W -f='${Version}' caddy", _CADDY_TAG),
)
def install_caddy() -> None:
    deb = download(
        "https://github.com/caddyserver/caddy/releases/download/"
        f"{_CADDY_TAG}/caddy_{_CADDY_VERSION}_linux_amd64.deb"
    )
    run_cmd(f"sudo apt-get install -y -o Dpkg::Options::=--force-confold {deb}")


@brick(
    profile="edge",
    name="nftables-deny",
    check="grep -q 'policy drop' /etc/nftables.conf 2>/dev/null",
    verify="systemctl is-active nftables && grep -q 'policy drop' /etc/nftables.conf",
)
def install_nftables_deny() -> None:
    apt_install(["nftables"])
    run_cmd("sudo mkdir -p /etc/nftables.d")
    write_system_file(Path("/etc/nftables.conf"), _NFTABLES_CONF)
    run_cmd("sudo nft -f /etc/nftables.conf")
    run_cmd("sudo systemctl enable --now nftables")


@brick(
    profile="edge",
    name="unattended-upgrades",
    check="test -f /etc/apt/apt.conf.d/20auto-upgrades",
    verify="dpkg -s unattended-upgrades > /dev/null "
    "&& grep -q Unattended-Upgrade /etc/apt/apt.conf.d/20auto-upgrades",
)
def install_unattended_upgrades() -> None:
    apt_install(["unattended-upgrades"])
    write_system_file(Path("/etc/apt/apt.conf.d/20auto-upgrades"), _AUTO_UPGRADES)


# Rootful engine with the user in the docker group. The daemon itself is the
# supervisor — restart policies bring fleet apps back at boot, so no unit
# wraps them. Distro packages as-is, like caddy; the OS baseline stops at the
# container boundary, and an engine already on the box (docker-ce) passes the
# check and stays. The group applies on the next login, which is when fleet's
# apps step runs.
@brick(
    profile="docker",
    name="docker",
    check='docker compose version > /dev/null 2>&1 && getent group docker | grep -qw "$USER"',
    verify="docker compose version > /dev/null && docker info > /dev/null",
)
def install_docker() -> None:
    apt_install(["docker.io", "docker-compose-v2", "docker-buildx"])
    run_cmd(f"sudo usermod -aG docker {getpass.getuser()}")


# Caddy with the deSEC DNS provider, for certificates the ACME DNS challenge
# obtains (a wildcard for vhosts no public resolver points at). The vendor
# binary carries no DNS providers, so upstream's builder image compiles the
# pinned caddy with the pinned module, which needs docker. A dpkg diversion
# moves the package's binary to caddy.default: a .deb upgrade lands there and
# never overwrites the build, and the vendor unit runs the build unchanged.
_CADDY_DESEC_TAG = _v("caddy-desec")
_DESEC_MODULE = "dns.providers.desec"


@brick(
    profile="web-dns",
    name="caddy-desec",
    check=pinned_check("caddy version", _CADDY_TAG)
    + " && "
    + pinned_check(
        f"caddy list-modules --versions | grep {_DESEC_MODULE}", _CADDY_DESEC_TAG
    ),
)
def install_caddy_desec() -> None:
    out = ONSET_PATH / "caddy-desec"
    out.mkdir(parents=True, exist_ok=True)
    build = (
        f"xcaddy build {_CADDY_TAG}"
        f" --with github.com/caddy-dns/desec@{_CADDY_DESEC_TAG} --output /out/caddy"
        f" && chown {os.getuid()}:{os.getgid()} /out/caddy"
    )
    run_cmd(
        f"docker run --rm -e XCADDY_SETCAP=0 -v {out}:/out"
        f' caddy:{_CADDY_VERSION}-builder sh -c "{build}"'
    )
    run_cmd(
        f"sudo dpkg-divert --local --rename --divert {_CADDY_BIN}.default"
        f" --add {_CADDY_BIN}"
    )
    run_cmd(f"sudo install -m 755 {out / 'caddy'} {_CADDY_BIN}")
    run_cmd("sudo systemctl try-restart caddy")
