import shutil
from pathlib import Path

from setup.runner import brick
from setup.util import (
    apt_install,
    dpkg_check,
    extended_env,
    pinned_check,
    run_cmd,
    run_shell,
)
from setup.versions import get as _v

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
    "rsync",
    "xclip",
    "tree",
    "btop",
    "libclang-dev",
    "libgraphite2-3",
    "libxml2-utils",
    "openssh-server",
]

_DIENCEPHALON = Path(__file__).resolve().parents[3]
_RUST_TAG = _v("rust")


@brick(profile="base", name="apt-base", check=dpkg_check(*_APT_BASE))
def install_apt_base() -> None:
    run_cmd("sudo apt-get update")
    apt_install(_APT_BASE)


@brick(
    profile="base",
    name="restow",
    check="test -f ~/.config/environment.d/10-vars.conf",
)
def run_restow() -> None:
    run_cmd(f"bash {_DIENCEPHALON}/dotfiles/.local/bin/restow")


@brick(profile="base", name="rust", check=pinned_check("rustc --version", _RUST_TAG))
def install_rust() -> None:
    if shutil.which("rustup", path=extended_env()["PATH"]):
        run_cmd(f"rustup toolchain install {_RUST_TAG}")
        run_cmd(f"rustup default {_RUST_TAG}")
    else:
        run_shell(
            "curl -fsSL https://sh.rustup.rs"
            f" | sh -s -- -y --default-toolchain {_RUST_TAG}"
        )


@brick(profile="base", name="rclone", check="rclone --version")
def install_rclone() -> None:
    run_shell("curl -fsSL https://rclone.org/install.sh | sudo bash")
