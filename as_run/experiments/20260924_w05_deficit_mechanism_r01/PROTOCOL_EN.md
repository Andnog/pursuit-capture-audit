# Protocol — why does SUMO deliver less progress than the kinematic abstraction assumes?

## This is a diagnostic, and it says so

**There is no pre-registered acceptance rule, because there was no hypothesis to test.** A-41 withdrew
A-40's mechanism attribution and left the question open: SUMO overrides the commanded speed, the deficit
accumulates, and *why* was not established.

Fabricating a frozen acceptance rule after the fact would be worse than admitting the shape of the work.
What is fixed instead:

1. **Candidates are checked against the whole corpus, not the route that suggested them.** A-40 attributed a
   mechanism from one route and A-41 had to withdraw it. A candidate that explains one route explains
   nothing.
2. **Any correction found is applied to the MODEL, never fitted to the measurements.** A modelling error is
   repaired by using the right quantity; it is not repaired by adding a term calibrated on the residual.
3. **If a correction reduces the error, the previous refutation is re-stated rather than quietly softened.**
   A-40 and A-41 are sealed; if their magnitudes were inflated by a defect in the runner, that is recorded in
   those words.

## Method

- Offline inspection of the network files with `sumolib`: no claim about the simulator is made from a
  quantity that can be read from the network itself.
- Where a candidate implies a different model input, re-run the **closed-loop** arm of A-41 across the same
  4 TRAINING maps and 12 routes with the corrected input, and compare like with like.
- Same tolerance, 0.1 s. Same routes, same order, same seed.

## Prohibited

- Fitting any delay term to the residual.
- Selecting routes after seeing their residual.
- Any TEST map, optimizer update or checkpoint load.
