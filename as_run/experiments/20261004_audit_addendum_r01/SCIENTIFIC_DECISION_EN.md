# Scientific decision — audit addendum r01 (A-115)

Versioned replays completing follow-up of sealed episodes, plus one negative control and offline reanalysis.
3,459 replay/episode rows (12 placement failures, all in B3). Summary data: `ADDENDUM_SUMMARY.json`.

## B1 — persistence of PC captures, now with complete follow-up (R1)

The 188 right-censored A-108 replays were re-run with pursuers frozen and the horizon extended to t_c + 61 s; all
reproduced and now have 60 s of follow-up. **0 of 1,433 captured evaders escape within 60 s (Wilson 95 % upper bound
0.27 %).** The earlier statement was right in outcome but its follow-up was incomplete for 188 cases; this addendum
completes it.

## B2 — certificates with complete follow-up and joint escape (R2)

Joint escape is gate escape or leaving the network within 60 s, with the horizon extended so that no audit is
censored.

| Indicator | Set | Audited | Gate escape | Network exit (extra) | **Joint escape** | Wilson 95 % | Family 95 % | PC among audited |
|---|---|---|---|---|---|---|---|---|
| Lane-level | TEST | 240 | 13 | 6 | **19 (7.9 %)** | [5.1, 12.0] | [1.6, 15.9] | 0.95 |
| Lane-level | A-91 | 225 | 18 | 1 | **19 (8.4 %)** | [5.5, 12.8] | [4.9, 12.4] | 0.97 |
| Junction-level | TEST | 848 | 512 | 103 | **615 (72.5 %)** | [69.4, 75.4] | [66.2, 78.5] | 0.25 |
| Junction-level | A-91 | 1,098 | 805 | 95 | **900 (82.0 %)** | [79.6, 84.1] | [79.7, 84.2] | 0.16 |

Reading:
- The lane-level indicator is an empirically evaluated, fallible containment indicator. About 8 % of certified
  evaders escape under the joint definition, against 72–82 % for the junction-level indicator.
- Its upper bounds exceed 10 %, so the earlier "confirmed (escape ≤ 10 %)" verdicts, which counted gate escapes only
  and censored late certificates, are not reproduced under the joint definition. Per A-115, no new pass/fail rule is
  applied.

## B3 — negative control: a null team that does not pursue (R3)

548 episodes, 7 non-TEST cities, five pursuers driving random routes:

| Endpoint | Null-team success | Wilson 95 % |
|---|---|---|
| PC | 3.1 % | [2.0, 4.9] |
| Body gap ≤ 5 m | 33.2 % | [29.4, 37.3] |
| Centre ≤ 5 m | 23.4 % | [20.0, 27.1] |
| Body gap ≤ 10 m | 42.3 % | [38.3, 46.5] |

PC registers incidental matches (slow following or queueing behind a non-pursuing vehicle) in about 3 % of episodes;
proximity endpoints register "success" in 23–42 % of episodes when nobody pursues. PC is an operational near-stop
endpoint with a small incidental floor, not proof that escape is physically impossible.

## B4 — family-clustered uncertainty (R5)

| Contrast | Estimate | Family 95 % | City → family 95 % |
|---|---|---|---|
| A-99: PLB − pursuit | +0.105 | [0.068, 0.141] | [0.054, 0.158] |
| A-99 primary: PLB − A-95 ambush | +0.050 | [0.016, 0.084] | [0.003, 0.097] |
| TEST H1: PLB − pursuit (97.5 %) | +0.145 | [0.086, 0.207] | [0.074, 0.228] (95 %) |
| TEST S1: PLB − ambush | +0.102 | [0.053, 0.151] | [0.043, 0.171] |
| TEST S2: PLB − pursuit, optimal evader | +0.171 | [0.108, 0.238] | [0.061, 0.281] |
| TEST S4: MAPPO-KAN − PLB | −0.001 | [−0.040, 0.037] | [−0.049, 0.045] |
| TEST S4: MAPPO-MLP − PLB | −0.009 | [−0.048, 0.030] | [−0.053, 0.034] |
| OX: PLB − pursuit, optimal evader | +0.214 | [0.149, 0.279] | [0.126, 0.304] |
| Goal-directed: PLB − pursuit | +0.105 | [0.058, 0.156] | [0.037, 0.181] |
| TEST H2: body ≤ 5 m − PC, pursuit (97.5 %) | +0.679 | [0.620, 0.735] | [0.570, 0.769] (95 %) |

Every pooled conclusion keeps its sign under family and two-stage city → family resampling. The A-99 primary is the
weakest: its lower bound is 0.003 with city clustering. Body ≤ 5 m / PC ratio for pursuit on TEST: 4.94.

## B5 — KAN with matched estimands (R6)

Same estimand: mean predicted probability vs observed capture of the same held-out rows, per bin.
- Lanes to close: correlation r = 0.28 (KAN), 0.33 (spline-additive logistic), 0.06 (MLP), 0.04 (logistic).
- MAE: 0.088 / 0.076 / 0.085 / 0.096.
- The earlier r = 0.70 compared partial dependence with conditional means and is withdrawn as evidence.
- Family bootstrap: AUC differences KAN − logistic, KAN − MLP and KAN − spline are all n.s. Lanes correlation KAN −
  logistic +0.18 [0.01, 0.30]; KAN − spline +0.03 [−0.12, 0.30].
- **A spline-additive model matches the KAN's shape fidelity, so no KAN-specific advantage remains.**
- Symbolic law: in scaled units −0.744·lanes; in raw units −0.186 logit per lane to close (scaling in the summary).

## B6 — "no route" branch (R9)

It appeared in 2 of 300 natural episodes (1 PLB, 1 junction ambush); negligible for the reported comparisons.
