from __future__ import annotations

import getpass
import os
from pathlib import Path

from setup.runner import brick
from setup.util import (
    BIN_DIR,
    apt_install,
    clone_gh,
    dpkg_check,
    extended_env,
    fetch,
    link_bin,
    pinned_check,
    run_cmd,
    write_system_file,
)
from setup.versions import get as _v

_APT_DESKTOP = [
    "libxcb-xfixes0-dev",
    "libxkbcommon-dev",
    "libxkbcommon-x11-dev",
    "libfreetype-dev",
    "libfontconfig1-dev",
    "alsa-utils",
    "libportaudio2",
    "pulseaudio",
    "pulseaudio-utils",
    "pulseaudio-module-bluetooth",
    "xbindkeys",
    "libnotify-bin",
    "wmctrl",
    "dbus-x11",
    "xorg",
    "polybar",
    "dunst",
    "light",
    "vlc-bin",
    "vlc",
    "imagemagick",
    "bluez",
]

_ALACRITTY_TAG = _v("alacritty")
_NERD_FONT_TAG = _v("nerd-fonts")
_NERD_FONT_NAME = "UbuntuMono"
_FONTS_DIR = Path.home() / ".local/share/fonts"
# the release zip carries no version, so the installed tag is recorded beside the fonts
_NERD_FONT_MARKER = _FONTS_DIR / f"{_NERD_FONT_NAME}.nerd-font-version"


@brick(profile="screen", name="apt-desktop", check=dpkg_check(*_APT_DESKTOP))
def install_apt_desktop() -> None:
    apt_install(_APT_DESKTOP)


_GROUPS = ["video", "input", "audio", "tty"]
_GROUPS_CHECK = " && ".join(f'id -nG "$USER" | grep -qw {g}' for g in _GROUPS)


@brick(profile="screen", name="user-groups", check=_GROUPS_CHECK)
def setup_user_groups() -> None:
    for group in _GROUPS:
        run_cmd(f"sudo usermod -aG {group} {getpass.getuser()}")


@brick(profile="screen", name="leftwm", check="leftwm --version")
def install_leftwm() -> None:
    dest = clone_gh("leftwm", "leftwm", "main")
    run_cmd("cargo build --profile optimized", cwd=dest, env=extended_env())
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"install -s -Dm755 target/optimized/leftwm target/optimized/lefthk -t {BIN_DIR}",
        cwd=dest,
    )


@brick(
    profile="screen",
    name="alacritty",
    check=pinned_check("alacritty --version", _ALACRITTY_TAG),
)
def install_alacritty() -> None:
    dest = clone_gh("alacritty", "alacritty", _ALACRITTY_TAG)
    run_cmd(
        "cargo build --release --no-default-features --features=x11",
        cwd=dest,
        env=extended_env(),
    )
    link_bin(dest / "target/release/alacritty")
    run_cmd("sudo tic -xe alacritty,alacritty-direct extra/alacritty.info", cwd=dest)


@brick(
    profile="screen",
    name="nerd-fonts",
    check=f"fc-list | grep -q '{_NERD_FONT_NAME} Nerd Font' && "
    + pinned_check(f"cat {_NERD_FONT_MARKER}", _NERD_FONT_TAG),
)
def install_nerd_fonts() -> None:
    fetch(
        "https://github.com/ryanoasis/nerd-fonts/releases/download/"
        f"{_NERD_FONT_TAG}/{_NERD_FONT_NAME}.zip",
        _FONTS_DIR,
    )
    run_cmd(f"fc-cache -f {_FONTS_DIR}")
    _NERD_FONT_MARKER.write_text(_NERD_FONT_TAG + "\n")


# ~/.xinitrc is stowed; the check demands the symlink so a stray real file
# (which would shadow the committed one) reads as unconfigured.
_X11_CHECK = (
    "grep -q allowed_users=anybody /etc/X11/Xwrapper.config 2>/dev/null"
    " && test -L ~/.xinitrc"
)


@brick(profile="screen", name="x11-config", check=_X11_CHECK)
def configure_x11() -> None:
    write_system_file(Path("/etc/X11/Xwrapper.config"), "allowed_users=anybody\n")
    xresources = Path.home() / ".Xresources"
    if not xresources.exists():
        xresources.write_text("Xft.dpi: 96\n")


# $TIMEZONE comes from the host's private var layer; the check reads it at
# run time so an unset value fails rather than matching nothing.
_TZ_CHECK = 'test -n "$TIMEZONE" && timedatectl show -p Timezone --value | grep -qxF "$TIMEZONE"'


@brick(profile="screen", name="timezone", check=_TZ_CHECK)
def set_timezone() -> None:
    tz = os.environ.get("TIMEZONE")
    if not tz:
        raise SystemExit("TIMEZONE is unset (export it from ~/.local-vars)")
    run_cmd(f"sudo timedatectl set-timezone {tz}")
    run_cmd("sudo timedatectl set-ntp true")


_GRUB_CHECK = "grep -q '^GRUB_TIMEOUT=0' /etc/default/grub"


@brick(profile="screen", name="grub-quiet", check=_GRUB_CHECK)
def configure_grub() -> None:
    run_cmd(
        "sudo sed -i 's/GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=hidden/' /etc/default/grub"
    )
    run_cmd("sudo sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub")
    run_cmd("sudo update-grub")
