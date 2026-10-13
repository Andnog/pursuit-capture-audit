# Decision — the signal-aware approach model

**Claim class: model soundness on the network.** No capture, no assistance, no learning, no TEST map.
Nothing discharges O22. **Windows and capacity-over-windows are not implemented here.**

## Verdict

`MODEL_STILL_OPTIMISTIC`.

The model closes almost all of the gap A-40 opened, and **still does not earn `UNDER`**, because the
criterion is sign and not accuracy.

## What it explains

A-40 measured a **+117.0 s** error on `washington_downtown` route 0 and could not account for it. A-41
withdrew the junction attribution. A-42 found the internal-lane speed error and left a residual consistent
with signals but unconfirmed.

The signal-aware model resolves it:

| | |
|---|---|
| Naive target | 73.86 s |
| Actual arrival | 190.905 s |
| **Model** | **190.790 s** |
| Model error | **0.115 s** |
| Predicted signal waits | 3, totalling **121.122 s** |

**The 117 seconds were three red lights.** A-42's candidate is confirmed, and the model predicts the whole
of it to within a tenth of a second.

Across 12 routes the worst deviation falls from **117.0 s** to **5.6 s**.

## Why that is not enough

`UNDER` is a **guarantee**, not an estimate. A model that is close but *early* claims a time the vehicle
cannot reach even at full effort, and a set built from it is not under-approximating.

With speed control released so SUMO drives as fast as it legally can, and driver imperfection set to zero:

| model − SUMO free run | |
|---|---|
| min | **−5.606 s** |
| median | **−1.209 s** |
| max | +1.890 s |
| **optimistic routes** | **8 of 12** |

**The model is earlier than the best the vehicle can do on two thirds of routes.** It does not yet earn
`UNDER`.

## Two controls

**SUMO's default driver is not the explanation.** Imperfection `sigma = 0.5` costs only 0.5–3.0 s against
`sigma = 0`. The optimism survives removing it.

**The distance disagreement is the dominant residual.** The model's own segment chain is short of SUMO's
odometer by up to **42.3 m**, median 17.3 m. The relationship is direct:

| distance gap | deviation |
|---|---|
| 0 m (3 routes) | −2.566, −0.182, **+1.615** s |
| −42 m | −5.6 s |

**A model that disagrees about how far cannot be judged on how long.** On the three routes where distances
agree, the model is close and one of them is conservative.

**Ruled out as causes**: lane choice — slowest, longest and edge-length give the *identical* total; and
missing internal lanes — every connection on the probed route has a via lane. **The cause is not
identified**, and it is the next thing to fix rather than something to reason around.

## Where this leaves the Research lead's choices

- **Window path — model reads the signal program:** vindicated. Signals were the residual, and reading the
  program predicts them to 0.115 s on the worst case.
- **Capacity over the whole window** and **width derived per approach:** both still unimplemented, and both
  depend on an approach model that under-approximates. That is the gate.

## What is not established

That the model under-approximates. Windows. Capacity over windows. Capture, assistance, learning, benefit,
transfer, novelty.
