"""Preview or apply pinned tool version installs."""

import argparse
import subprocess

from setup.versions import dump, load, bump

from .registry import TOOLS


def _check_passes(cmd: str) -> bool:
    return subprocess.run(cmd, shell=True, capture_output=True).returncode == 0


def cmd_dry_run() -> None:
    versions = load()
    print(f"{'Tool':<14} {'Installed':<18} {'Pinned':<18} {'Action'}")
    print("-" * 66)
    for tv in versions.values():
        entry = TOOLS.get(tv.name)
        installed = tv.installed or "—"
        if entry is None:
            action = "no_installer"
        elif tv.installed == tv.tag:
            action = "up-to-date"
        elif not tv.installed:
            if entry.check and _check_passes(entry.check):
                action = "mark-installed"
            else:
                action = "install"
        else:
            action = f"upgrade"
        print(f"{tv.name:<14} {installed:<18} {tv.tag:<18} {action}")


def cmd_live() -> None:
    versions = load()
    for tv in versions.values():
        entry = TOOLS.get(tv.name)
        if entry is None:
            print(f"[ -- ] {tv.name}: no installer")
            continue

        if not tv.installed and entry.check:
            if _check_passes(entry.check):
                print(f"[init] {tv.name}: marking installed at {tv.tag}")
                versions[tv.name].installed = tv.tag
                dump(versions)
                continue

        if tv.tag == tv.installed:
            print(f"[skip] {tv.name}")
            continue

        fn = entry.upgrade_fn or entry.install_fn
        print(f"[ >> ] {tv.name}: {tv.installed or 'uninstalled'} → {tv.tag}")
        try:
            fn()
            versions[tv.name].installed = tv.tag
            dump(versions)
            print(f"[ ok ] {tv.name}")
        except Exception as e:
            print(f"[FAIL] {tv.name}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="dienpy versions upgrade-system")
    parser.add_argument(
        "--live",
        action="store_true",
        help="install tools whose pinned version differs from installed",
    )
    args = parser.parse_args()

    if args.live:
        cmd_live()
    else:
        cmd_dry_run()


def get_completions(args: list[str]) -> list[str]:
    return [] if args else ["--live"]
