# pursuit_audit — score a vehicle-pursuit study under more than one capture endpoint

Many multi-vehicle pursuit studies declare a capture when a pursuer comes within a few metres of the
evader. In microscopic traffic that rule is also met by two cars that pass each other in opposite
lanes. This small package scores the same episode under proximity rules and under an operational
capture rule, so that a study can report both and say what its success rate means.

It has no dependency beyond the Python standard library (3.10 or later). The SUMO helpers are optional.

## What it computes

For one episode, given as a trace of vehicle states:

| Endpoint | Rule |
|---|---|
| `oc` (operational capture) | For at least 2 s, continuously and for one and the same pursuer: body gap 0.3–2.0 m; both speeds at most 1 m/s; headings within 15°; the evader behind the pursuer, within 1 m of its axis |
| `body_5m`, `body_10m` | The gap between the two vehicle bodies is at most 5 m (10 m) at some instant |
| `centre_5m`, `centre_10m` | The distance between the two body centres is at most 5 m (10 m) |
| `front_5m`, `front_10m` | The distance between the two front bumpers is at most 5 m (10 m); this is what a simulator's "position" usually measures |

All thresholds are parameters. The operational band has to be chosen with the simulator's own
stopping distance in mind: a follower that stops behind its leader must be able to come to rest
inside the band, and a pursuer that merely trails the evader must not.

## Quick start

```bash
cd audit_kit
python -m pursuit_audit examples/*.jsonl --evader e1
```

The three example traces show the point of the exercise:

| Trace | What happens | `oc` | `body_5m` | `front_5m` |
|---|---|---|---|---|
| `blocked_stop` | the evader stops 1 m behind a stopped pursuer and stays | yes, at 5.0 s | yes | no |
| `passing_cars` | the two cars pass in opposite lanes at 12 m/s | no | yes | yes |
| `follower_behind` | the pursuer trails the evader at 10 m/s | no | yes | no |

From Python:

```python
import pursuit_audit as pa

frames = pa.load_trace("episode.jsonl")
row = pa.score_trace(frames, evader="e1")          # every endpoint, one flat dictionary
oc = pa.operational_capture(frames, evader="e1")    # details: pursuer, witness, why not
```

## Trace format

JSON Lines, one frame per line, at a constant step:

```json
{"t": 12.3, "vehicles": {"e1": {"x": 1.0, "y": 2.0, "heading_rad": 0.0, "speed": 3.1, "length": 5.0, "width": 1.8},
                         "p1": {"front_x": 9.0, "front_y": 2.0, "heading_deg": 90.0, "speed": 0.0, "length": 5.0, "width": 1.8}}}
```

- `x`, `y` is the **centre** of the body; give `front_x`, `front_y` instead if your simulator reports the front bumper.
- `heading_rad` is measured from +x, counter-clockwise; `heading_deg` is a compass angle (0 = north, clockwise).
- A trace with a non-finite value, a negative speed or an irregular step is refused (`TraceError`): it is unresolved
  evidence, not an observed failure.
- A frame in which the pursuer or the evader is missing breaks the witness. The witness cannot pass from one pursuer
  to another.

## SUMO helpers (optional)

`pursuit_audit.sumo.frame(conn, ids)` reads one frame from a running TraCI simulation, converting SUMO's front-bumper
position and compass angle. `pursuit_audit.sumo.hold_audit(conn, pursuers, evader)` holds every pursuer at the
instant a capture is declared and follows the evader for 60 s: it answers whether the declared capture persists.

To audit an existing environment without editing it, subclass it and read the state of the capturing pair before the
environment removes the evader; `scripts/audit_published_env.py` in the parent project does this for a published
environment.

## A reporting checklist

1. State the capture rule in full: which points of the vehicles the distance joins, the speeds allowed, and whether
   the evader is removed at capture.
2. Report the score of a team that does not pursue, under the same rule.
3. Report a hold audit: what the evader does in a fixed time after capture, with complete follow-up.
4. For any containment indicator, report the share of certified evaders that escape, counting exits from the network.
5. Evaluate on networks not used for design, opened once, with intervals clustered by scenario.
6. Say which analyses were registered before the runs and which were not.

`pursuit_audit.audits` has two small functions for items 2 and 5: success rates per endpoint and their paired
difference, with intervals that resample scenario groups instead of episodes.

## Checks

`tests/test_audit_kit.py` in the parent project covers the geometry, each condition of the operational rule, traces
and the command line. It also runs 400 random traces through this package and through the parent project's own
capture judge and requires the same verdict, pursuer, witness start and longest run.

## Limits

- The package scores traces; it does not simulate. The quality of the verdict is that of the trace.
- Operational capture is a near-stop behind a pursuer. It is not a proof that escape is impossible, and it requires
  no rear blocker.
- Defaults are those of the parent study (5 m vehicles; evader minimum gap 1.0 m, pursuers 2.5 m). Check the band
  against your simulator before using them.

## Status

Version 0.1.0, prepared with the article "When Proximity Is Not Interception". Licence and citation: to be set by
the author before release.
