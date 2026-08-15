from __future__ import annotations

import argparse
import os

import setup.bricks  # noqa: F401 — registers all bricks
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
        help="Run bricks even when their check command passes.",
    )
    run_p.add_argument("--brick", "-b", metavar="NAME")

    sub.add_parser(
        "list", help="List all registered bricks with profile, check, and verify"
    )

    ver_p = sub.add_parser("verify", help="Run verify commands for installed bricks")
    _profile_args(ver_p)
    ver_p.add_argument("--brick", "-b", metavar="NAME")

    args = parser.parse_args()

    if args.cmd == "run":
        run(
            profiles=_resolve_cli_profiles(args.profile),
            dry_run=args.dry_run,
            brick_name=args.brick,
            force=args.force,
        )
    elif args.cmd == "list":
        width = max((len(b.profile_label) for b in REGISTRY), default=4)
        for b in REGISTRY:
            check = f"  [check: {b.check}]" if b.check else ""
            vfy = f"  [verify: {b.verify}]" if b.verify else ""
            print(f"  [{b.profile_label:>{width}}]  {b.name}{check}{vfy}")
    elif args.cmd == "verify":
        ok = verify(profiles=_resolve_cli_profiles(args.profile), brick_name=args.brick)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
