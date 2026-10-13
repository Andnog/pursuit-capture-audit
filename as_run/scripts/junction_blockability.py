"""Structural blockability (A-94): how many lanes must a team occupy to close a junction?

For every (arrival edge -> junction) pair of a network, the lanes to close are all passenger lanes
of all legal continuations of the arrival edge (including a legal U-turn). A team of n pursuers can
close that junction against an evader arriving on that edge only if the count is <= n. Reported per
map as the share of arrival edges whose junction is closable by 1, 2, 3, 5 pursuers.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from train_caging_pilot import _net, _paths  # noqa: E402

MAPS = [
    "adelaide_cbd",
    "toronto_downtown",
    "washington_downtown",
    "seattle_downtown",
    "phoenix_downtown",
    "portland_downtown",
    "sapporo_grid",
    "C2_grid6x6",
    "C3_grid9x9",
]


def main() -> int:
    import sumolib

    out = {}
    for m in MAPS:
        net = _net(m)
        snet = sumolib.net.readNet(_paths()[m])
        lanes = {}
        for e in net.edges:
            lanes[e] = sum(1 for ln in snet.getEdge(e).getLanes() if ln.allows("passenger"))
        need = []
        for e in net.edges:
            succ = net.successors(e)
            if succ:
                need.append(sum(lanes[s] for s in succ))
        n = len(need)
        out[m] = {
            "arrival_edges": n,
            "median_lanes_to_close": sorted(need)[n // 2],
            **{f"closable_by_{k}": round(sum(x <= k for x in need) / n, 3) for k in (1, 2, 3, 5)},
        }
        print(m, out[m], flush=True)
    with open(os.path.join(ROOT, "docs", "manuscript", "junction_blockability.json"), "w") as h:
        json.dump(out, h, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
