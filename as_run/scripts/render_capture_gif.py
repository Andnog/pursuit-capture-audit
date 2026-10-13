"""Render a SUMO trace as an animated GIF with two panels.

Left: the whole map, every vehicle as a coloured, labelled marker. Right: a zoom centred on the
evader with bodies and lanes to scale. Header: map, scenario, arm, time. Footer: legend, verdict
and every vehicle's speed. Frames every `step_s` over [t0, t1].
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

BG = (14, 22, 30)
PANEL = (20, 32, 42)
ROAD_FULL = (110, 118, 128)
ROAD_ZOOM = (58, 66, 78)
LANE_LINE = (95, 105, 118)
TEXT = (235, 238, 242)
SUB = (120, 190, 240)
WARN = (240, 200, 110)
COLOURS = {
    "e1": (235, 80, 80),
    "p1": (90, 160, 235),
    "p2": (240, 200, 60),
    "p3": (70, 200, 160),
    "p4": (200, 150, 220),
    "p5": (240, 240, 240),
}
NAMES = {"e1": "EVADER", "p1": "P1", "p2": "P2", "p3": "P3", "p4": "P4", "p5": "P5"}


class _View:
    def __init__(self, box, x0, y0, span, span_y=None):
        self.box, self.x0, self.y0 = box, x0, y0
        sx = (box[2] - box[0] - 20) / span
        sy = (box[3] - box[1] - 20) / (span_y if span_y else span)
        # Fit BOTH dimensions: the full map overflowed a non-square panel.
        self.scale = min(sx, sy) if span_y else sx

    def px(self, x, y):
        bx0, _, _, by1 = self.box
        return bx0 + 10 + (x - self.x0) * self.scale, by1 - 10 - (y - self.y0) * self.scale


def _scale_bar(d, view, metres, label):
    bx0, _, _, by1 = view.box
    x, y = bx0 + 20, by1 - 22
    d.line([(x, y), (x + metres * view.scale, y)], fill=TEXT, width=3)
    d.text((x, y - 16), label, fill=TEXT)


def render(
    out,
    net_file,
    frames,
    finisher,
    helper,
    t0,
    t1,
    title="",
    subtitle="",
    verdict_line="",
    zoom_radius=35.0,
    step_s=0.5,
    overlays=None,
    **_ignored,
):
    """`overlays`: list of dicts {t, safe_nodes, gate_nodes, assignment, safe} (F1 caging):
    the evader's safe region is drawn on the full map, each gate in its pursuer's colour."""
    import sumolib

    net = sumolib.net.readNet(net_file, withInternal=True)
    W, H = 1120, 660
    left = (12, 88, 548, 520)
    right = (560, 88, 1096, 520)
    xmin, ymin, xmax, ymax = net.getBoundary()
    full = _View(left, xmin - 20, ymin - 20, (xmax - xmin) + 40, (ymax - ymin) + 40)

    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)
    d.rectangle(left, fill=PANEL)
    d.rectangle(right, fill=PANEL)
    for edge in net.getEdges():
        if edge.getFunction() == "internal":
            continue
        d.line([full.px(x, y) for x, y in edge.getShape()], fill=ROAD_FULL, width=2)
    _scale_bar(d, full, 50, "50 m")
    d.text((left[0] + 8, left[1] - 22), "FULL MAP", fill=TEXT)
    d.text((right[0] + 8, right[1] - 22), "ZOOM ON EVADER: bodies to scale", fill=TEXT)

    lanes = [
        (lane, edge.getFunction() == "internal")
        for edge in net.getEdges()
        for lane in edge.getLanes()
    ]
    window = [f for f in frames if t0 - 1e-9 <= f.time_s <= t1 + 1e-9]
    every = max(1, int(round(step_s / 0.1)))
    images = []
    roles = {finisher: "finisher", helper: "helper"}
    for f in window[::every]:
        img = base.copy()
        dr = ImageDraw.Draw(img)
        dr.text((16, 12), title, fill=TEXT)
        dr.text((16, 36), f"{subtitle} | t = {f.time_s:5.1f} / 300.0 s", fill=SUB)
        if overlays:
            ov = max(
                (o for o in overlays if o["t"] <= f.time_s + 1e-9),
                key=lambda o: o["t"],
                default=None,
            )
            if ov is not None:
                for n in ov.get("safe_nodes", []):
                    cx, cy = full.px(*net.getNode(n).getCoord())
                    dr.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(120, 40, 40))
                owner = {g: vid for vid, g in ov.get("assignment", {}).items()}
                for n in ov.get("gate_nodes", []):
                    cx, cy = full.px(*net.getNode(n).getCoord())
                    col = COLOURS.get(owner.get(n), (200, 200, 200))
                    dr.rectangle((cx - 6, cy - 6, cx + 6, cy + 6), outline=col, width=2)
                dr.text(
                    (left[0] + 8, left[3] - 40),
                    f"safe region: {ov.get('safe', len(ov.get('safe_nodes', [])))} junctions",
                    fill=(240, 150, 150),
                )
        for vid, v in f.vehicles.items():
            x, y = full.px(v.x, v.y)
            c = COLOURS.get(vid, (160, 160, 160))
            r = 7
            if vid == "e1":
                dr.rectangle((x - r, y - r, x + r, y + r), outline=c, width=3)
            else:
                dr.ellipse((x - r, y - r, x + r, y + r), outline=c, width=3)
            tag = NAMES.get(vid, vid) + (f" ({roles[vid]})" if vid in roles else "")
            dr.text((x + 10, y - 8), tag, fill=c)
        if "e1" in f.vehicles:
            e = f.vehicles["e1"]
            # Draw the zoom on its own canvas and paste it, so nothing spills out of the panel.
            zw, zh = right[2] - right[0], right[3] - right[1]
            zimg = Image.new("RGB", (zw, zh), PANEL)
            zdr = ImageDraw.Draw(zimg)
            zoom = _View(
                (0, 0, zw, zh), e.x - zoom_radius, e.y - zoom_radius * zh / zw, 2 * zoom_radius
            )
            for lane, _internal in lanes:
                shape = lane.getShape()
                if not any(
                    abs(px - e.x) < zoom_radius * 1.6 and abs(py - e.y) < zoom_radius * 1.6
                    for px, py in shape
                ):
                    continue
                pts = [zoom.px(px, py) for px, py in shape]
                zdr.line(pts, fill=ROAD_ZOOM, width=max(2, int(lane.getWidth() * zoom.scale)))
                zdr.line(pts, fill=LANE_LINE, width=1)
            for vid, v in f.vehicles.items():
                if abs(v.x - e.x) > zoom_radius * 1.3 or abs(v.y - e.y) > zoom_radius * 1.3:
                    continue
                c, s = math.cos(v.heading_rad), math.sin(v.heading_rad)
                hl, hw = v.length_m / 2, v.width_m / 2
                pts = [
                    zoom.px(v.x + a * c - b * s, v.y + a * s + b * c)
                    for a, b in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))
                ]
                col = COLOURS.get(vid, (160, 160, 160))
                zdr.polygon(pts, fill=col, outline=(0, 0, 0))
                lx, ly = zoom.px(v.x, v.y)
                zdr.text((lx + 12, ly - 16), NAMES.get(vid, vid), fill=col)
            _scale_bar(zdr, zoom, 10, "10 m")
            img.paste(zimg, (right[0], right[1]))
        dr.text(
            (16, 532),
            (
                "Red = evader | P1 blue, P2 yellow, P3 green, P4 violet, P5 white "
                f"| finisher = {NAMES.get(finisher, finisher)}, "
                f"helper = {NAMES.get(helper, helper)}"
            )
            if finisher
            else (
                "Red = evader, dark-red dots = its safe region, squares = gates in the colour of "
                "the pursuer sent there | P1 blue, P2 yellow, P3 green, P4 violet, P5 white"
            ),
            fill=TEXT,
        )
        if verdict_line:
            dr.text((16, 556), verdict_line, fill=WARN)
        speeds = " | ".join(
            f"{NAMES.get(v, v).lower()}: {f.vehicles[v].speed_mps:4.1f} m/s"
            for v in sorted(f.vehicles, key=lambda k: (k != "e1", k))
        )
        dr.text((16, 584), speeds, fill=TEXT)
        images.append(img)
    images[0].save(out, save_all=True, append_images=images[1:], duration=90, loop=0)
