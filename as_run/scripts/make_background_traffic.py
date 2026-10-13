"""Background traffic route files (A-92), one per map, with SUMO's randomTrips.py.

Deterministic (fixed seed per map). One trip departs every `period` seconds over the 300 s horizon,
between edges at least `min_distance` m apart, routed by duarouter; written to
assets/background_traffic/<map_id>.rou.xml. Background vehicles are ordinary SUMO cars; they are
not pursuers, so they never count toward any capture or trap endpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from train_caging_pilot import _paths  # noqa: E402

SUMO_PY = "/Library/Frameworks/Python.framework/Versions/3.10"
SUMO_HOME = f"{SUMO_PY}/lib/python3.10/site-packages/sumo"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--maps", nargs="+", required=True)
    parser.add_argument("--period", type=float, default=1.0)
    parser.add_argument("--min-distance", type=float, default=300.0)
    args = parser.parse_args()
    out_dir = os.path.join(ROOT, "assets", "background_traffic")
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ, SUMO_HOME=SUMO_HOME, PATH=f"{SUMO_PY}/bin:" + os.environ["PATH"])
    manifest = {}
    for m in args.maps:
        seed = int(hashlib.sha256(f"bg{m}".encode()).hexdigest()[:8], 16)
        route = os.path.join(out_dir, f"{m}.rou.xml")
        cmd = [
            f"{SUMO_PY}/bin/python3",
            f"{SUMO_HOME}/tools/randomTrips.py",
            "-n",
            _paths()[m],
            "-o",
            os.path.join(out_dir, f"{m}.trips.xml"),
            "-r",
            route,
            "--begin",
            "0",
            "--end",
            "300",
            "--period",
            str(args.period),
            "--min-distance",
            str(args.min_distance),
            "--seed",
            str(seed),
            "--prefix",
            "bg",
            "--vehicle-class",
            "passenger",
            "--validate",
        ]
        subprocess.run(cmd, check=True, env=env, capture_output=True)
        with open(route, "rb") as h:
            data = h.read()
        manifest[m] = {
            "route_file": os.path.relpath(route, ROOT),
            "sha256": hashlib.sha256(data).hexdigest(),
            "vehicles": data.count(b"<vehicle "),
            "seed": seed,
            "period_s": args.period,
            "min_distance_m": args.min_distance,
        }
        print(m, manifest[m]["vehicles"], flush=True)
    with open(os.path.join(out_dir, "MANIFEST.json"), "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
