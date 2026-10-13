# Split protocol

Stage: W2. Date: 21 September 2026.
Status: **protocol specified; no dataset generated; D15 UNRESOLVED; TEST closed.**

## 1. Three splits, three different permissions

| Split | Permits | Forbids |
|---|---|---|
| `TRAINING` | gradient updates, demonstrations, normaliser fitting | — |
| `DEVELOPMENT` | evaluation, method decisions | gradient updates; adding its trajectories to training data |
| `TEST` | one final evaluation after everything is frozen | any access before the freeze |

`DEVELOPMENT` exposure is **recorded**, because method selection uses its information even without
gradients. An examined holdout is exposed development evidence, not a fresh holdout.

## 2. City-level separation

Unseen-city transfer requires separation at the **city** level, not random road segments. Overlapping OSM
extracts and derived-data leakage must be inspected, not assumed absent: two extracts of the same
metropolitan area can share road segments while carrying different names.

Frozen per map: provenance, city boundary, road-data version, clipping, graph construction, traffic
demand, route generation and scenario seeds, with licenses and hashes of source and generated assets.

## 3. Inherited exposure — this is not a clean slate

The historical programme exposed the following. They are **not** available as fresh holdouts:

| Asset | Exposure |
|---|---|
| Condesa, Berlin, Boston, Roma | the four historical maps; used throughout the historical programme |
| the four Condesa cases, indices 0..3, seeds 520000..520003 | examined in three successive evidence packages (O26, O27, O28) |
| the 20 reserved TRAINING curriculum cases | 180 paired zero-update jobs were frozen and launched over them; their outcomes were opened |
| historical DEVELOPMENT episodes | used for method decisions throughout |

Consequently **any city used for a transfer claim in this project must be separated at the city level from
all four historical maps**, and the extract overlap must be checked rather than assumed.

## 4. The sealed historical TEST set — an unresolved blocker

The historical record states at every checkpoint that the final city TEST set remained sealed and was never
opened. **It does not record the identity or provenance of that set.**

Until it is located, this project cannot claim that its own TEST split is disjoint from it. Reusing a city
that was reserved as historical TEST — without knowing it — would silently destroy the transfer claim. This
is recorded as an open blocker in [`../governance/LEGACY_OBLIGATIONS_EN.md`](../governance/LEGACY_OBLIGATIONS_EN.md) §6.

## 5. Four reported settings

Reported **separately**, never averaged into one generalisation number:

1. new starts in known maps;
2. new cities;
3. new evader policies;
4. new cities combined with new evaders.

A new road topology is allowed as public map information under the declared deployment interface. Frozen
normalisers; no learning from TEST trajectories. **Any target fine-tuning is a separate adaptation
experiment and must not be labelled zero-shot transfer** — the nearest precedent in the literature performs
target adaptation, so the distinction decides whether the comparison is fair.

## 6. Opening TEST

TEST stays closed until method, checkpoint-selection rule, metrics, inference procedure and resource limits
are all frozen, and the manifest is sealed. Opening it is a recorded, one-time event with its own ledger
entry.

## 7. Implementation status

**No dataset exists.** `maps_manifest.json` and `split_manifest.json` are declared empty with their
required field sets, so that a later population cannot quietly omit provenance. D15 is UNRESOLVED.
