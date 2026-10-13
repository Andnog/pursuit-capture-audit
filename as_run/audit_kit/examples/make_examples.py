"""Write three small synthetic traces (0.1 s step) that show how the endpoints differ."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def car(x, y, heading_deg, speed):
    return {"x": x, "y": y, "heading_rad": heading_deg * 3.141592653589793 / 180.0, "speed": speed,
            "length": 5.0, "width": 1.8}  # fmt: skip


def write(name, frames):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as handle:
        for t, vehicles in frames:
            handle.write(json.dumps({"t": round(t, 1), "vehicles": vehicles}) + "\n")


def blocked_stop():
    """The evader stops 1 m behind a stopped pursuer and stays there: an operational capture."""
    frames = []
    for k in range(61):
        t = k / 10
        ex = min(-6.0, -30.0 + 8.0 * t)  # arrives at x = -6 (bodies 1 m apart) and stops
        frames.append(
            (t, {"e1": car(ex, 0.0, 0, 8.0 if ex < -6.0 else 0.0), "p1": car(0.0, 0.0, 0, 0.0)})
        )
    return frames


def passing_cars():
    """Opposite directions, lanes 3.2 m apart: within 5 m for an instant, nobody is stopped."""
    return [
        (
            k / 10,
            {
                "e1": car(-40.0 + 12.0 * k / 10, 0.0, 0, 12.0),
                "p1": car(40.0 - 12.0 * k / 10, 3.2, 180, 12.0),
            },
        )
        for k in range(61)
    ]


def follower_behind():
    """The pursuer follows 2.5 m behind the evader at speed: close, but the evader is free."""
    return [
        (
            k / 10,
            {"e1": car(10.0 * k / 10, 0.0, 0, 10.0), "p1": car(10.0 * k / 10 - 7.5, 0.0, 0, 10.0)},
        )
        for k in range(61)
    ]


if __name__ == "__main__":
    write("blocked_stop.jsonl", blocked_stop())
    write("passing_cars.jsonl", passing_cars())
    write("follower_behind.jsonl", follower_behind())
