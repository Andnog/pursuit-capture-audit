# Use the library

`pursuit_audit` scores an episode under several capture endpoints, so that a study can report them side by side and
say what its success rate means. It needs only the Python standard library.

```bash
git clone https://github.com/Andnog/pursuit-capture-audit.git
cd pursuit-capture-audit && uv sync
```

## Score a trace

```python
import pursuit_audit as pa

frames = pa.load_trace("episode.jsonl")
row = pa.score_trace(frames, evader="e1")        # every endpoint, one flat dictionary

capture = pa.operational_capture(frames, evader="e1")
if not capture.captured:
    print("closest miss:", capture.closest_failure)   # which condition failed when they were closest
```

From the command line:

```bash
uv run pursuit-audit score episode.jsonl --evader e1
```

## The trace format

One frame per line, at a constant step:

```json
{"t": 12.3, "vehicles": {
  "e1": {"x": 1.0, "y": 2.0, "heading_rad": 0.0, "speed": 3.1, "length": 5.0, "width": 1.8},
  "p1": {"front_x": 9.0, "front_y": 2.0, "heading_deg": 90.0, "speed": 0.0, "length": 5.0, "width": 1.8}}}
```

`x`, `y` is the centre of the body; give `front_x`, `front_y` if your simulator reports the front bumper, as SUMO
does. `heading_rad` is measured from +x, counter-clockwise; `heading_deg` is a compass angle. A trace with a
missing frame or a non-numeric value is refused instead of being scored: incomplete evidence is not a failed
capture.

## Change the rule

Every threshold is a parameter, and the rule is a composition of named conditions:

```python
strict = pa.CaptureParameters(gap_max_m=1.5, dwell_s=3.0)
capture = pa.operational_capture(frames, evader="e1", params=strict)

rule = pa.contact_specification(strict)            # the conditions that must hold at one instant
```

The band of the gap has to be chosen with the simulator's own stopping distance in mind: a follower that stops
behind its leader must be able to come to rest inside the band, and a pursuer that merely trails the evader must
not.

A proximity rule is a threshold and a distance. Three distances are built in, and another is one call away:

```python
pa.proximity(frames, "e1", pa.ProximityRule(5.0, "body"))      # between bodies
pa.proximity(frames, "e1", pa.ProximityRule(5.0, "front"))     # between front bumpers

pa.register_distance("rear", my_rear_bumper_distance)
```

## Clustered intervals

```python
from pursuit_audit import family_bootstrap

# differences[(city, scenario, evader)] = [method A minus method B, one value per team size]
interval = family_bootstrap(differences, alpha=0.05)
print(interval.estimate, interval.low, interval.high)
```

Episodes that share a start are not independent observations. The intervals resample families, so that every cell
of a family moves together; `two_stage=True` resamples cities first.

## How it is organized

| Module | What it holds | Pattern |
|---|---|---|
| `domain` | vehicle bodies, traces | value objects |
| `endpoints` | operational capture; proximity rules | Specification; Strategy with a registry |
| `controllers` | prediction of the evader's path; assignment of pursuers to lanes | pure functions |
| `statistics` | family-clustered bootstrap; paired contrasts | |
| `evidence` | sealed packages; the catalogue of studies | Repository |
| `reporting` | headline results recomputed from raw records | |

The patterns are there where they make the rule easier to read or to extend, and nowhere else.
