"""X01 (exploratory): why model captures fail to reproduce in SUMO, and how fragile they are.

On the A-47 gate's DEVELOPMENT capture scenarios (regenerated deterministically; seeds checked
against the sealed gate results):
- TIMING MARGIN: model time from the finisher coming to rest to the evader entering the
  finisher's edge; reproduction (from the sealed gate) by margin bin;
- DRIVER IMPERFECTION: open-loop SUMO replays with Krauss sigma 0.5 (SUMO's default) under three
  SUMO seeds; share of model captures still reproduced (same finisher, +-5 s).
Exploratory: no threshold, no gate. Nothing in the sealed gate package is modified.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import CaptureParameters, load_domain  # noqa: E402
from joint_interception.evaluation.capture_judge import judge_capture  # noqa: E402
from joint_interception.opportunities.types import Verdict  # noqa: E402
from joint_interception.validation.diagnostic_set import generate  # noqa: E402
from joint_interception.validation.sumo_replay import replay  # noqa: E402
from joint_interception.world.network import GraphNetwork  # noqa: E402

SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
GATE = "experiments/20260926_w04_model_validation_r01"


def margin_s(run) -> float | None:
    f = run.capture["finisher"]
    rest = None
    count = 0
    for k, st in enumerate(run.states):
        if st[f][3] < 0.05:
            count += 1
            if count >= 10 and rest is None:
                rest = (k - 9) * 0.1
                edge = st[f][0]
                break
        else:
            count = 0
    if rest is None:
        return None
    for k, st in enumerate(run.states):
        if st["e1"][0] == edge and st["e1"][1] is None:
            return round(k * 0.1 - rest, 2)
    return None


def main() -> int:
    import sumolib

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    domain = load_domain()
    params = CaptureParameters.from_domain(domain)
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    with open(os.path.join(ROOT, GATE, "results.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(line) for line in h]
    captures = [r for r in rows if r["model_capture"]]
    t0 = time.process_time()
    c0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    nets = {}
    out_rows = []
    for r in captures:
        mid = r["map_id"]
        if mid not in nets:
            nets[mid] = (
                GraphNetwork.from_sumo(paths[mid]),
                sumolib.net.readNet(paths[mid], withInternal=True),
            )
        net, snet = nets[mid]
        run = generate(net, mid, r["index"], domain, domain["team"]["pursuer_ids"])
        same = (
            run is not None
            and run.scenario.seed == r["scenario_seed"]
            and run.capture == r["model_capture"]
        )
        row = {
            "map_id": mid,
            "index": r["index"],
            "regenerated_identically": same,
            "reproduced_sigma0": r["m3"][0]["reproduced"],
            "margin_s": margin_s(run) if same else None,
            "sigma05": [],
        }
        if same:
            for seed in range(1, args.seeds + 1):
                rec = replay(
                    run,
                    net,
                    snet,
                    paths[mid],
                    domain,
                    SUMO,
                    imperfection=0.5,
                    seed=seed,
                    label=f"x{mid}{r['index']}{seed}",
                )
                j = judge_capture(rec.trace, "e1", params, 0.1)
                row["sigma05"].append(
                    j.verdict is Verdict.SUPPORTED
                    and j.finisher == run.capture["finisher"]
                    and abs(j.witness_start_s - run.capture["witness_start_s"]) <= 5.0
                )
        out_rows.append(row)
        print(row, flush=True)
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as h:
        for row in out_rows:
            h.write(json.dumps(row) + "\n")
    ok = [r for r in out_rows if r["regenerated_identically"]]
    bins = {"<0 s": [], "0-2 s": [], "2-5 s": [], "5-15 s": [], ">=15 s": [], "unknown": []}
    for r in ok:
        m = r["margin_s"]
        key = (
            "unknown"
            if m is None
            else "<0 s"
            if m < 0
            else "0-2 s"
            if m < 2
            else "2-5 s"
            if m < 5
            else "5-15 s"
            if m < 15
            else ">=15 s"
        )
        bins[key].append(r["reproduced_sigma0"])
    sig = [x for r in ok for x in r["sigma05"]]
    c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    summary = {
        "captures": len(captures),
        "regenerated_identically": len(ok),
        "reproduced_sigma0": sum(r["reproduced_sigma0"] for r in ok),
        "by_margin": {k: {"n": len(v), "reproduced": sum(v)} for k, v in bins.items()},
        "sigma05_replays": len(sig),
        "sigma05_reproduced": sum(sig),
        "sigma05_all_seeds_reproduced": sum(all(r["sigma05"]) for r in ok if r["sigma05"]),
        "cpu_seconds_python": round(time.process_time() - t0, 1),
        "cpu_seconds_sumo": round(c1.ru_utime + c1.ru_stime - c0.ru_utime - c0.ru_stime, 1),
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
