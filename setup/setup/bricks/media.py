from setup.runner import brick
from setup.util import apt_install, run_cmd

# Media playback box: mpv (vo=gpu-next) for HDR playback, cage as the kiosk
# compositor for the fullscreen browser, ALSA for HDMI bitstream passthrough.
# The HWE kernel carries the AMD colour-management pipeline the HDR path
# needs. HDR bench entry point is compositor-less mpv (--gpu-context=drm);
# gamescope is NOT in the Ubuntu archive — source-build it only if the drm
# path disappoints. Bench sequence lives in the homelab plan.
_APT_MEDIA = ["mpv", "cage", "alsa-utils", "wayland-utils"]

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
    check="command -v mpv > /dev/null && command -v cage > /dev/null",
    verify="mpv --version | head -1 && command -v cage",
)
def install_media_stack() -> None:
    apt_install(_APT_MEDIA)
