#!/usr/bin/env python3
"""Audit the legacy OSM map assets: which ones actually work.

Read-only. Parses each network with `sumolib` and reports what it finds. **No SUMO process
is started and no episode is run** — reading a network file is not a simulation.

Why this exists: the historical archive contains 32 probed extracts, of which 12 were
retained with a manifest. "Retained in a manifest" is not the same as "usable", and the
project needs to know which is which before any dataset decision. The output is written to
the project root so the answer is available without re-deriving it.

The maps themselves are **legacy assets**. They are read, hashed and assessed here; they are
not copied into this project, and adopting any of them later requires a provenance entry
under the fresh-start policy.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys

LEGACY_MANIFEST = (
    "/Users/andrei/Documents/PHD/Union/urban_dynamic_containment/assets/osm/manifest.json"
)
LEGACY_ROOT = "/Users/andrei/Documents/PHD/Union/urban_dynamic_containment"

# Thresholds for usability, fixed here rather than tuned per map.
MIN_PASSENGER_EDGES = 100
MIN_JUNCTIONS = 50
MAX_DEAD_END_FRACTION = 0.40


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def assess(map_entry: dict) -> dict:
    """Assess one map. Every failure mode is named, never collapsed into a boolean."""
    import sumolib

    path = os.path.join(LEGACY_ROOT, map_entry["relative_path"])
    record: dict = {
        "map_id": map_entry["map_id"],
        "declared_split": map_entry["split"],
        "path": path,
        "problems": [],
    }

    if not os.path.isfile(path):
        record["status"] = "MISSING"
        record["problems"].append("file not found")
        return record

    record["bytes"] = os.path.getsize(path)
    actual = sha256_of(path)
    record["sha256"] = actual
    record["sha256_matches_manifest"] = actual == map_entry["sha256"]
    if not record["sha256_matches_manifest"]:
        record["problems"].append("sha256 differs from the manifest")

    try:
        net = sumolib.net.readNet(path)
    except Exception as exc:  # noqa: BLE001
        record["status"] = "UNPARSABLE"
        record["problems"].append(f"sumolib could not read the network: {exc}")
        return record

    edges = net.getEdges()
    passenger_edges = [e for e in edges if e.allows("passenger")]
    passenger_lanes = [ln for e in passenger_edges for ln in e.getLanes() if ln.allows("passenger")]
    junctions = net.getNodes()

    # A dead end is a passenger edge with no outgoing passenger continuation. It matters
    # here because a capture that happens in a cul-de-sac is only a COORDINATED capture if
    # the evader was forced into it, and a network full of cul-de-sacs makes that
    # distinction impossible to establish.
    dead_ends = []
    for edge in passenger_edges:
        outgoing = [e for e in edge.getOutgoing() if e.allows("passenger")]
        if not outgoing:
            dead_ends.append(edge.getID())

    lane_counts = [
        len([ln for ln in e.getLanes() if ln.allows("passenger")]) for e in passenger_edges
    ]
    multi_lane = sum(1 for c in lane_counts if c > 1)

    record.update(
        {
            "parsed_passenger_edges": len(passenger_edges),
            "parsed_passenger_lanes": len(passenger_lanes),
            "parsed_junctions": len(junctions),
            "manifest_passenger_edges": map_entry["passenger_edges"],
            "manifest_passenger_lanes": map_entry["passenger_lanes"],
            "manifest_junctions": map_entry["junctions"],
            "dead_end_edges": len(dead_ends),
            "dead_end_fraction": round(len(dead_ends) / len(passenger_edges), 6)
            if passenger_edges
            else None,
            "multi_lane_edges": multi_lane,
            "multi_lane_fraction": round(multi_lane / len(passenger_edges), 6)
            if passenger_edges
            else None,
            "max_lanes_on_an_edge": max(lane_counts) if lane_counts else 0,
            "total_passenger_length_m": round(sum(e.getLength() for e in passenger_edges), 1),
        }
    )

    if len(passenger_edges) < MIN_PASSENGER_EDGES:
        record["problems"].append(
            f"only {len(passenger_edges)} passenger edges, below {MIN_PASSENGER_EDGES}"
        )
    if len(junctions) < MIN_JUNCTIONS:
        record["problems"].append(f"only {len(junctions)} junctions, below {MIN_JUNCTIONS}")
    if record["dead_end_fraction"] and record["dead_end_fraction"] > MAX_DEAD_END_FRACTION:
        record["problems"].append(
            f"dead-end fraction {record['dead_end_fraction']} above {MAX_DEAD_END_FRACTION}"
        )

    # A count that disagrees with the manifest is reported, not silently preferred either
    # way: it means the manifest and the file describe different things.
    for field, parsed_key, manifest_key in (
        ("passenger_edges", "parsed_passenger_edges", "manifest_passenger_edges"),
        ("junctions", "parsed_junctions", "manifest_junctions"),
    ):
        if record[parsed_key] != record[manifest_key]:
            record["problems"].append(
                f"{field}: parsed {record[parsed_key]} but manifest says {record[manifest_key]}"
            )

    record["status"] = "USABLE" if not record["problems"] else "USABLE_WITH_CAVEATS"
    if not record["sha256_matches_manifest"]:
        record["status"] = "INTEGRITY_FAILURE"
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="MAPS_STATUS.json")
    args = parser.parse_args()

    if not os.path.isfile(LEGACY_MANIFEST):
        print(f"legacy manifest not found: {LEGACY_MANIFEST}", file=sys.stderr)
        return 1
    with open(LEGACY_MANIFEST, encoding="utf-8") as handle:
        manifest = json.load(handle)

    records = [assess(entry) for entry in manifest["maps"]]
    by_status: dict[str, list[str]] = {}
    for record in records:
        by_status.setdefault(record["status"], []).append(record["map_id"])

    usable = [r for r in records if r["status"] in ("USABLE", "USABLE_WITH_CAVEATS")]
    splits: dict[str, list[str]] = {}
    for record in usable:
        splits.setdefault(record["declared_split"], []).append(record["map_id"])

    out = {
        "schema_version": 1,
        "generated": datetime.date.today().isoformat(),
        "generated_by": "scripts/audit_maps.py",
        "purpose": (
            "Which legacy OSM maps actually work. Regenerate with `uv run python "
            "scripts/audit_maps.py` before any dataset decision."
        ),
        "source_manifest": LEGACY_MANIFEST,
        "source_license": manifest.get("license"),
        "access": "READ_ONLY; no map was copied, modified or executed",
        "sumo_process_started": False,
        "thresholds": {
            "min_passenger_edges": MIN_PASSENGER_EDGES,
            "min_junctions": MIN_JUNCTIONS,
            "max_dead_end_fraction": MAX_DEAD_END_FRACTION,
        },
        "totals": {
            "in_manifest": len(records),
            "usable": len(usable),
            "by_status": {k: len(v) for k, v in sorted(by_status.items())},
        },
        "usable_by_declared_split": {k: sorted(v) for k, v in sorted(splits.items())},
        "maps": records,
        "limits": [
            "Parsing a network proves it is well formed, not that an episode runs on it.",
            "The declared splits come from the LEGACY manifest. Adopting them carries the "
            "legacy exposure with them; a fresh split decision is D15.",
            "These are legacy assets. Adopting one requires a provenance entry under the "
            "fresh-start policy; none is copied by this audit.",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2)
        handle.write("\n")

    print(
        json.dumps(
            {"totals": out["totals"], "usable_by_declared_split": out["usable_by_declared_split"]},
            indent=2,
        )
    )
    for record in records:
        flag = "OK " if record["status"] == "USABLE" else "!! "
        print(f"{flag}{record['map_id']:24s} {record['status']:22s} {record.get('problems')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
