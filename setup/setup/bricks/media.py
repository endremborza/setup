import subprocess

from setup.runner import brick
from setup.util import apt_install, run_cmd

# Media playback box: cage as the kiosk compositor for the fullscreen browser
# (XWayland inside it carries Steam), mpv for SDR playback, libmpv for the
# Jellyfin shim, ALSA for HDMI bitstream passthrough, edid-decode to read what
# the sink advertises. The HWE kernel carries the AMD colour-management
# pipeline the HDR path needs.
_APT_MEDIA = ["mpv", "libmpv2", "cage", "alsa-utils", "edid-decode"]

_HWE = "linux-generic-hwe-24.04"
_SHIM = "jellyfin-mpv-shim"
_STEAM = "steam-installer"
# Steam's licence prompt, answered ahead so the install is unattended
_STEAM_DEBCONF = 'steam steam/question select I AGREE\nsteam steam/license note ""\n'


@brick(
    profile="media",
    name="hwe-kernel",
    check=f"dpkg -s {_HWE} 2>/dev/null | grep -q 'Status: install ok'",
    verify=f"dpkg -s {_HWE} 2>/dev/null | grep -q 'Status: install ok'",
)
def install_hwe_kernel() -> None:
    run_cmd("sudo apt-get update")
    apt_install([_HWE])


@brick(
    profile="media",
    name="media-stack",
    check="command -v cage > /dev/null && command -v edid-decode > /dev/null"
    " && dpkg -s libmpv2 2>/dev/null | grep -q 'Status: install ok'",
    verify="mpv --version | head -1 && command -v cage && command -v edid-decode",
)
def install_media_stack() -> None:
    apt_install(_APT_MEDIA)


# The shim is a uv tool loading the system libmpv, so the stowed mpv.conf
# (ALSA bitstream path) governs what it plays; tv-session starts it when present.
@brick(
    profile="media",
    name="jellyfin-shim",
    check=f"test -x ~/.local/bin/{_SHIM}",
    verify=f"test -x ~/.local/bin/{_SHIM}",
)
def install_jellyfin_shim() -> None:
    run_cmd(f"uv tool install {_SHIM}")


# Steam's runtime is 32-bit: the i386 foreign architecture must exist before
# multiverse's installer package resolves.
@brick(
    profile="media",
    name="steam",
    check=f"dpkg -s {_STEAM} 2>/dev/null | grep -q 'Status: install ok'",
    verify="command -v steam > /dev/null",
)
def install_steam() -> None:
    run_cmd("sudo dpkg --add-architecture i386")
    run_cmd("sudo apt-get update")
    subprocess.run(
        ["sudo", "debconf-set-selections"], input=_STEAM_DEBCONF, text=True, check=True
    )
    apt_install([_STEAM])
