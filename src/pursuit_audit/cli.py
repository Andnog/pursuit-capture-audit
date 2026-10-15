"""Command line of the library.

pursuit-audit verify      compare every sealed evidence package with its checksums
pursuit-audit recompute   recompute the headline results from the per-episode records
pursuit-audit score       score trace files under every capture endpoint
pursuit-audit studies     list the studies and how to run each one again
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .domain.trace import TraceError, load_trace
from .endpoints.scoring import score_trace
from .evidence.catalogue import load_catalogue
from .evidence.inventory import verify_snapshot
from .reporting.headline import headline_checks

_SNAPSHOT = "as_run"


def find_snapshot(start: str | None = None) -> str:
    """Return the frozen snapshot directory, looking upwards from a starting directory.

    Raises:
        SystemExit: If no snapshot is found.
    """
    directory = os.path.abspath(start or os.getcwd())
    while True:
        candidate = os.path.join(directory, _SNAPSHOT)
        if os.path.isdir(os.path.join(candidate, "experiments")):
            return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            raise SystemExit("no as_run/experiments directory found; use --snapshot")
        directory = parent


def _verify(args: argparse.Namespace) -> int:
    result = verify_snapshot(
        args.snapshot or find_snapshot(), complete=args.complete, inventory_path=args.inventory
    )
    print(f"{result.matched} sealed files present and identical")
    print(f"{result.absent} sealed files not in this copy")
    print(f"{result.damaged} packages with a file that differs from its seal")
    print(f"{result.archive_absent} companion-archive files absent (sealed and unsealed)")
    for error in result.errors:
        print(f"ERROR {error}")
    if not result.errors:
        mode = "complete" if args.complete else "public-copy (only listed omissions permitted)"
        print(f"PASS: {mode} inventory verification")
    return 1 if result.errors else 0


def _recompute(args: argparse.Namespace) -> int:
    root = os.path.join(args.snapshot or find_snapshot(), "experiments")
    checks = headline_checks(root)
    for check in checks:
        status = "same  " if check.agrees else "DIFFER"
        print(f"{status} {check.label:58s} {check.recomputed}  sealed {check.sealed}")
    different = sum(not check.agrees for check in checks)
    print(f"{len(checks) - different} of {len(checks)} recomputed values equal the sealed ones")
    return 1 if different else 0


def _score(args: argparse.Namespace) -> int:
    status = 0
    for path in args.traces:
        try:
            row = score_trace(load_trace(path), args.evader)
        except TraceError as error:
            print(f"{path}: not scored ({error})", file=sys.stderr)
            status = 1
            continue
        print(json.dumps({"trace": os.path.basename(path), **row}))
    return status


def _studies(args: argparse.Namespace) -> int:
    for study in load_catalogue():
        if args.article and not study.in_article:
            continue
        print(f"{study.package:48s} {study.amendment or '-':7s} {study.title}")
        if args.commands and study.command:
            print(f"    {study.command}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser of the command line."""
    parser = argparse.ArgumentParser(prog="pursuit-audit", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser("verify", help="compare the sealed packages with their checksums")
    verify.add_argument("--snapshot", help="path of the as_run directory")
    verify.add_argument("--complete", action="store_true", help="require every companion file too")
    verify.add_argument("--inventory", help="explicit inventory JSON; defaults to this release")
    verify.set_defaults(run=_verify)

    recompute = commands.add_parser("recompute", help="recompute the headline results")
    recompute.add_argument("--snapshot", help="path of the as_run directory")
    recompute.set_defaults(run=_recompute)

    score = commands.add_parser("score", help="score traces under every endpoint")
    score.add_argument("traces", nargs="+", help="JSON Lines trace files")
    score.add_argument("--evader", default="e1", help="identifier of the evader")
    score.set_defaults(run=_score)

    studies = commands.add_parser("studies", help="list the studies")
    studies.add_argument("--article", action="store_true", help="only those behind the article")
    studies.add_argument("--commands", action="store_true", help="show how to run each again")
    studies.set_defaults(run=_studies)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return the exit status."""
    args = build_parser().parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
