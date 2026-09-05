from setup.runner import brick
from setup.util import apt_install, run_cmd

# Media playback box: cage as the kiosk compositor for the fullscreen browser,
# mpv for SDR playback inside it, ALSA for HDMI bitstream passthrough,
# edid-decode to read what the sink advertises. The HWE kernel carries the AMD
# colour-management pipeline the HDR path needs.
_APT_MEDIA = ["mpv", "cage", "alsa-utils", "wayland-utils", "edid-decode"]

_HWE = "linux-generic-hwe-24.04"


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
    check="command -v cage > /dev/null && command -v edid-decode > /dev/null",
    verify="mpv --version | head -1 && command -v cage && command -v edid-decode",
)
def install_media_stack() -> None:
    apt_install(_APT_MEDIA)

