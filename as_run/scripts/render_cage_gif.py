"""Caging GIF, v2 (A-83): what the certificate sees, readable at a glance.

Left: a 500 m window that follows the evader. Junctions of the evader's safe region are small red
dots; gates are squares in the colour of the pursuer sent there (filled when held); a thin line
joins each pursuer to its gate; pursuers outside the window are shown as edge arrows with their
distance. Right: a zoom that always contains the evader and the nearest pursuer, bodies to scale.
Bottom: a timeline of the safe-region size over the whole episode (red-light waits in amber, the
10 s certification window in green) and a plain-language event line.

The episode is replayed in SUMO (`audit_cage_certificate.replay`); idle stretches (evader stopped
at a red light, or nobody moving) are fast-forwarded and labelled.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

BG = (14, 22, 30)
PANEL = (20, 32, 42)
ROAD = (70, 80, 92)
ROAD_ZOOM = (58, 66, 78)
LANE_LINE = (95, 105, 118)
TEXT = (235, 238, 242)
SUB = (120, 190, 240)
GOOD = (110, 220, 140)
WARN = (240, 200, 110)
BAD = (240, 110, 110)
SAFE_DOT = (200, 70, 70)
COLOURS = {
    "e1": (235, 80, 80),
    "p1": (90, 160, 235),
    "p2": (240, 200, 60),
    "p3": (70, 200, 160),
    "p4": (200, 150, 220),
    "p5": (240, 240, 240),
}
NAMES = {"e1": "EVADER", "p1": "P1", "p2": "P2", "p3": "P3", "p4": "P4", "p5": "P5"}
W, H = 1200, 800
LEFT = (12, 96, 600, 560)
RIGHT = (612, 96, 1188, 560)
TIMELINE = (12, 640, 1188, 700)
WINDOW_M = 500.0


def _font(size):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class View:
    def __init__(self, box, cx, cy, span_m):
        self.box = box
        w, h = box[2] - box[0], box[3] - box[1]
        self.scale = min(w, h) / span_m
        self.cx, self.cy = cx, cy

    def px(self, x, y):
        bx0, by0, bx1, by1 = self.box
        return (
            (bx0 + bx1) / 2 + (x - self.cx) * self.scale,
            (by0 + by1) / 2 - (y - self.cy) * self.scale,
        )

    def inside(self, x, y, pad=0):
        px, py = self.px(x, y)
        bx0, by0, bx1, by1 = self.box
        return bx0 + pad <= px <= bx1 - pad and by0 + pad <= py <= by1 - pad


def _record_at(records, t):
    best = None
    for r in records:
        if r["t"] <= t + 1e-6:
            best = r
        else:
            break
    return best


def _overlay_at(overlays, t):
    best = None
    for o in overlays or []:
        if o["t"] <= t + 1e-6:
            best = o
        else:
            break
    return best


def _red(r):
    return (
        r is not None
        and r["v_e"] <= 0.5
        and r["signal"] is not None
        and r["signal"][1] <= 30.0
        and r["signal"][2] in "rRyYu"
    )


def _blocked(r):
    return (
        r is not None
        and r["v_e"] <= 0.5
        and r["leader"] is not None
        and r["leader"][0] in NAMES
        and r["leader"][0] != "e1"
        and r["leader"][1] <= 15.0
    )


def schedule(trace, records, caged_at, persist_s):
    """Frame times: 0.5 s near the cage, 1 s normally, 5 s through idle stretches."""
    times, flags = [], []
    t_end = trace[-1].time_s
    t = trace[0].time_s
    while t <= t_end + 1e-9:
        r = _record_at(records, t)
        near = caged_at is not None and caged_at - 15.0 <= t
        idle = r is not None and (
            _red(r) or (r["v_e"] <= 0.5 and all(v <= 0.5 for v in r["pursuers"].values()))
        )
        times.append(t)
        flags.append(idle and not near)
        t += 0.5 if near else (5.0 if idle else 1.0)
    return times, flags


def event_line(r, ov, t, caged_at, persist_s, frame=None, trapped_at=None):
    if r is None:
        return "", TEXT

    def gap(vid):
        # Bumper-to-bumper distance from the trace (SUMO's leader gap excludes minGap).
        if frame is None or vid not in frame.vehicles or "e1" not in frame.vehicles:
            return r["leader"][1]
        a, b = frame.vehicles["e1"], frame.vehicles[vid]
        return max(0.0, math.dist((a.x, a.y), (b.x, b.y)) - (a.length_m + b.length_m) / 2)

    if trapped_at is not None and t >= trapped_at + 10.0 - 1e-6:
        who = r["leader"][0] if r["leader"] else None
        tail = f" behind {NAMES.get(who, who)} (gap {gap(who):.1f} m)" if who in NAMES else ""
        return f"TRAPPED: evader immobilised for 10 s{tail} - no way out", GOOD
    if caged_at is not None and t >= caged_at + persist_s - 1e-6 and not r["caged_now"]:
        return (
            f"CERTIFICATE BROKEN: the evader drove past the pursuers - it can again reach "
            f"{len(r['safe'])} junctions first",
            BAD,
        )
    if caged_at is not None and t >= caged_at + persist_s - 1e-6:
        if _blocked(r):
            who = NAMES.get(r["leader"][0], r["leader"][0])
            return (
                f"CAGE CERTIFIED - evader stopped behind {who} (gap {gap(r['leader'][0]):.1f} m), "
                "no exit left",
                GOOD,
            )
        return "CAGE CERTIFIED - every exit of the evader's area is held by a pursuer", GOOD
    if caged_at is not None and t >= caged_at - 1e-6:
        return (
            f"CAGE HOLDING {t - caged_at:4.1f} / {persist_s:.0f} s: safe region "
            f"{len(r['safe'])} junctions, gates held {len(r['held'])}/{len(r['gates'])}",
            WARN,
        )
    if _red(r):
        return f"Evader waiting at a red light ({r['signal'][1]:.0f} m ahead)", WARN
    if _blocked(r):
        who = NAMES.get(r["leader"][0], r["leader"][0])
        return f"Evader stopped behind {who} (gap {gap(r['leader'][0]):.1f} m)", WARN
    n = len(r["safe"])
    return (
        f"Evader free: it can still reach {n} junctions before any pursuer; "
        f"gates held {len(r['held'])}/{len(r['gates'])}",
        TEXT,
    )


def render(
    out, net_file, ep, records, title, subtitle, persist_s=10.0, trapped_at=None, lenient=False
):
    import sumolib

    net = sumolib.net.readNet(net_file, withInternal=True)
    coords = {n.getID(): n.getCoord() for n in net.getNodes()}
    edges = [
        (e.getShape(), e.getLaneNumber()) for e in net.getEdges() if e.getFunction() != "internal"
    ]
    lanes = [(ln.getShape(), ln.getWidth()) for e in net.getEdges() for ln in e.getLanes()]
    f_title, f_big, f_small = _font(18), _font(17), _font(13)
    trace = ep.trace
    times, fast = schedule(trace, records, ep.caged_at, persist_s)
    if lenient:  # short passes last under a second: render every 0.3 s, no fast-forward
        times = [
            trace[0].time_s + 0.3 * i
            for i in range(int((trace[-1].time_s - trace[0].time_s) / 0.3) + 1)
        ]
        fast = [False] * len(times)
    by_t = {round(f.time_s, 1): f for f in trace}
    t_end = trace[-1].time_s

    # Timeline background (whole episode).
    strip = Image.new("RGB", (TIMELINE[2] - TIMELINE[0], TIMELINE[3] - TIMELINE[1]), PANEL)
    sd = ImageDraw.Draw(strip)
    sw, sh = strip.size
    top = math.log(1 + max((len(r["safe"]) for r in records), default=1))
    for r in records:
        x = int(r["t"] / max(t_end, 1e-6) * (sw - 1))
        if _red(r):
            sd.line([(x, 0), (x, sh)], fill=(90, 72, 30))
    if ep.caged_at is not None and ep.caged_at < t_end:
        x0 = int(ep.caged_at / t_end * (sw - 1))
        x1 = int(min(t_end, ep.caged_at + persist_s) / t_end * (sw - 1))
        sd.rectangle((x0, 0, x1, sh), fill=(40, 100, 60))
        sd.rectangle((x1, 0, sw, sh), fill=(28, 60, 40))
    pts = [
        (
            int(r["t"] / max(t_end, 1e-6) * (sw - 1)),
            sh - 4 - int(math.log(1 + len(r["safe"])) / max(top, 1e-6) * (sh - 10)),
        )
        for r in records
    ]
    if len(pts) > 1:
        sd.line(pts, fill=SAFE_DOT, width=2)

    images = []
    trail: list[tuple[float, float]] = []
    for t, is_fast in zip(times, fast, strict=False):
        f = by_t.get(round(t, 1))
        if f is None or "e1" not in f.vehicles:
            continue
        r = _record_at(records, t)
        ov = _overlay_at(ep.overlays, t)
        e = f.vehicles["e1"]
        trail.append((e.x, e.y))
        trail = trail[-60:]
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((16, 10), title, fill=TEXT, font=f_title)
        d.text((16, 36), f"{subtitle}   |   t = {t:5.1f} s", fill=SUB, font=f_big)
        if is_fast:
            d.text((1000, 36), ">> fast-forward", fill=WARN, font=f_big)
        d.rectangle(LEFT, fill=PANEL)
        d.rectangle(RIGHT, fill=PANEL)
        d.text(
            (LEFT[0] + 6, LEFT[1] - 22), "AREA AROUND THE EVADER (500 m)", fill=TEXT, font=f_small
        )
        d.text(
            (RIGHT[0] + 6, RIGHT[1] - 22),
            "ZOOM: evader + nearest pursuer, to scale",
            fill=TEXT,
            font=f_small,
        )

        # Left: local map.
        lw, lh = LEFT[2] - LEFT[0], LEFT[3] - LEFT[1]
        limg = Image.new("RGB", (lw, lh), PANEL)
        ld = ImageDraw.Draw(limg)
        view = View((0, 0, lw, lh), e.x, e.y, WINDOW_M)
        for shape, n_lanes in edges:
            if not any(abs(x - e.x) < WINDOW_M and abs(y - e.y) < WINDOW_M for x, y in shape):
                continue
            ld.line([view.px(x, y) for x, y in shape], fill=ROAD, width=max(2, n_lanes * 2))
        if ov is not None:
            for n in ov["safe_nodes"]:
                if n in coords and view.inside(*coords[n], 4):
                    cx, cy = view.px(*coords[n])
                    ld.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=SAFE_DOT)
            owner = {g: vid for vid, g in ov.get("assignment", {}).items()}
            held = set(r["held"]) if r is not None else set()
            for vid, g in ov.get("assignment", {}).items():
                if vid in f.vehicles and g in coords:
                    p = f.vehicles[vid]
                    ld.line([view.px(p.x, p.y), view.px(*coords[g])], fill=COLOURS[vid], width=1)
            for n in ov["gate_nodes"]:
                if n in coords and view.inside(*coords[n], 8):
                    cx, cy = view.px(*coords[n])
                    col = COLOURS.get(owner.get(n), (200, 200, 200))
                    box = (cx - 8, cy - 8, cx + 8, cy + 8)
                    if n in held:
                        ld.rectangle(box, fill=col, outline=TEXT)
                    else:
                        ld.rectangle(box, outline=col, width=3)
        if len(trail) > 1:
            ld.line([view.px(x, y) for x, y in trail], fill=(150, 60, 60), width=2)
        for vid, v in f.vehicles.items():
            col = COLOURS.get(vid, (160, 160, 160))
            if view.inside(v.x, v.y, 10):
                x, y = view.px(v.x, v.y)
                if vid == "e1":
                    ld.polygon([(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)], fill=col)
                else:
                    ld.ellipse((x - 7, y - 7, x + 7, y + 7), fill=col, outline=BG)
                hx, hy = math.cos(v.heading_rad), math.sin(v.heading_rad)
                ld.line([(x, y), (x + hx * 16, y - hy * 16)], fill=col, width=2)
                ld.text((x + 10, y - 18), NAMES.get(vid, vid), fill=col, font=f_small)
            else:
                ang = math.atan2(v.y - e.y, v.x - e.x)
                cx, cy = lw / 2, lh / 2
                rx, ry = lw / 2 - 16, lh / 2 - 16
                k = min(rx / max(abs(math.cos(ang)), 1e-6), ry / max(abs(math.sin(ang)), 1e-6))
                x, y = cx + math.cos(ang) * k, cy - math.sin(ang) * k
                ld.ellipse((x - 5, y - 5, x + 5, y + 5), outline=col, width=2)
                dist = math.dist((v.x, v.y), (e.x, e.y))
                ld.text((x - 30, y + 6), f"{NAMES[vid]} {dist:.0f} m", fill=col, font=f_small)
        ld.line(
            [(12, lh - 14), (12 + 100 * view.scale, lh - 14)],
            fill=TEXT,
            width=3,
        )
        ld.text((12, lh - 32), "100 m", fill=TEXT, font=f_small)
        img.paste(limg, (LEFT[0], LEFT[1]))

        # Right: zoom containing the evader and the nearest pursuer.
        others = [v for k, v in f.vehicles.items() if k != "e1"]
        near = min(others, key=lambda v: math.dist((v.x, v.y), (e.x, e.y)), default=None)
        dist = math.dist((near.x, near.y), (e.x, e.y)) if near else 30.0
        span = min(260.0, max(60.0, dist * 1.3 + 30.0))
        mx, my = (
            (e.x + near.x) / 2 if near and dist < 200 else e.x,
            ((e.y + near.y) / 2 if near and dist < 200 else e.y),
        )
        zw, zh = RIGHT[2] - RIGHT[0], RIGHT[3] - RIGHT[1]
        zimg = Image.new("RGB", (zw, zh), PANEL)
        zd = ImageDraw.Draw(zimg)
        zview = View((0, 0, zw, zh), mx, my, span)
        for shape, width in lanes:
            if not any(abs(x - mx) < span and abs(y - my) < span for x, y in shape):
                continue
            p = [zview.px(x, y) for x, y in shape]
            zd.line(p, fill=ROAD_ZOOM, width=max(2, int(width * zview.scale)))
            zd.line(p, fill=LANE_LINE, width=1)
        for vid, v in f.vehicles.items():
            if abs(v.x - mx) > span or abs(v.y - my) > span:
                continue
            c, s = math.cos(v.heading_rad), math.sin(v.heading_rad)
            hl, hw = v.length_m / 2, v.width_m / 2
            poly = [
                zview.px(v.x + a * c - b * s, v.y + a * s + b * c)
                for a, b in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))
            ]
            col = COLOURS.get(vid, (160, 160, 160))
            zd.polygon(poly, fill=col, outline=(0, 0, 0))
            lx, ly = zview.px(v.x, v.y)
            zd.text(
                (lx + 10, ly - 20),
                f"{NAMES.get(vid, vid)} {v.speed_mps:.1f} m/s",
                fill=col,
                font=f_small,
            )
        bar = 10.0 if span < 120 else 50.0
        zd.line([(12, zh - 14), (12 + bar * zview.scale, zh - 14)], fill=TEXT, width=3)
        zd.text((12, zh - 32), f"{bar:.0f} m", fill=TEXT, font=f_small)
        img.paste(zimg, (RIGHT[0], RIGHT[1]))

        # Event line, timeline, speeds, legend.
        text, col = event_line(r, ov, t, ep.caged_at, persist_s, f, trapped_at)
        if lenient:
            near = min(
                (
                    (math.dist((e.x, e.y), (v.x, v.y)), k, v)
                    for k, v in f.vehicles.items()
                    if k != "e1"
                ),
                default=None,
                key=lambda x: x[0],
            )
            if near and near[0] <= 5.0:
                text = (
                    f"'CAPTURED' by the 5 m rule: {NAMES[near[1]]} {near[0]:.1f} m away at "
                    f"{near[2].speed_mps:.1f} m/s, evader {e.speed_mps:.1f} m/s - NOT a capture"
                )
                col = BAD
        d.text((16, 572), text, fill=col, font=f_big)
        d.text(
            (16, 604),
            "Safe-region size over the episode (amber = evader at a red light, "
            "green = cage held / certified):",
            fill=TEXT,
            font=f_small,
        )
        img.paste(strip, (TIMELINE[0], TIMELINE[1]))
        xt = TIMELINE[0] + int(t / t_end * (TIMELINE[2] - TIMELINE[0] - 1))
        d.line([(xt, TIMELINE[1] - 4), (xt, TIMELINE[3] + 4)], fill=TEXT, width=2)
        speeds = "   ".join(
            f"{NAMES.get(k, k)}: {v.speed_mps:4.1f} m/s"
            for k, v in sorted(f.vehicles.items(), key=lambda kv: (kv[0] != "e1", kv[0]))
        )
        d.text((16, 712), speeds, fill=TEXT, font=f_big)
        d.text(
            (16, 744),
            "Diamond = evader; circles = pursuers (P1 blue, P2 yellow, P3 green); red dots = "
            "junctions the evader reaches first; squares = exits (gates), filled when held; "
            "thin line = pursuer -> its gate",
            fill=(170, 176, 186),
            font=f_small,
        )
        images.append(img)
    images[0].save(
        out, save_all=True, append_images=images[1:], duration=110, loop=0, optimize=True
    )
    return len(images)


def main() -> int:
    import json

    from audit_cage_certificate import replay
    from train_caging_pilot import _paths

    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", default="experiments/20260930_marl_pilot_r03")
    parser.add_argument("--checkpoint", required=True, help="e.g. U_seed2_final, or cut")
    parser.add_argument("--map", required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--condition", default="hold")
    parser.add_argument("--post-cage-s", type=float, default=20.0)
    parser.add_argument("--caption", default="")
    parser.add_argument("--trap", action="store_true", help="A-84 view: stop 18 s after trapping")
    parser.add_argument("--salt", default=None, help="defaults to the pilot's evaluation salt")
    parser.add_argument("--speed", type=float, default=None, help="evader speed factor (A-90: 1.0)")
    parser.add_argument("--level", default=None, help="evader level name (A-92)")
    parser.add_argument("--params-json", default=None, help="ambush_plus parameters (A-98)")
    parser.add_argument("--mappo-package", default="experiments/20261002_mappo_r01")
    parser.add_argument("--team", type=int, default=None, help="team size (A-92)")
    parser.add_argument("--seed", type=int, default=None, help="SUMO seed (default 9500 + index)")
    parser.add_argument("--window", type=float, nargs=2, default=None, help="show [t0, t1] only")
    parser.add_argument(
        "--lenient", action="store_true", help="A-90: flag moments within 5 m (literature rule)"
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    pilot = os.path.join(ROOT, args.pilot)
    with open(os.path.join(pilot, "inputs.json"), encoding="utf-8") as h:
        salt = args.salt or json.load(h)["arguments"]["eval_salt"]
    weights = None
    kind = (
        args.checkpoint
        if args.checkpoint
        in ("cut", "individual", "random", "nearest", "pursuit", "ambush", "ambush_plus")
        else None
    )
    learner = {"params": json.loads(args.params_json)} if args.params_json else None
    if args.checkpoint.startswith("mappo_"):
        # A-103: mappo_<run> -> best checkpoint of that run in the MAPPO package (greedy).
        import pickle

        with open(os.path.join(ROOT, args.mappo_package, "state.pkl"), "rb") as h:
            run = pickle.load(h)["runs"][args.checkpoint[len("mappo_") :]]
        kind = "mappo"
        learner = {
            "params": json.loads(args.params_json),
            "head": args.checkpoint.split("_")[1],
            "weights": run["best_model"],
            "mode": "greedy",
            "seed": 0,
        }
    elif kind is None:
        with open(os.path.join(pilot, "checkpoints", f"{args.checkpoint}.pt"), "rb") as h:
            weights = h.read()
    ep, records = replay(
        args.map,
        args.index,
        9500 + args.index if args.seed is None else args.seed,
        salt,
        args.checkpoint[0],
        weights,
        args.condition,
        args.post_cage_s,
        kind=kind,
        speed=args.speed,
        level=args.level,
        team=args.team,
        learner=learner,
    )
    from run_trap_endpoint import first_immobilisation

    t_imm = first_immobilisation(records)
    if args.trap and t_imm is not None:
        end = t_imm + 18.0
        ep.trace = [f for f in ep.trace if f.time_s <= end + 1e-6]
        records = [r for r in records if r["t"] <= end + 1e-6]
    if args.window:
        t0, t1 = args.window
        ep.trace = [f for f in ep.trace if t0 - 1e-6 <= f.time_s <= t1 + 1e-6]
        records = [r for r in records if r["t"] <= t1 + 1e-6]
    if args.trap:
        verdict = (
            f"TRAPPED at t = {t_imm + 10:.0f} s" if t_imm is not None else "NOT trapped in 300 s"
        )
    else:
        verdict = (
            f"physical cage certified at t = {ep.caged_at + 10:.0f} s"
            if ep.caged_at is not None
            else "no cage in 300 s"
        )
    n = render(
        args.out,
        _paths()[args.map],
        ep,
        records,
        f"{args.map}  |  scenario {args.index}  |  {args.team or 3} pursuers vs evader "
        f"({args.level or 'AVOIDANT'}, {args.speed or 1.5}x speed)  |  {verdict}",
        f"policy: {args.checkpoint}",
        trapped_at=t_imm if args.trap else None,
        lenient=args.lenient,
    )
    print(verdict, n, "frames ->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
