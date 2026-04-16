from __future__ import annotations

import argparse

import setup.steps  # noqa: F401 — registers all steps
from setup.runner import REGISTRY, run, update


def main() -> None:
    parser = argparse.ArgumentParser(prog="setup", description="Leveled system initialization")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run setup up to a given level")
    run_p.add_argument("--level", "-l", type=int, default=1, help="Max level to run (0-4, default 1)")
    run_p.add_argument("--dry-run", "-n", action="store_true", help="Show what would run without executing")
    run_p.add_argument("--step", "-s", metavar="NAME", help="Run a single named step")

    upd_p = sub.add_parser("update", help="Re-run steps ignoring idempotency checks")
    upd_p.add_argument("--step", "-s", metavar="NAME", help="Update a single named step")

    sub.add_parser("list", help="List all registered steps")

    args = parser.parse_args()

    if args.cmd == "run":
        run(level=args.level, dry_run=args.dry_run, step_name=args.step)
    elif args.cmd == "update":
        update(step_name=args.step)
    elif args.cmd == "list":
        for s in REGISTRY:
            check = f"  [check: {s.check}]" if s.check else ""
            print(f"  L{s.level}  {s.name}{check}")


if __name__ == "__main__":
    main()
