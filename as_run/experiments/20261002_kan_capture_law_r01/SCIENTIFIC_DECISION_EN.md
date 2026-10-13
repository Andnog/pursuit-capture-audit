# KAN capture law r01 (A-104; post hoc, descriptive; no new simulation)

**Data.** 5,382 episodes of the optimised planner (`c2_15`) from the sealed A-99 test and the A-101 r02 test. Fit on
the 4 TRAINING cities (3,098 episodes); test on the 3 DEVELOPMENT cities (2,284 episodes).

**Features** (scenario-level only): team size, evader type, pursuer speed, free-flow time of the nearest and mean
pursuer to the evader's start, and lanes to close at the evader's first junction. City-level features were excluded
after a first attempt: they are constant within each of only four training cities and did not transfer
(held-out R² ≤ 0).

**Model.** Reference KAN (pykan 0.2.8), width 6-3-1, cubic splines, BCE loss, L1/entropy regularisation.

| Model | AUC train | AUC test | Brier test |
|---|---|---|---|
| Base rate | 0.50 | 0.50 | 0.214 |
| Logistic | 0.62 | 0.57 | 0.215 |
| **KAN** | 0.67 | **0.57** | 0.216 |
| Gradient boosting | 0.84 | 0.55 | 0.228 |
| MLP | 0.48 | 0.45 | 0.221 |

**Reading.**
- **Weakly predictable.** Whether a given episode ends in capture is only weakly predictable from its initial
  conditions (best held-out AUC 0.57). This is consistent with a process driven by the evader's moment-to-moment
  choices.
- **Lanes to close dominates.** The KAN's attribution ranks *lanes to close at the evader's first junction* first
  (score 0.75), then the mean pursuer time (0.51) and the nearest pursuer time (0.24). Team size, evader type and
  pursuer speed score low.
- **Effect size.** The KAN effect curve falls from ≈ 0.50 capture with 2–4 lanes to ≈ 0.18–0.23 with 7–9 lanes. The
  logistic coefficient for this feature is the largest (−0.85). This independently corroborates the structural
  blockability result (A-94).
- **Comparison with other models.** The KAN matches logistic regression in held-out accuracy and exposes the same
  dominant factor. Gradient boosting overfits (AUC 0.84 train vs 0.55 test).
- **Limitations.**
  - Some KAN effect curves are non-monotone and noisy.
  - Effect curves at intermediate values of the binary evader-type feature carry no meaning.
  - Symbolic extraction (`auto_symbolic`) was attempted in the first pass and failed numerically; no formula is
    claimed.
