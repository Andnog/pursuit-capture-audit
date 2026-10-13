"""Command line: score trace files under every endpoint.

python -m pursuit_audit traces/*.jsonl --evader e1
"""

from __future__ import annotations

import argparse
import json
import sys

from .endpoints import CaptureParameters, score_trace
from .trace import TraceError, load_trace


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pursuit_audit", description=__doc__)
    parser.add_argument("traces", nargs="+", help="JSON Lines trace files, one episode each")
    parser.add_argument("--evader", required=True, help="identifier of the evader in the traces")
    parser.add_argument(
        "--pursuers", nargs="*", default=None, help="pursuer ids (default: all others)"
    )
    parser.add_argument("--gap", nargs=2, type=float, default=(0.3, 2.0), metavar=("MIN", "MAX"))
    parser.add_argument("--dwell", type=float, default=2.0)
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args(argv)
    params = CaptureParameters(
        gap_min_m=args.gap[0], gap_max_m=args.gap[1], dwell_s=args.dwell, speed_max_mps=args.speed
    )
    status = 0
    for path in args.traces:
        try:
            row = score_trace(load_trace(path), args.evader, args.pursuers, params)
        except TraceError as error:
            row, status = {"unresolved": str(error)}, 2
        print(json.dumps({"trace": path, **row}))
    return status


if __name__ == "__main__":
    sys.exit(main())
