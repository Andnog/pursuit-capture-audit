# Decision — the deficit had two causes, and the first was mine

**Claim class: diagnostic.** No pre-registered acceptance rule, because there was no hypothesis to test —
A-41 left the mechanism open. No capture, no assistance, no learning, no TEST map. Nothing discharges O22.

## Verdict

`TWO_MECHANISMS_ONE_WAS_MY_OWN_MODELLING_ERROR`.

## Finding 1 — the abstraction was given a speed the vehicle is not allowed to use

`route_speed_limit` sampled **only normal edge lanes**. SUMO's **internal junction lanes** are much slower,
and every route crosses them.

On `adelaide_cbd`:

| Lane class | n | median | min |
|---|---|---|---|
| Normal | 1358 | **13.89** m/s | 2.78 |
| Internal (junction) | 3299 | **7.99** m/s | 2.78 |

**68% of internal lanes are slower than 13.89 m/s**, median 6.51 m/s among those.

So the constructive schedule was built against a speed limit the vehicle can never hold through a junction.
It was not SUMO failing to deliver what the abstraction assumed — **the abstraction assumed something
impossible.**

**The correction is a model input, not a fitted term.** Take the minimum over the route's edge lanes *and*
the internal lanes connecting them. That is the conservative bound `UNDER` always required: an
under-approximation must assume the slowest legal passage, not the fastest.

### Effect, same routes, same seed, same tolerance

| | Naive limit | Corrected limit |
|---|---|---|
| Median error | **39.636 s** | **4.351 s** |
| Max error | 117.045 s | 101.798 s |
| Kept feasibility throughout | 0 of 12 | **2 of 12** |
| Within the 0.1 s tolerance | 0 of 12 | 0 of 12 |

**Seven of twelve routes fall to 0.104–0.205 s** — the observation resolution. Per-route reductions reach
**362×** and **209×**.

## What this does to A-40 and A-41

**Their magnitudes were inflated by a defect in my runner. Their conclusion survives.**

- A-41 reported *"48 of 48 lost feasibility mid-flight"*. Under a model using a reachable speed, that is
  **10 of 12**.
- Median error **39.6 s becomes 4.35 s**.
- **Still 0 of 12 arrive within tolerance.** The refutation stands; it was overstated by roughly an order of
  magnitude.

Neither sealed package was edited. This is the correction of record.

## Finding 2 — the residual is consistent with traffic lights, and is not confirmed

| Evidence | |
|---|---|
| **For** | All three routes with **zero** signals on the approach have residuals below 0.21 s. The most signalised map, `washington_downtown` at 4–8 signals per route, is uniformly large: 10.3 to 101.8 s. |
| **Against a count rule** | Seattle routes 0, 1, 2 all cross **two** signals and give 37.7 / 47.1 / **0.14** s. Toronto crosses 3 and 5 signals with small residuals, and 2 signals with 8.5 s. |

**Count does not determine the outcome, because being stopped depends on phase timing at the moment of
arrival, not on how many signals are passed.** This is the same reason junction count explained nothing in
A-41 — and the second time a count has been the wrong variable, which is worth remembering before reaching
for a third one.

Two routes got **worse** under the corrected limit (Seattle 0: 34.7 → 37.7 s; Seattle 1: 40.8 → 47.1 s). A
delay that does not shrink when the schedule is relaxed is **additive**, not kinematic — which is what a red
phase looks like.

**Status: plausible and unconfirmed.** No signal-phase trace was recorded. That would confirm it and was not
done here.

## Consequence for the window-based redefinition of `SUPPORTED`

A signal hold is set by the signal program. **From the kinematic model's point of view it is unbounded, and
no kinematic bound absorbs it.** So a window-based `SUPPORTED` has three options:

1. Windows wide enough to span the **worst-case signal delay** on the approach — requires reading the signal
   program, which is available from the network.
2. The model **reads the signal program** and schedules against it.
3. Stations restricted to **unsignalised approaches**.

Option 3 is worth noting precisely because A-41 closed the analogous junction-free restriction as *empty*.
**This one is not empty: three of twelve routes qualify.**

## What is not established

That traffic lights are the residual cause. Capture, assistance, learning, benefit, transfer, novelty. O22.
