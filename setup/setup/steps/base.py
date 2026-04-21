from __future__ import annotations

from setup.runner import step
from setup.util import apt_install, append_to_profile, run_cmd

_APT_BASE = [
    "file",
    "build-essential",
    "pkg-config",
    "cmake",
    "autoconf",
    "libtool",
    "automake",
    "bison",
    "libevent-dev",
    "libssl-dev",
    "libncurses-dev",
    "libreadline-dev",
    "ncurses-dev",
    "ninja-build",
    "gnupg-utils",
    "unzip",
    "gettext",
    "wget",
    "net-tools",
    "nfs-common",
    "git",
    "make",
    "stow",
    "xclip",
    "tree",
    "btop",
    "libclang-dev",
    "openssh-server",
]


@step(
    level=0,
    name="apt-base",
    check="dpkg -s build-essential 2>/dev/null | grep -q 'Status: install ok'",
    verify="dpkg -s build-essential 2>/dev/null | grep -q 'Status: install ok'",
)
def install_apt_base() -> None:
    run_cmd("sudo apt-get update")
    apt_install(_APT_BASE)


@step(level=0, name="rust", check="rustc --version", verify="rustc --version")
def install_rust() -> None:
    run_cmd("sh -c 'curl https://sh.rustup.rs -sSf | sh -s -- -y'")
    append_to_profile('. "$HOME/.cargo/env"')


@step(level=0, name="rclone", check="rclone --version", verify="rclone --version")
def install_rclone() -> None:
    run_cmd("sh -c 'sudo -v && curl https://rclone.org/install.sh | sudo bash'")
