from __future__ import annotations

import os
from pathlib import Path

from setup.runner import step
from setup.util import apt_install, clone_gh, run_cmd, write_system_file, extended_env

_APT_DESKTOP = [
    "libxcb-xfixes0-dev",
    "libxkbcommon-dev",
    "libxkbcommon-x11-dev",
    "libfreetype6-dev",
    "libfontconfig1-dev",
    "alsa-utils",
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

_ALACRITTY_TAG = "v0.13.2"
_NERD_FONT_VERSION = "v3.2.1"
_NERD_FONT_NAME = "UbuntuMono"


@step(
    level=3,
    name="apt-desktop",
    check="dpkg -s xorg 2>/dev/null | grep -q 'Status: install ok'",
)
def install_apt_desktop() -> None:
    apt_install(_APT_DESKTOP)


@step(level=3, name="user-groups")
def setup_user_groups() -> None:
    user = os.environ.get("USER", os.getlogin())
    for group in ["video", "input", "audio", "tty"]:
        run_cmd(f"sudo usermod -aG {group} {user}")


@step(level=3, name="leftwm", check="leftwm --version")
def install_leftwm() -> None:
    dest = clone_gh("leftwm", "leftwm", "main")
    run_cmd("cargo build --profile optimized", cwd=dest, env=extended_env())
    bin_dir = Path.home() / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"install -s -Dm755 target/optimized/leftwm target/optimized/lefthk -t {bin_dir}",
        cwd=dest,
    )


@step(level=3, name="alacritty", check="alacritty --version")
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


@step(level=3, name="nerd-fonts", check=f"fc-list | grep -qi {_NERD_FONT_NAME}")
def install_nerd_fonts() -> None:
    fonts_dir = Path.home() / ".local/share/fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{_NERD_FONT_NAME}.zip"
    url = f"https://github.com/ryanoasis/nerd-fonts/releases/download/{_NERD_FONT_VERSION}/{zip_name}"
    run_cmd(f"curl -OL {url}", cwd=fonts_dir)
    run_cmd(f"unzip -o {zip_name}", cwd=fonts_dir)
    (fonts_dir / zip_name).unlink(missing_ok=True)


@step(level=3, name="x11-config")
def configure_x11() -> None:
    write_system_file(Path("/etc/X11/Xwrapper.config"), "allowed_users=anybody\n")
    xresources = Path.home() / ".Xresources"
    if not xresources.exists():
        xresources.write_text("Xft.dpi: 96\n")
    xinitrc = Path.home() / ".xinitrc"
    xinitrc.write_text(
        "xrdb -merge ~/.Xresources\nsetxkbmap us\nexec dbus-launch ~/.local/bin/leftwm\n"
    )
    profile = Path.home() / ".profile"
    text = profile.read_text() if profile.exists() else ""
    if "startx" not in text:
        block = '\nif [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then\n    startx\nfi\n'
        profile.write_text(text + block)


@step(level=3, name="timezone")
def set_timezone() -> None:
    run_cmd("sudo timedatectl set-timezone Europe/Budapest")
    run_cmd("sudo timedatectl set-ntp true")


@step(level=3, name="grub-quiet")
def configure_grub() -> None:
    run_cmd(
        "sudo sed -i 's/GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=hidden/' /etc/default/grub"
    )
    run_cmd("sudo sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub")
    run_cmd("sudo update-grub")
