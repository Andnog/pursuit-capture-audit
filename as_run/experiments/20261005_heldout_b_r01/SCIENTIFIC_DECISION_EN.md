# Scientific decision — single-shot evaluation on a second held-out set of cities (A-138)

**Date:** 2026-10-06. **Package:** `experiments/20261005_heldout_b_r01`. Single shot; the four cities (Denver,
Vancouver, Barcelona, Buenos Aires) are now **spent**.

**Version 2, written a few minutes after version 1, on the same night.** Version 1 (`SCIENTIFIC_DECISION_EN.v1_superseded.md`, kept)
quoted the wrong TEST figure in its reading: +0.171, which is the TEST result against the OPTIMAL evader, instead of
the TEST primary, +0.145; and a TEST pursuit rate pooled over three evaders (0.172) instead of two (0.198). The
error was in the comparison text only. No number of this evaluation, no primary and no verdict changes; results,
summary, inputs and logs are byte-identical to the first seal (`checksums.v1_superseded.json`).

## Integrity

- 4,640 scheduled episodes, 4,640 rows, no duplicate key. 4,498 valid, 142 failed, 0 collisions.
- Every failure has one cause, recorded before any controller acts: the frozen scenario generator could not place the
  team (`ValueError: scenario could not place the team`). The 42 failed keys are identical for the three methods, so
  every contrast is paired on the same scenarios. The null team has 16 failures of the same kind.
- Failures by city: Vancouver 0, Denver 6, Barcelona 16, Buenos Aires 20 per method (of 360).
- The 68 source files and the four networks hashed in `inputs.json` are unchanged at the end of the run.
- The run is one evaluation in two sittings (12 episodes on 5 October, the rest on 6 October), on the same sources
  (`DEVIATIONS_EN.md`). No outcome was read before the run ended; `summary.json` was read once, complete.
- The methods, the endpoint, the scenario generator and the analysis were frozen before the cities were downloaded.

## Primaries (family-clustered, 97.5 % intervals; 157 families, 459 paired cells)

| Primary | Estimate | Interval | Lower bound > 0 |
|---|---|---|---|
| **B1** PLB − pursuit, operational capture (OC) | +0.064 | [0.015, 0.114] | **met** |
| **B2** body gap ≤ 5 m − OC, pursuit team | +0.549 | [0.476, 0.620] | **met** |

Both pre-registered primaries are met. With cities resampled first (city → family, 95 %): B1 [0.009, 0.132], B2
[0.416, 0.674].

## Rates (AVOIDANT and RANDOM evaders, teams of 3, 5 and 7)

| Team | OC | Body gap ≤ 5 m | Centre ≤ 5 m |
|---|---|---|---|
| PLB | 0.291 | 0.792 | 0.647 |
| Junction ambush | 0.267 | 0.777 | 0.641 |
| Pursuit | 0.227 | 0.776 | 0.643 |
| Null team (random routes, five pursuers) | 0.016 | 0.273 | 0.214 |

Body gap ≤ 5 m scores the pursuit team 3.4 times higher than OC (0.776 against 0.227).

## Secondaries (95 %, family-clustered)

- OPTIMAL evader, PLB − pursuit: +0.073 [0.017, 0.131] (rates 0.158 against 0.085).
- PLB − junction ambush: +0.024 [−0.017, 0.064]. **Not distinguishable from zero.**
- Centre ≤ 5 m − OC, pursuit: +0.416 [0.348, 0.484].
- PLB − pursuit under body gap ≤ 5 m: +0.016 [−0.002, 0.037]; under centre ≤ 5 m: +0.004 [−0.016, 0.025]. The
  ranking that OC shows is not visible under either proximity rule.
- By city, PLB − pursuit (OC): Denver +0.145 [0.033, 0.254]; Vancouver +0.029 [−0.075, 0.121]; Barcelona +0.031
  [−0.014, 0.086]; Buenos Aires +0.050 [0.000, 0.111]. The sign is positive in the four cities; only Denver is
  distinguishable from zero on its own.
- By team: 3 pursuers +0.054 [−0.003, 0.112]; 5 pursuers +0.082 [0.023, 0.138]; 7 pursuers +0.057 [−0.003, 0.117].

## Reading

1. **The measurement finding replicates at full strength.** On cities chosen and built after every design decision,
   a 5 m proximity rule still scores the same pursuit episodes several times higher than OC, a team that does not
   pursue still reaches 27 % under it and 1.6 % under OC, and the difference between controllers that OC shows
   disappears under proximity.
2. **The controller advantage replicates in sign and passes its registered test, with a smaller size.** PLB − pursuit
   is +0.064 here and was +0.145 (family 97.5 % [0.086, 0.207]) on TEST. The two results are reported side by side
   and are not pooled. With the same pooling, the pursuit team scores higher here than on TEST (0.227 against 0.198)
   and PLB lower (0.291 against 0.343).
3. **PLB over the junction ambush does not replicate as a detectable difference.** It was +0.102 [0.053, 0.151] on
   TEST and is +0.024 [−0.017, 0.064] here. On these cities the evidence supports "junction-based blocking beats
   pursuit" more firmly than "PLB beats the simpler junction ambush".
4. **Heterogeneity between cities is real and is not explained here.** One of four cities carries most of the pooled
   advantage. No cause is claimed. The two cities with many one-way streets (Barcelona, Buenos Aires) also have the
   most unplaceable scenarios.

## Consequences for the article

- The article can say that both pre-registered primaries held on a second set of four cities that did not exist in
  the project when the methods were frozen: eight held-out cities in two independent single shots.
- The size of the controller advantage must be reported as a range across the two held-out sets (+0.064 to +0.145),
  not by the TEST figure alone.
- The claim "PLB improves on the junction ambush" must be limited to TEST and the development cities, with this
  result stated next to it.
- Whether the TEST and held-out B estimates differ by more than sampling error is a post hoc question. It is
  answered in a separate, labelled package and is not part of this decision.

## Differences from the TEST evaluation (A-110)

- The capture judge carries the invalid-value guard added after the fifth review. It can remove a capture and cannot
  create one; 140 of 140 earlier episodes reproduce with it.
- Three methods instead of five (the learned controllers were not run), and no certificate audit.
- The maps were built by this project from OpenStreetMap with a recipe recovered from the headers of the existing
  networks; the original extraction script is not available.
