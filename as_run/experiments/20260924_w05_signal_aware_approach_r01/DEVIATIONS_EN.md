# Deviations

## D-1. A stub that returned zero was written and removed before it could mislead

The first version of `earliest_arrival_on_approach` called a helper `_arrive_stopped` that returned `0.0`
unconditionally — dead code wearing the name of a calculation. Worse, it concealed a real omission: to stop
at a signal the vehicle must brake during the **preceding** segment, which takes longer than passing through.

Replaced with a **fixed point over the set of signals requiring a stop**, iterated until stable. Convergence
is not guaranteed — a signal can oscillate in and out of the set — so the iteration is bounded and a failure
to stabilise is **reported**, never rounded into a plausible number.

## D-2. Yellow is not treated as go

`is_green` accepts `G` and `g` only. Entering on yellow is a judgement the model must not make for the
vehicle, and treating it as go would produce times the simulator may refuse to honour.

## D-3. The model is achievable, not optimal

Waiting at a red and then proceeding is one strategy. A slower approach that catches an earlier green may
exist, so the computed time is not the infimum over all strategies. `UNDER` needs achievability, so this is
a gap in tightness rather than in soundness — and it is recorded rather than blurred.

## D-4. The verdict is on sign, and the sign was fixed before the numbers existed

The protocol states that accuracy is not the criterion. It would have been easy to present "worst deviation
falls from 117.0 s to 5.6 s" as success. It is progress, and the model still fails the only test that
matters for `UNDER`.

## D-5. The distance discrepancy is reported unresolved

Two candidate causes were tested and both ruled out. Rather than proceed on a model whose distance is wrong
by up to 4%, the package stops and names it.

## D-6. Resource limit respected

80 process starts permitted, 64 used. No optimizer, no checkpoint, no TEST access.
