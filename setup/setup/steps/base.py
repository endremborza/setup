import os
from pathlib import Path

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
    "libgraphite2-3",
    "openssh-server",
]

_SYNC_ROOT = Path(os.environ.get("SYNC_ROOT", str(Path.home() / "synced")))
_DIENCEPHALON = Path(
    os.environ.get("DIEN_ROOT", str(_SYNC_ROOT / "composites/pkm/diencephalon"))
)


@step(
    profile="base",
    name="apt-base",
    check="dpkg -s build-essential 2>/dev/null | grep -q 'Status: install ok'",
    verify="dpkg -s build-essential 2>/dev/null | grep -q 'Status: install ok'",
)
def install_apt_base() -> None:
    run_cmd("sudo apt-get update")
    apt_install(_APT_BASE)


# Registered between apt-base and rust so that dotfiles/.profile is a stow symlink
# before append_to_profile runs (which would otherwise create a conflicting real file).
@step(
    profile="base",
    name="restow",
    check="test -f ~/.config/environment.d/10-vars.conf",
    verify="test -f ~/.config/environment.d/10-vars.conf",
)
def run_restow() -> None:
    run_cmd(f"bash {_DIENCEPHALON}/dotfiles/.local/bin/restow")


@step(profile="base", name="rust", check="rustc --version", verify="rustc --version")
def install_rust() -> None:
    run_cmd("sh -c 'curl https://sh.rustup.rs -sSf | sh -s -- -y'")
    append_to_profile('. "$HOME/.cargo/env"')


@step(
    profile="base", name="rclone", check="rclone --version", verify="rclone --version"
)
def install_rclone() -> None:
    run_cmd("sh -c 'sudo -v && curl https://rclone.org/install.sh | sudo bash'")
