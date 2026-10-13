# Evidence map of the manuscript

Written on 10 October 2026 for the authors' own review of the article. State checked that day: last amendment
A-157; 113 of 113 numbers of the text found in the sealed summaries; every sealed package verifies.

All paths are relative to the project root:

```
/Volumes/SSD Mac/PHD/Union/doctoral_joint_interception
```

## 1. What to read, in order

1. The article and the supplement (section 2).
2. For each claim, the decision document of its package (`SCIENTIFIC_DECISION_EN.md`), then its protocol
   (`PROTOCOL_EN.md`), then the numbers (`summary.json` or the file named in section 4).
3. The amendment that registered the study and the one that reported it (`governance/AMENDMENTS_EN.md`, search for
   `## A-<number>`).
4. The reviews and the responses to them (section 6), to see what was challenged and how it was answered.

## 2. The manuscript

| What | Path |
|---|---|
| **Article, source the authors edit** | `docs/manuscript/ieee/main.tex` |
| Supplement, source | `docs/manuscript/ieee/supplement.tex` |
| References | `docs/manuscript/ieee/refs.bib` (41 entries) |
| Article and supplement, PDF (IEEE template; 11 and 13 pages) | `docs/manuscript/ieee/main.pdf`, `supplement.pdf` |
| Elsevier format (29 and 27 pages) | `docs/manuscript/elsevier/main.tex`, `main.pdf`, `supplement.tex`, `supplement.pdf`, `README_FORMAT_EN.md` |
| IOP format (24 and 23 pages) | `docs/manuscript/jphysa/main.tex`, `main.pdf`, `supplement.tex`, `supplement.pdf`, `REQUIREMENTS_JPHYSA_EN.md` |
| Earlier versions | `docs/manuscript/ieee/main_v1_20261003.*` … `main_v16_20261006.*`, `supplement_v1_…` … `supplement_v7_…`, `refs_v1_…` … `refs_v3_…` |
| Figures (PDF and PNG) | `docs/manuscript/figures/F0_method.pdf` … `F7_kan_mlp_logistic_shapes.pdf` |
| Script that draws the data figures F1–F7 from the sealed results | `scripts/make_figures.py` |
| Source of the method schematic (figure 1 of the article) | `docs/manuscript/figures/F0_method.tex` |
| Reference verification logs | `docs/manuscript/REFERENCES_VERIFIED_EN.md`, `_v2_EN.md`, `_v3_EN.md`, `_v4_EN.md` (v4 is current) |
| Use of AI tools: publisher policy, declarations, provider terms | `docs/manuscript/AI_USE_COMPLIANCE_EN.md` |

The Elsevier and IOP versions are generated from the IEEE sources by `scripts/convert_manuscript_to_elsevier.py` and
`scripts/convert_manuscript_to_iop.py`; the scientific text is the same in the three. Edit one of them only.

Markers still to be removed before submission: `grep -n "pending{" docs/manuscript/ieee/main.tex` (three: repository
URL, verification of the references, AI declaration).

## 3. How to check a number yourself

```
uv run python scripts/check_manuscript_numbers.py                           # IEEE sources
uv run python scripts/check_manuscript_numbers.py docs/manuscript/elsevier  # another format
```

The script reads each sealed summary, formats the value and looks for it in the text. It tells that a number is in
the text; it does not tell that the sentence around it is right. That is what section 4 is for. Its source lists
every package, file and key it uses: `scripts/check_manuscript_numbers.py`.

To check that no sealed file changed: `uv run python scripts/package_tools.py verify --package experiments/<name>`.

## 4. Claim by claim

Every package is a folder under `experiments/`. Unless stated, its documents are `PROTOCOL_EN.md`,
`SCIENTIFIC_DECISION_EN.md` and `summary.json`, and its raw rows `results.jsonl`.

### Setting and methods (article Sections III–VI)

| Claim | Where it is defined or recorded |
|---|---|
| Operational capture (OC): the predicate and its parameters | `configs/domain_v1.json`; judge `src/joint_interception/evaluation/capture_judge.py`; tests `tests/test_capture_judge.py` |
| Split of the eleven cities; TEST opened once and spent | `contracts/SPLIT_PROTOCOL_EN.md`, `contracts/SPLIT_STATUS_EN.md`; A-110, A-111 |
| HELD-OUT B: cities fixed before download, build recipe | A-138; `assets/osm_b/MANIFEST.json`; `scripts/build_heldout_b_maps.py` |
| Evaders (random, avoidant, optimal, goal-directed, tuned) | `src/joint_interception/simulator/evader.py`; A-112 (goal-directed), A-127 (tuned) |
| Controllers: pursuit, junction ambush, PLB | `src/joint_interception/native/ambush.py`, `ambush_plus.py`, `engine.py`; A-94, A-95, A-98, A-99 |
| PLB parameters (`c2_15`) and their search | `20261002_ambush_optimization_r01` (`summary.json`, key `final_params`); A-98, A-99 |
| Family-clustered and city → family bootstraps | `scripts/addendum_reanalysis.py` (`fam_boot`); A-115, A-117 |
| Count of episodes | `provenance/EPISODE_COUNTS.json`, `scripts/count_episodes.py` |

### Finding 1 — proximity is not interception (Section VII)

| Claim in the article | Package | File and key | Amendments |
|---|---|---|---|
| Null team on seven cities: OC 3.1 % [1.5, 5.1]; 33.2 %, 23.4 %, 42.3 % under proximity | `20261004_audit_addendum_r01` (episodes, block B3); intervals in `20261004_audit_addendum_r02` | `ADDENDUM_R02_SUMMARY.json`, `N_I/null_d06`, `null_prox_5m`, `null_prox_5m_centre`, `null_prox_10m` | A-115, A-117, A-119, A-120 |
| Null team on HELD-OUT B: 1.6 %, 27.3 %, 21.4 % | `20261005_heldout_b_r01` | `summary.json`, `null_team` | A-138, A-141 |
| TEST: body gap 5 m minus OC +0.679 [0.620, 0.735]; 0.851 against 0.172 | `20261003_test_confirmation_r01`; intervals in `20261004_audit_addendum_r01` | `ADDENDUM_SUMMARY.json`, `B4/TEST_H2_prox5_minus_pc_pursuit` | A-110, A-111, A-117 |
| HELD-OUT B: +0.549 [0.476, 0.620]; 0.776 against 0.227 | `20261005_heldout_b_r01` | `summary.json`, `B2_prox5_minus_oc_pursuit_family_97.5`, `rates_primary_levels` | A-141 |
| Development cities and literature-like grids (0.85–0.96 against 0.10–0.35; 0.24 against 0.36) | `20261001_final_study_r01`, `20261001_robustness_study_r01` | their `summary.json` and decisions | A-90 to A-93 |
| First published environment (DGMARL-MVP): 999 events, none in the same lane; null 42.7 %, chaser 4.0 % | `20261005_published_env_audit_r01` | `summary.json`, `cells/<scenario>|<team>/published` | A-126, A-128 |
| …follow-up at +10 s, stop of 2 s in simulation time | `20261005_published_env_audit_r02` | `ANALYSIS.json`, `marks`, `stop_analogue` | A-133, A-134 |
| Second published environment (PEPCRL-MVP): 2,380 events (22 before an abort), none in the same lane; null 31–59 % | `20261005_published_env_pepcrl_r01` | `summary.json`, `cells/…/published` and `followup`; table: `scripts/report_published_env_pepcrl.py --latex` | A-137, A-140, A-146 |
| Third-party code that was run, unmodified | `third_party/DGMARL-MVP`, `third_party/PEPCRL-MVP` (not redistributed) | `THIRD_PARTY_NOTICES.md` | A-126, A-137 |
| Table of PLB and pursuit under each endpoint: set A | `20261005_mappo_prox_r01` | `summary.json`, `secondary/d06:plb_minus_pursuit`, `prox_5m:…`, `prox_5m_centre:…` | A-125, A-129 |
| …set B | `20261005_mappo_v3_r01` | `summary.json`, same keys | A-133, A-135 |
| …set C | `20261006_mappo_v4_r01` | `ANALYSIS.json`, `test/secondary`, same keys | A-143, A-144 |
| …on HELD-OUT B: +0.016 and +0.004 under the proximity rules | `20261005_heldout_b_r01` | `summary.json`, `plb_minus_pursuit_under_body_gap_5m`, `…_under_centre_5m` | A-141 |
| Learner trained on proximity: earlier 16-point loss; not reproduced | `20261005_mappo_prox_r01`, `20261005_mappo_prox_posthoc_r01`; repetitions `20261005_mappo_v3_r01` (arm P), `20261006_mappo_v4_r01` (arm P) | `summary.json`, `primary…`; v4: `primary_2_gap_P_final_minus_start` | A-129, A-135, A-144 |
| Hold audit: 0 escapes in 1,433 captures with pursuers held | `20261003_d06_persistence_audit_r01` | `results.jsonl`, `summary.json` | A-108, A-109 |
| …completion of 188 censored follow-ups | `20261004_audit_addendum_r01` (block B1) | `SCIENTIFIC_DECISION_EN.md` | A-115, A-117 |
| …each extended replay verified against its capture; 176 families | `20261004_audit_addendum_r02` | `ADDENDUM_R02_SUMMARY.json`, `P` | A-119, A-120 |
| …capture instants confirmed, 1,433 of 1,433 | `20261005_capture_instant_scan_r01` | `summary.json` | A-139, A-142 |
| Released if the controllers keep re-planning (8–14 %) | `20261003_d06_persistence_audit_r01` | `SCIENTIFIC_DECISION_EN.md` | A-109 |
| Active-escape probe: 15 escapes, 3 of 176 families; 115 and 1,316 episodes by request type | `20261004_audit_addendum_r03` (block AE); `20261005_ae_reclassification_r01` | `ADDENDUM_R03_SUMMARY.json`, `AE`; reclassification decision | A-121, A-122, A-125 (third review) |

### Finding 2 — containment indicators (Section VIII)

| Claim | Package | File and key | Amendments |
|---|---|---|---|
| Junction-level indicator: 82.0 % [79.1, 84.8] (seven cities), 72.5 % [66.0, 78.5] (TEST) joint escape | replays in `20261004_audit_addendum_r01` (blocks B2F, B2T); intervals in `20261004_audit_addendum_r02` | `ADDENDUM_R02_SUMMARY.json`, `N_I/B2F_junction_joint`, `B2T_junction_joint` | A-115, A-117, A-120 |
| Lane-level indicator: 8.4 % [4.7, 12.9] and 7.9 % [1.7, 15.8] | same | `N_I/B2F_lane_nv_joint`, `B2T_lane_nv_joint` | same |
| Earlier analysis (gate escapes only, 5.4–5.8 %) and why it is superseded | `20261001_final_study_r01`, `20261003_test_confirmation_r01` | their decisions | A-91, A-111, A-117 |
| Origin of the indicators | `20260930_cage_certificate_audit_r01`, `_r02`, `20261001_endpoint_validation_r01` | decisions | A-88, A-89 |

### Finding 3 — waiting ahead beats chasing (Section IX)

| Claim | Package | File and key | Amendments |
|---|---|---|---|
| TEST table (rates by evader and team size) and primary +0.145, cell interval [0.101, 0.189] | `20261003_test_confirmation_r01` | `summary.json`, `SCIENTIFIC_DECISION_EN.md` | A-110, A-111 |
| …family [0.086, 0.207] and city → family [0.074, 0.228] intervals; by city; optimal evader +0.171; PLB minus ambush +0.102 | `20261004_audit_addendum_r01` | `ADDENDUM_SUMMARY.json`, `B4/TEST_H1_plb_minus_pursuit`, `TEST_S2_optimal_plb_minus_pursuit`, `TEST_S1_plb_minus_a95` | A-117 |
| HELD-OUT B primary +0.064 [0.015, 0.114]; city → family [0.009, 0.132]; by city; optimal +0.073; PLB minus ambush +0.024 | `20261005_heldout_b_r01` | `summary.json`, `B1_…`, `by_city_plb_minus_pursuit`, `optimal_…`, `plb_minus_ambush_family_95` | A-138, A-141 |
| Difference between the two held-out sets, +0.081 [0.011, 0.149] (post hoc) | `20261006_heldout_sets_posthoc_r01` | `summary.json`, `contrasts/…/TEST_minus_HELDOUT_B_95`, `cities` | A-141 |
| Development cities: PLB minus pursuit +0.105; PLB minus ambush +0.050 (registered primary) | `20261002_ambush_optimization_r01`; intervals in `20261004_audit_addendum_r01` | `ADDENDUM_SUMMARY.json`, `B4/A99_plb_minus_pursuit`, `A99_plb_minus_a95 (A-99 primary)` | A-98, A-99, A-117 |
| Optimal evader on development cities, +0.214 | `20261003_test_confirmation_r01` (blocks OX, OS); interval in addendum r01 | `B4/OX_optimal_plb_minus_pursuit` | A-110, A-117 |
| Goal-directed evader, +0.105 | `20261003_goal_evader_r01`; interval in addendum r01 | `B4/GOAL_plb_minus_pursuit` | A-112, A-114, A-117 |
| Evader tuned against PLB, +0.128; search 0.37 → 0.27 | `20261005_tuned_evader_r01` | `summary.json`, `primary_plb_minus_pursuit_vs_tuned_family_95`, `plb_tuned_minus_reference_family_95` | A-127, A-130 |
| Coordination ablation: +0.071 [0.054, 0.089]; by evader and team size | `20261004_audit_addendum_r03` (block AB) | `ADDENDUM_R03_SUMMARY.json`, `AB` | A-121, A-122 |
| Duplicated lane targets, 49 % against 0 % (post hoc) | `20261004_mechanism_diagnostics_r01` | `SCIENTIFIC_DECISION_EN.md` | A-123 |
| Single pursuers and the independence reference | `20261003_test_confirmation_r01` (blocks TS, OS), `20261001_robustness_study_r01` | decisions | A-93, A-111 |

### What limits capture (Section X) and limitations (Section XII)

| Claim | Package | File and key | Amendments |
|---|---|---|---|
| Lanes to close at a junction; share of junctions a team can close | `docs/manuscript/junction_blockability.json`, `junction_blockability_test.json` | figure F4 | A-94 |
| Capture by number of lanes on TEST (0.43, 0.32, 0.12) | `20261003_test_confirmation_r01`; discussed in the decisions of `20261004_audit_addendum_r01` and `_r02` | recorded in `governance/AMENDMENTS_EN.md`, A-111 | A-111, A-117, A-120 |
| Oracle evader model: +0.03 to +0.04 (descriptive, not gated) | recorded in the amendment | `governance/AMENDMENTS_EN.md`, A-100 | A-100 |
| Faster pursuers, −0.07 to +0.03 | `20261002_sensitivity_r02` (`_r01` is void) | `summary.json`, decision | A-101, A-102 |
| First MAPPO study | `20261002_mappo_r01` | `summary.json`, decision, `DEVIATIONS_EN.md` | A-103, A-105 |
| Decision-commitment replication, +0.010 [−0.012, 0.033] | `20261003_commitment_r01` | `summary.json` | A-106, A-107 |
| MAPPO-v2: validation 0.36–0.37 → 0.20–0.22; primaries [−0.011, 0.059], [−0.015, 0.048] | `20261004_mappo_v2_r01` | `summary.json`, `primary` | A-116, A-118 |
| MAPPO-v3 (corrected critic input and sampling) | `20261005_mappo_v3_r01` | `summary.json` | A-133, A-135 |
| Defects of the training loop and their incidence | `20261005_v3_first_batch_reconstruction_r01`, `20261005_fifth_review_delimitation_r01` | `summary.json`; `DELIMITATION.json` | A-139, A-142 |
| MAPPO-v4 (corrected loop): 16,026 valid training episodes; primaries not met; final minus start | `20261006_mappo_v4_r01` | `ANALYSIS.json` (`training`, `test`), `summary.json`, `train_ledger.jsonl` | A-143, A-144 |
| Option PPO matched its rule | `20261001_ambush_learning_r01` | `summary.json` | A-96, A-97 |
| KAN, spline, MLP and logistic models (post hoc): TEST AUC 0.597 against 0.645–0.647 | `20261002_kan_capture_law_r01`, `20261003_kan_capture_law_test_r01`, `20261003_interpretability_r01`; recomputed in addendum r02 | `ADDENDUM_R02_SUMMARY.json`, `K` | A-104, A-113, A-120 |
| Kinematic model: +0.126, +0.140 (ballistic), +0.118 (IDM) | `20261005_kinematic_sensitivity_r01` | `summary.json`, `variants/K0`, `K1`, `K2` | A-127, A-130 |
| Background traffic: +0.094; effect of traffic on PLB | `20261005_traffic_sensitivity_r01` | `summary.json` | A-127, A-130 |
| …interaction with traffic [−0.066, 0.000] (post hoc) | `20261005_traffic_interaction_posthoc_r01` | `POSTHOC.json`, `family_95` | A-134 |
| Reproducibility: 8,966 re-runs with corrected bookkeeping; 58 traces to 1 mm | `20261004_audit_addendum_r03` (blocks RC, RP); `20261004_audit_addendum_r02` | `ADDENDUM_R03_SUMMARY.json`; decisions | A-119 to A-122 |
| Source recoverability (seven archives; 69 packages) | `provenance/PACKAGE_SOURCE_STATUS.json`, `provenance/SOURCE_ARCHIVE_*.tar.gz` | `scripts/build_source_status.py` | A-136, A-146 |
| Sealed logs altered by leftover processes and restored | `provenance/log_tails/20261006T220311Z/MANIFEST.json` | `scripts/repair_log_tails.py` | A-145 |

### Related work

| Claim | Where to check |
|---|---|
| Every reference: identity and what the article takes from it | `docs/manuscript/REFERENCES_VERIFIED_v4_EN.md` and the reference audits under `reviews/` |
| Bykov et al. (2025), read in full | `REFERENCES_VERIFIED_v4_EN.md`, last update; A-147 |
| Samanta et al., van Droffelaar et al., published environments | `reviews/20261004_third_review/REFERENCE_UPDATE.md`, `reviews/20261006_sixth_review/REFERENCE_REVIEW.md` |

## 5. Governance: decisions, registrations and results

| What | Path |
|---|---|
| Log of amendments (every registration, result, correction and decision of the Research lead; append-only) | `governance/AMENDMENTS_EN.md` (A-88 to A-157 cover the studies of the article) |
| Sealed baseline decisions (never edited) | `governance/DECISIONS_EN.md` |
| Split status of the cities | `contracts/SPLIT_STATUS_EN.md` |

Amendments by theme: endpoints and indicators A-88 to A-93; controllers A-94 to A-102; learning A-96/A-97, A-103 to
A-107, A-116, A-118, A-125, A-129, A-133, A-135, A-139, A-142 to A-144; hold audit A-108, A-109; TEST A-110, A-111;
further evaders and limits A-112 to A-114, A-127, A-130; published environments A-126, A-128, A-132, A-137, A-140;
HELD-OUT B A-138, A-141; reviews and corrections A-115 to A-124, A-125 (third review), A-133 to A-136, A-139,
A-142, A-145 to A-147; manuscript, authors and formats A-131, A-148 to A-157.

## 6. Reviews and responses

| Review | Folder | Response |
|---|---|---|
| First (4 October) | `reviews/20261004_independent_review/` | A-115, A-117; addendum r01 |
| Second | `reviews/20261004_second_review/` | A-119, A-120; addendum r02 |
| Self-audit | `docs/reports/20261004_self_audit_EN.md` | A-121 to A-124; addendum r03 |
| Third | `reviews/20261004_third_review/` | A-125 (third review) |
| Fourth (5 October) | `reviews/20261005_fourth_review/` | `docs/reports/20261005_fourth_review_response_EN.md`; A-133 to A-136 |
| Fifth | `reviews/20261005_fifth_review/` | `docs/reports/20261006_fifth_review_response_EN.md`; A-139, A-142 to A-145 |
| Sixth (6 October) | `reviews/20261006_sixth_review/` | `docs/reports/20261006_sixth_review_response_EN.md`; A-146, A-147 |

Other reports: `docs/reports/20261003_foundations_review_EN.md`, `docs/reports/20261005_items_1_2_3_EN.md`,
`docs/reports/20261006_q1_strengthening_EN.md`.

## 7. Code behind the results

| What | Path |
|---|---|
| Engine, controllers, evaders, judge | `src/joint_interception/` |
| Study runners and analyses | `scripts/` (one script per study; each package's `inputs.json` lists the scripts and source hashes it used) |
| Corrected training loop and its contract | `scripts/train_mappo_v4.py`, `src/joint_interception/rl/transitions.py`, `src/joint_interception/evaluation/capture_time.py` |
| Unit tests (528) | `tests/`; run with `uv run python -m unittest discover -s tests -t tests` |
| Standalone endpoint scorer and checklist | `audit_kit/` |

## 8. Where the article is weakest (read these first if time is short)

These are the places where a reviewer is most likely to press, with the evidence that bounds each one.

1. **Size of the controller advantage.** +0.145 on TEST and +0.064 on HELD-OUT B; PLB is not distinguishable from
   the junction ambush on the second set. `20261005_heldout_b_r01`, `20261006_heldout_sets_posthoc_r01`.
2. **What OC measures.** It admits slow following and needs no rear blocker; 15 escapes under the active probe.
   `20261004_audit_addendum_r03` (AE), `20261005_ae_reclassification_r01`.
3. **One simulator, scripted evaders.** `20261005_kinematic_sensitivity_r01`, `20261005_tuned_evader_r01`.
4. **Two published environments of one research group; their learners were not trained.**
   `20261005_published_env_audit_r01`, `_r02`, `20261005_published_env_pepcrl_r01`; A-132.
5. **Learning: a negative result with two seeds per arm, after three implementations.** `20261006_mappo_v4_r01`.
6. **Coordination ablation removes two decisions together; mechanism not isolated.**
   `20261004_audit_addendum_r03` (AB), `20261004_mechanism_diagnostics_r01`.
7. **Registration is internal (sealed packages), not externally timestamped.** `governance/AMENDMENTS_EN.md`.
8. **Novelty is in the audit of endpoints, not in stopping or in learned controllers.**
   `docs/manuscript/REFERENCES_VERIFIED_v4_EN.md`.
