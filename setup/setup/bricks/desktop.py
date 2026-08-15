from __future__ import annotations

import os
from pathlib import Path

from setup.runner import brick
from setup.util import apt_install, clone_gh, run_cmd, write_system_file, extended_env
from setup.versions import get as _v

_APT_DESKTOP = [
    "libxcb-xfixes0-dev",
    "libxkbcommon-dev",
    "libxkbcommon-x11-dev",
    "libfreetype6-dev",
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
_NERD_FONT_VERSION = _v("nerd-fonts")
_NERD_FONT_NAME = "UbuntuMono"


@brick(
    profile="screen",
    name="apt-desktop",
    check="dpkg -s xorg 2>/dev/null | grep -q 'Status: install ok'",
)
def install_apt_desktop() -> None:
    apt_install(_APT_DESKTOP)


_GROUPS = ["video", "input", "audio", "tty"]
_GROUPS_CHECK = " && ".join(f'id -nG "$USER" | grep -qw {g}' for g in _GROUPS)


@brick(profile="screen", name="user-groups", check=_GROUPS_CHECK, verify=_GROUPS_CHECK)
def setup_user_groups() -> None:
    user = os.environ.get("USER", os.getlogin())
    for group in _GROUPS:
        run_cmd(f"sudo usermod -aG {group} {user}")


@brick(profile="screen", name="leftwm", check="leftwm --version")
def install_leftwm() -> None:
    dest = clone_gh("leftwm", "leftwm", "main")
    run_cmd("cargo build --profile optimized", cwd=dest, env=extended_env())
    bin_dir = Path.home() / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"install -s -Dm755 target/optimized/leftwm target/optimized/lefthk -t {bin_dir}",
        cwd=dest,
    )


@brick(profile="screen", name="alacritty", check="alacritty --version")
def install_alacritty() -> None:
    dest = clone_gh("alacritty", "alacritty", _ALACRITTY_TAG)
    run_cmd(
        "cargo build --release --no-default-features --features=x11",
        cwd=dest,
        env=extended_env(),
    )
    link = Path.home() / ".local/bin/alacritty"
    link.unlink(missing_ok=True)
    link.symlink_to(dest / "target/release/alacritty")
    run_cmd("sudo tic -xe alacritty,alacritty-direct extra/alacritty.info", cwd=dest)


@brick(
    profile="screen", name="nerd-fonts", check=f"fc-list | grep -qi {_NERD_FONT_NAME}"
)
def install_nerd_fonts() -> None:
    fonts_dir = Path.home() / ".local/share/fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{_NERD_FONT_NAME}.zip"
    url = f"https://github.com/ryanoasis/nerd-fonts/releases/download/{_NERD_FONT_VERSION}/{zip_name}"
    run_cmd(f"curl -OL {url}", cwd=fonts_dir)
    run_cmd(f"unzip -o {zip_name}", cwd=fonts_dir)
    (fonts_dir / zip_name).unlink(missing_ok=True)


_X11_CHECK = (
    "grep -q allowed_users=anybody /etc/X11/Xwrapper.config 2>/dev/null"
    " && test -e ~/.xinitrc"
)


@brick(profile="screen", name="x11-config", check=_X11_CHECK, verify=_X11_CHECK)
def configure_x11() -> None:
    write_system_file(Path("/etc/X11/Xwrapper.config"), "allowed_users=anybody\n")
    xresources = Path.home() / ".Xresources"
    if not xresources.exists():
        xresources.write_text("Xft.dpi: 96\n")
    # never overwrite: ~/.xinitrc is normally a stow symlink into the repo —
    # writing through it clobbers the committed dotfile
    xinitrc = Path.home() / ".xinitrc"
    if not xinitrc.exists():
        xinitrc.write_text(
            "xrdb -merge ~/.Xresources\nsetxkbmap us\nexec dbus-launch ~/.local/bin/leftwm\n"
        )
    profile = Path.home() / ".profile"
    text = profile.read_text() if profile.exists() else ""
    if "startx" not in text:
        block = (
            '\nif [ -z "$NO_STARTX" ] && [ -z "$DISPLAY" ]'
            ' && [ "$(tty)" = "/dev/tty1" ]; then\n    startx\nfi\n'
        )
        profile.write_text(text + block)


_TZ_CHECK = "timedatectl show -p Timezone --value | grep -q Europe/Budapest"


@brick(profile="screen", name="timezone", check=_TZ_CHECK, verify=_TZ_CHECK)
def set_timezone() -> None:
    run_cmd("sudo timedatectl set-timezone Europe/Budapest")
    run_cmd("sudo timedatectl set-ntp true")


_GRUB_CHECK = "grep -q '^GRUB_TIMEOUT=0' /etc/default/grub"


@brick(profile="screen", name="grub-quiet", check=_GRUB_CHECK, verify=_GRUB_CHECK)
def configure_grub() -> None:
    run_cmd(
        "sudo sed -i 's/GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=hidden/' /etc/default/grub"
    )
    run_cmd("sudo sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub")
    run_cmd("sudo update-grub")
