"""Build the networks of the second held-out set of cities (A-138, pre-registered).

For each city of the registered list, in order, until four are accepted:
1. download the road ways of a 2.4 km square from OpenStreetMap (Overpass API);
2. build a SUMO network with the options recorded in the headers of the existing networks;
3. accept it if it passes the usability thresholds of `audit_maps.py` and the frozen scenario
   generator places a team of seven in at least 15 of 20 scenarios for two evaders.
No controller and no simulation runs here. Data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

OUT = os.path.join(ROOT, "assets", "osm_b")
RAW = os.path.join(OUT, "raw")
SUMO_HOME = "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/sumo"
NETCONVERT = os.environ.get("NETCONVERT_BINARY", os.path.join(SUMO_HOME, "bin", "netconvert"))
TYPEMAP = os.path.join(SUMO_HOME, "data", "typemap", "osmNetconvert.typ.xml")
OVERPASS = "https://overpass-api.de/api/interpreter"
SIDE_KM = 2.4
ROAD_TYPES = (
    "primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|unclassified"
)
# Registered order: four cities, then four reserves (A-138).
CITIES = [
    ("denver_downtown", 39.7475, -104.9940),
    ("vancouver_downtown", 49.2827, -123.1207),
    ("barcelona_eixample", 41.3917, 2.1650),
    ("buenos_aires_microcentro", -34.6037, -58.3816),
    ("brisbane_cbd", -27.4698, 153.0251),
    ("kyoto_central", 35.0050, 135.7640),
    ("mexico_city_centro", 19.4326, -99.1332),
    ("lisbon_baixa", 38.7110, -9.1390),
]
NEEDED = 4
SALT, SCENARIOS, MIN_PLACED, TEAM = "PB1", 20, 15, 7
MIN_PASSENGER_EDGES, MIN_JUNCTIONS, MAX_DEAD_END_FRACTION = 100, 50, 0.40
NETCONVERT_OPTIONS = [
    "--proj.utm", "true",
    "--geometry.remove", "true",
    "--tls.discard-loaded", "true",
    "--tls.discard-simple", "true",
    "--ramps.guess", "false",
    "--keep-edges.postload", "true",
    "--remove-edges.isolated", "true",
    "--no-internal-links", "false",
    "--junctions.join", "true",
]  # fmt: skip


DOWNLOAD_ATTEMPTS = 4


class DownloadUnavailable(RuntimeError):
    """The map server did not answer. This stops the build; it never rejects a city."""


def bbox(lat, lon, side_km=SIDE_KM):
    """(south, west, north, east) of a square of `side_km` centred on (lat, lon)."""
    dlat = side_km / 2 / 110.574
    dlon = side_km / 2 / (111.320 * math.cos(math.radians(lat)))
    return (round(lat - dlat, 6), round(lon - dlon, 6), round(lat + dlat, 6), round(lon + dlon, 6))


def query(box):
    s, w, n, e = box
    return (
        "[out:xml][timeout:180];"
        f'(way["highway"~"^({ROAD_TYPES})$"]({s},{w},{n},{e}););'
        "(._;>;);out body;"
    )


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as h:
        for block in iter(lambda: h.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(city, box):
    path = os.path.join(RAW, f"{city}.osm")
    q = query(box)
    if not os.path.exists(path):
        data = urllib.parse.urlencode({"data": q}).encode()
        body, last = None, None
        for attempt in range(DOWNLOAD_ATTEMPTS):
            request = urllib.request.Request(
                OVERPASS,
                data=data,
                headers={"User-Agent": "doctoral-joint-interception/held-out-b"},
            )
            try:
                with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
                    body = response.read()
                break
            except OSError as error:  # server busy or timed out: not a property of the city
                last = error
                time.sleep(45 * (attempt + 1))
        if body is None:
            raise DownloadUnavailable(f"{city}: {type(last).__name__}: {str(last)[:120]}")
        with open(path, "wb") as h:
            h.write(body)
        time.sleep(5)  # be polite to the public endpoint
    return {
        "file": os.path.relpath(path, ROOT),
        "bytes": os.path.getsize(path),
        "sha256": sha256_of(path),
        "downloaded_utc": datetime.datetime.fromtimestamp(
            os.path.getmtime(path), datetime.UTC
        ).isoformat(),
        "endpoint": OVERPASS,
        "query": q,
    }


def build(city):
    osm, net = os.path.join(RAW, f"{city}.osm"), os.path.join(OUT, f"{city}.net.xml")
    cmd = [NETCONVERT, "--type-files", TYPEMAP, "--osm-files", osm, "-o", net, *NETCONVERT_OPTIONS]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    return {
        "file": os.path.relpath(net, ROOT),
        "returncode": done.returncode,
        "warnings": done.stderr.count("Warning"),
        "errors": [x for x in done.stderr.splitlines() if x.startswith("Error")][:5],
        "bytes": os.path.getsize(net) if os.path.exists(net) else 0,
        "sha256": sha256_of(net) if os.path.exists(net) else None,
    }


def usability(net_path):
    """The thresholds of `audit_maps.py`, computed the same way."""
    import sumolib

    net = sumolib.net.readNet(net_path)
    passenger = [e for e in net.getEdges() if e.allows("passenger")]
    dead = [e for e in passenger if not [o for o in e.getOutgoing() if o.allows("passenger")]]
    lanes = [len([ln for ln in e.getLanes() if ln.allows("passenger")]) for e in passenger]
    record = {
        "passenger_edges": len(passenger),
        "passenger_lanes": sum(lanes),
        "junctions": len(net.getNodes()),
        "dead_end_fraction": round(len(dead) / len(passenger), 6) if passenger else None,
        "multi_lane_fraction": round(sum(c > 1 for c in lanes) / len(passenger), 6)
        if passenger
        else None,
    }
    problems = []
    if record["passenger_edges"] < MIN_PASSENGER_EDGES:
        problems.append(f"only {record['passenger_edges']} passenger edges")
    if record["junctions"] < MIN_JUNCTIONS:
        problems.append(f"only {record['junctions']} junctions")
    if record["dead_end_fraction"] is None or record["dead_end_fraction"] > MAX_DEAD_END_FRACTION:
        problems.append(f"dead-end fraction {record['dead_end_fraction']}")
    return record, problems


def placement(city):
    """Scenarios (of 20) in which the frozen generator places a team of seven, per evader."""
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario
    from train_caging_pilot import _net

    net = _net(city)
    out = {}
    for level in ("AVOIDANT", "RANDOM"):
        placed = 0
        for i in range(SCENARIOS):
            try:
                sc = make_scenario(
                    net,
                    city,
                    EvaderLevel[level],
                    [f"p{k}" for k in range(1, TEAM + 1)],
                    f"{SALT}s{i}",
                )
                placed += len(sc.pursuer_starts) == TEAM
            except Exception:  # noqa: BLE001 - a scenario that cannot be built is not placed
                continue
        out[level] = placed
    return out


def main() -> int:
    os.makedirs(RAW, exist_ok=True)
    accepted, log = [], []
    for city, lat, lon in CITIES:
        if len(accepted) == NEEDED:
            break
        box = bbox(lat, lon)
        entry = {"city": city, "centre": [lat, lon], "bbox_swne": list(box)}
        try:
            entry["osm"] = download(city, box)
            entry["net"] = build(city)
            if entry["net"]["returncode"] != 0 or not entry["net"]["bytes"]:
                entry["decision"], entry["reasons"] = "rejected", ["netconvert failed"]
            else:
                entry["usability"], problems = usability(os.path.join(ROOT, entry["net"]["file"]))
                if not problems:
                    entry["placement"] = placement(city)
                    problems += [
                        f"{level}: team of seven placed in {n} of {SCENARIOS} scenarios"
                        for level, n in entry["placement"].items()
                        if n < MIN_PLACED
                    ]
                entry["decision"] = "accepted" if not problems else "rejected"
                entry["reasons"] = problems
        except DownloadUnavailable:
            raise  # a server failure must not move the list on to a reserve (A-138 note)
        except Exception as error:  # noqa: BLE001
            entry["decision"] = "rejected"
            entry["reasons"] = [f"{type(error).__name__}: {str(error)[:160]}"]
        if entry["decision"] == "accepted":
            accepted.append(city)
        else:
            net = os.path.join(OUT, f"{city}.net.xml")
            if os.path.exists(net):  # a rejected network must not be listed as a usable map
                os.replace(net, os.path.join(RAW, f"{city}.rejected.net.xml"))
        log.append(entry)
        print(
            json.dumps(
                {k: entry.get(k) for k in ("city", "decision", "reasons", "usability", "placement")}
            )
        )
    # A network that was built but is not in the accepted list must not be listed as a map.
    unused = []
    for name in sorted(os.listdir(OUT)):
        if name.endswith(".net.xml") and name[: -len(".net.xml")] not in accepted:
            os.replace(
                os.path.join(OUT, name),
                os.path.join(RAW, name.replace(".net.xml", ".unused.net.xml")),
            )
            unused.append(name[: -len(".net.xml")])
    manifest = {
        "amendment": "A-138",
        "built_but_not_used": unused,
        "licence": "Data (c) OpenStreetMap contributors, ODbL 1.0",
        "netconvert": NETCONVERT_OPTIONS,
        "typemap": "SUMO 1.21.0 data/typemap/osmNetconvert.typ.xml",
        "accepted": accepted,
        "cities": log,
    }
    with open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=1)
    print(json.dumps({"accepted": accepted}))
    return 0 if len(accepted) == NEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
