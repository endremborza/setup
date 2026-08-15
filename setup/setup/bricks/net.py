from pathlib import Path

from setup.runner import brick
from setup.util import apt_install, run_cmd, write_system_file

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


@brick(
    profile="wg",
    name="wireguard",
    check="command -v wg",
    verify="command -v wg",
)
def install_wireguard() -> None:
    apt_install(["wireguard"])


# Config (/etc/caddy/Caddyfile) and service state are the fleet controller's
# job — `fleet caddy` renders from its inventory and deploys on update. The
# distro package is deliberately used as-is (auto-HTTPS needs no plugins).
@brick(
    profile="web",
    name="caddy",
    check="dpkg -s caddy 2>/dev/null | grep -q 'Status: install ok'",
    verify="command -v caddy",
)
def install_caddy() -> None:
    apt_install(["caddy"])


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
