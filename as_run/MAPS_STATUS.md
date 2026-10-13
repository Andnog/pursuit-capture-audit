# Map status — which legacy OSM maps actually work

Generated 21 September 2026 by `scripts/audit_maps.py`. Machine-readable form:
[`MAPS_STATUS.json`](MAPS_STATUS.json).

**Regenerate before any dataset decision:**

```bash
uv run python scripts/audit_maps.py --out MAPS_STATUS.json
```

The audit is **read-only**. It parses each network with `sumolib`; **no SUMO process is started and no
episode is run.** No map is copied or modified.

## Result: 12 of 12 usable, no caveats

Every map in the legacy manifest parses cleanly, matches its recorded `sha256`, and passes the thresholds
below. Parsed edge and junction counts agree with the manifest in every case.

| Map | Split | Edges | Junctions | Dead ends | Multi-lane | Max lanes | Length |
|---|---|---:|---:|---:|---:|---:|---:|
| `washington_downtown` | train | 1098 | 498 | 18 (1.64%) | 53.2% | 5 | 85.1 km |
| `toronto_downtown` | train | 721 | 298 | 6 (0.83%) | 54.7% | 4 | 64.4 km |
| `adelaide_cbd` | train | 893 | 420 | 17 (1.90%) | 34.7% | 5 | 81.6 km |
| `seattle_downtown` | train | 433 | 218 | 7 (1.62%) | 55.7% | 4 | 30.4 km |
| `berlin_mitte_large` | validation | 1204 | 573 | 11 (0.91%) | 20.7% | 5 | 97.0 km |
| `sapporo_grid` | validation | 721 | 312 | 17 (2.36%) | 50.4% | 5 | 74.5 km |
| `phoenix_downtown` | validation | 483 | 241 | 9 (1.86%) | 44.7% | 6 | 61.9 km |
| `portland_downtown` | validation | 805 | 430 | 23 (2.86%) | 55.7% | 4 | 55.6 km |
| `chicago_loop` | **test** | 1327 | 683 | 21 (1.58%) | 55.7% | 6 | 96.0 km |
| `melbourne_cbd` | **test** | 823 | 471 | 35 (4.25%) | 38.6% | 4 | 64.0 km |
| `salt_lake_city` | **test** | 596 | 321 | 13 (2.18%) | 65.6% | 6 | 60.0 km |
| `minneapolis_downtown` | **test** | 492 | 245 | 9 (1.83%) | 55.7% | 5 | 54.2 km |

Thresholds applied: at least 100 passenger edges, at least 50 junctions, dead-end fraction at most 40%.

## The sealed historical TEST set is identified

This audit resolves a blocker that had been open since B0. The historical handoff stated at every
checkpoint that the final city TEST set remained sealed, but **never recorded which cities it was**.
The legacy manifest does:

> **TEST: `chicago_loop`, `melbourne_cbd`, `salt_lake_city`, `minneapolis_downtown`.**

Those four are now identified and must stay closed. A transfer claim can finally assert disjointness from
the historical TEST set instead of recording that disjointness is unprovable.

## Two facts that constrain how these may be used

**`berlin_mitte_large` is EXPOSED — confirmed 21 September 2026.** The Research lead confirmed it is the
same extract as the historical Berlin training map. So a map the legacy manifest records as `validation`
**carries training exposure**, and it must not be used as a fresh holdout. Any result on it is development
evidence.

The consequence for D15 is concrete: **the legacy 4/4/4 split cannot be adopted as-is**, because its
validation set contains an exposed map. A fresh split must either drop `berlin_mitte_large` from
validation or keep it and report it separately as exposed.

The other 11 carry no such flag: the historical four-map programme used Condesa, Berlin, Boston and Roma as
*local* extracts, and only Berlin appears among the 12.

**Dead ends are scarce, which makes them informative.** Between 0.83% and 4.25% of passenger edges are
cul-de-sacs, mean 1.99%. This bears directly on the capture contract: a capture in a dead end counts as
**coordinated** only if the evader was *forced* there with evidence it could not have taken a better exit.
Because cul-de-sacs are this rare, that claim is checkable by enumeration rather than assertion — and a
capture that merely happens to occur in one is distinguishable from a forced one.

## What this does and does not establish

**Establishes:** all 12 networks are well formed, hash-verified, and structurally adequate for the task;
the historical split assignment, including the TEST identity.

**Does not establish:** that an episode runs on any of them. Parsing proves a file is well formed, not that
the simulator drives vehicles across it. The first such check is a W4 action under that stage's gate.

**Does not decide D15.** These splits come from the **legacy** manifest, so adopting them carries the
legacy exposure with them. A fresh split decision is still required, and it now has an evidence base.

## Provenance

Source: `/Users/andrei/Documents/PHD/Union/urban_dynamic_containment/assets/osm/manifest.json`.
License: OpenStreetMap-derived data; **ODbL attribution required**.

These are **legacy assets**. This audit reads, hashes and assesses them; it copies nothing. Adopting any of
them into this project requires a provenance entry with its hash under the fresh-start policy.
