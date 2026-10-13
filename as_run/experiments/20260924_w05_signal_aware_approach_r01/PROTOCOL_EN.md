# Protocol — a signal-aware approach model, and whether it earns `UNDER` on the network

## Authorisation and scope

The Research lead chose, on 2026-09-24:

- **(1b)** `SUPPORTED` redefined over **windows** rather than exact times.
- **Window path:** the model **reads the signal program**.
- **Capacity:** must hold **over the whole window**.
- **Width:** **derived per approach** from the network.

This package builds the first component that all three depend on: an approach model that
computes an arrival time the vehicle can actually achieve, given the lanes it really
traverses and the signals it really meets. **Windows and capacity-over-windows are not
implemented here** and are not claimed.

## Why a lookup and not a prediction

A-40's `UNDER` failed on the network because the model asserted times the vehicle could not
reach. Reading a signal program is **not** a return to prediction: the programs are
fixed-time, deterministic, and there is no background traffic, so a release time is a
lookup of what the simulator will do. That is what keeps `UNDER` earnable in principle.

## The test that decides it

**Release speed control entirely** and let SUMO drive as fast as it legally can. Compare
that against the model's computed earliest arrival.

| Sign | Meaning |
|---|---|
| model **≥** SUMO free run | the model under-approximates achievability — `UNDER` is earnable |
| model **<** SUMO free run | the model is **optimistic**: it claims a time the vehicle cannot reach even at full effort |

**Accuracy is not the criterion. Sign is.** A model that is close but optimistic earns
nothing, because `UNDER` is a guarantee and not an estimate.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `MODEL_UNDER_APPROXIMATES` | model ≥ SUMO free run on every route |
| `MODEL_STILL_OPTIMISTIC` | the model is earlier than the free run on any route |
| `RUN_FAILED` | too few routes complete to judge |

A `MODEL_STILL_OPTIMISTIC` verdict must report **how far** the model has come as well as
where it stands, because the distance from A-40 is itself the finding.

## Controls

- Run at SUMO's default driver imperfection **and** at `sigma = 0`, so "the model is
  optimistic" is separated from "SUMO's default driver is deliberately imperfect".
- Record the model's own distance against SUMO's odometer distance. A model that disagrees
  about **how far** cannot be judged on **how long**.

## Prohibited

- Fitting any delay term to the residual.
- Selecting routes after seeing their error.
- Any TEST map, optimizer update or checkpoint load.

## Resource limits

SUMO process starts permitted: **80**. No optimizer, no checkpoint, no TEST access.
