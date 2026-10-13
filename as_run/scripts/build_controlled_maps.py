"""Build the controlled SUMO maps C0-C8 of docs/PLAN_NATIVE_CONTROLLED_EN.md.

Deterministic: plain node/edge XML written here, compiled with SUMO's netconvert (C5 with
netgenerate). Blocks of 100 m, 13.89 m/s, two-way streets with one lane per direction unless a
map's factor says otherwise. Writes assets/controlled/<id>.net.xml and a manifest with hashes.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "controlled")
BIN = "/Library/Frameworks/Python.framework/Versions/3.10/bin"
SPEED = 13.89


def _write_plain(name, nodes, edges):
    nod = os.path.join(OUT, f"{name}.nod.xml")
    edg = os.path.join(OUT, f"{name}.edg.xml")
    with open(nod, "w", encoding="utf-8") as h:
        h.write("<nodes>\n")
        for nid, x, y, kind in nodes:
            h.write(f'  <node id="{nid}" x="{x:.2f}" y="{y:.2f}" type="{kind}"/>\n')
        h.write("</nodes>\n")
    with open(edg, "w", encoding="utf-8") as h:
        h.write("<edges>\n")
        for eid, a, b, lanes, prio in edges:
            h.write(
                f'  <edge id="{eid}" from="{a}" to="{b}" numLanes="{lanes}" speed="{SPEED}" '
                f'priority="{prio}"/>\n'
            )
        h.write("</edges>\n")
    return nod, edg


def _netconvert(name, nod, edg, turnarounds):
    out = os.path.join(OUT, f"{name}.net.xml")
    cmd = [
        os.path.join(BIN, "netconvert"),
        "-n",
        nod,
        "-e",
        edg,
        "-o",
        out,
        "--no-internal-links",
        "false",
        "--no-warnings",
        "true",
    ]
    if not turnarounds:
        cmd += ["--no-turnarounds", "true"]
    else:
        # netconvert skips turnarounds at geometry-like nodes by default; a ring is all such.
        cmd += ["--no-turnarounds.geometry", "false"]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def grid(
    name,
    nx,
    ny,
    kind="priority",
    lanes=lambda horizontal, i: 1,
    xs=None,
    ys=None,
    oneway=lambda horizontal, i: None,
    split_short=(),
):
    """nx x ny junctions. `oneway(h, i)` -> None (two-way), +1 or -1 (direction kept)."""
    xs = xs or [100.0 * i for i in range(nx)]
    ys = ys or [100.0 * j for j in range(ny)]
    nodes = [(f"n{i}_{j}", xs[i], ys[j], kind) for i in range(nx) for j in range(ny)]
    edges = []
    extra_nodes = []

    def add(a, b, eid, n_lanes, prio, pa, pb, key):
        if key in split_short:
            # split near the far end into a long and a SHORT edge, as real downtowns have
            mx = pb[0] - (pb[0] - pa[0]) * 0.1
            my = pb[1] - (pb[1] - pa[1]) * 0.1
            mid = f"m_{eid}"
            if mid not in {n[0] for n in extra_nodes}:
                extra_nodes.append((mid, mx, my, "priority"))
            edges.append((f"{eid}_a", a, mid, n_lanes, prio))
            edges.append((f"{eid}_b", mid, b, n_lanes, prio))
        else:
            edges.append((eid, a, b, n_lanes, prio))

    for j in range(ny):  # horizontal streets (major)
        for i in range(nx - 1):
            a, b = f"n{i}_{j}", f"n{i + 1}_{j}"
            pa, pb = (xs[i], ys[j]), (xs[i + 1], ys[j])
            d = oneway(True, j)
            n = lanes(True, j)
            if d in (None, 1):
                add(a, b, f"h{i}_{j}f", n, 2, pa, pb, ("h", i, j))
            if d in (None, -1):
                add(b, a, f"h{i}_{j}r", n, 2, pb, pa, ("hr", i, j))
    for i in range(nx):  # vertical streets (minor)
        for j in range(ny - 1):
            a, b = f"n{i}_{j}", f"n{i}_{j + 1}"
            pa, pb = (xs[i], ys[j]), (xs[i], ys[j + 1])
            d = oneway(False, i)
            n = lanes(False, i)
            if d in (None, 1):
                add(a, b, f"v{i}_{j}f", n, 1, pa, pb, ("v", i, j))
            if d in (None, -1):
                add(b, a, f"v{i}_{j}r", n, 1, pb, pa, ("vr", i, j))
    nod, edg = _write_plain(name, nodes + extra_nodes, edges)
    return _netconvert(name, nod, edg, turnarounds=False)


def ring(name, n=12, circumference=1200.0):
    r = circumference / (2 * math.pi)
    nodes = [
        (f"r{k}", r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), "priority")
        for k in range(n)
    ]
    edges = []
    for k in range(n):
        a, b = f"r{k}", f"r{(k + 1) % n}"
        edges.append((f"cw{k}", a, b, 1, 1))
        edges.append((f"ccw{k}", b, a, 1, 1))
    nod, edg = _write_plain(name, nodes, edges)
    # Turnarounds ON: the only way the evader can choose on a ring is to reverse.
    return _netconvert(name, nod, edg, turnarounds=True)


def spider(name):
    out = os.path.join(OUT, f"{name}.net.xml")
    subprocess.run(
        [
            os.path.join(BIN, "netgenerate"),
            "--spider",
            "--spider.arm-number",
            "6",
            "--spider.circle-number",
            "3",
            "--spider.space-radius",
            "100",
            "--default.lanenumber",
            "1",
            "--default.speed",
            str(SPEED),
            "--no-turnarounds",
            "true",
            "-o",
            out,
            "--no-warnings",
            "true",
        ],
        check=True,
        capture_output=True,
    )
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(20260927)
    irregular_x = [0.0]
    irregular_y = [0.0]
    for _ in range(5):
        irregular_x.append(irregular_x[-1] + rng.uniform(60, 140))
        irregular_y.append(irregular_y[-1] + rng.uniform(60, 140))
    short = {("h", 1, 2), ("hr", 3, 4), ("v", 2, 1), ("vr", 4, 3), ("h", 3, 0), ("v", 0, 3)}
    maps = {
        "C0_ring": lambda: ring("C0_ring"),
        "C1_grid4x4": lambda: grid("C1_grid4x4", 4, 4),
        "C2_grid6x6": lambda: grid("C2_grid6x6", 6, 6),
        "C3_grid9x9": lambda: grid("C3_grid9x9", 9, 9),
        "C4_grid10x4": lambda: grid("C4_grid10x4", 10, 4),
        "C5_spider": lambda: spider("C5_spider"),
        "C6_grid6x6_signals": lambda: grid("C6_grid6x6_signals", 6, 6, kind="traffic_light"),
        "C7_grid6x6_arterials": lambda: grid(
            "C7_grid6x6_arterials", 6, 6, lanes=lambda h, i: 2 if i % 3 == 0 else 1
        ),
        "C8_grid6x6_irregular": lambda: grid(
            "C8_grid6x6_irregular",
            6,
            6,
            xs=irregular_x,
            ys=irregular_y,
            oneway=lambda h, i: (1 if (h and i == 2) else -1 if (not h and i == 3) else None),
            split_short=short,
        ),
    }
    only = sys.argv[1:] or list(maps)
    manifest = {}
    for name in only:
        path = maps[name]()
        with open(path, "rb") as h:
            manifest[name] = {
                "path": os.path.relpath(path, ROOT),
                "sha256": hashlib.sha256(h.read()).hexdigest(),
            }
        print(name, manifest[name]["path"])
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
