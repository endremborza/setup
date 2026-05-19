from __future__ import annotations

import argparse
import os

import setup.steps  # noqa: F401 — registers all steps
from setup.runner import BASE_PROFILE, REGISTRY, run, verify


def _env_profiles() -> list[str]:
    raw = os.environ.get("SETUP_PROFILES", "")
    return [p for p in raw.split() if p and p != BASE_PROFILE]


def _profile_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--profile",
        "-p",
        action="append",
        default=None,
        metavar="NAME",
        help=f"Profile(s) to include; `{BASE_PROFILE}` always implicit. "
        f"Repeat for multiple. Defaults to $SETUP_PROFILES.",
    )


def _resolve_cli_profiles(arg: list[str] | None) -> list[str]:
    return arg if arg is not None else _env_profiles()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="setup", description="Profile-based system initialization"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run setup for the given profile(s)")
    _profile_args(run_p)
    run_p.add_argument("--dry-run", "-n", action="store_true")
    run_p.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Run steps even when their check command passes.",
    )
    run_p.add_argument("--step", "-s", metavar="NAME")

    sub.add_parser(
        "list", help="List all registered steps with profile, check, and verify"
    )

    ver_p = sub.add_parser("verify", help="Run verify commands for installed steps")
    _profile_args(ver_p)
    ver_p.add_argument("--step", "-s", metavar="NAME")

    args = parser.parse_args()

    if args.cmd == "run":
        run(
            profiles=_resolve_cli_profiles(args.profile),
            dry_run=args.dry_run,
            step_name=args.step,
            force=args.force,
        )
    elif args.cmd == "list":
        width = max((len(s.profile) for s in REGISTRY), default=4)
        for s in REGISTRY:
            check = f"  [check: {s.check}]" if s.check else ""
            vfy = f"  [verify: {s.verify}]" if s.verify else ""
            print(f"  [{s.profile:>{width}}]  {s.name}{check}{vfy}")
    elif args.cmd == "verify":
        ok = verify(profiles=_resolve_cli_profiles(args.profile), step_name=args.step)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
