# Public evidence map

Paths below are relative to this public repository, not an author's private workspace.

## Manuscript and scope

- [Author manuscript](../docs/paper/manuscript.pdf), [supplement](../docs/paper/supplement.pdf), [source bundle](../docs/paper/manuscript-source.tar.gz) and [manuscript hashes](../docs/paper/MANIFEST.json).
- These are author drafts, not an accepted publication. The manuscript retains a pending companion-data DOI marker.
- [Reviewer guide](../docs/review.html), [reproduction instructions](../REPRODUCE.md), [availability](../DATA_AVAILABILITY.md).
- Internal registration is not an externally timestamped registry. Some launch-time sources are not fully recoverable.

## Claim → records → analysis

### Proximity and operational capture

Null-team calibration; identical episodes under different endpoints

- [as_run/experiments/20261004_audit_addendum_r01/results.jsonl](../as_run/experiments/20261004_audit_addendum_r01/results.jsonl)
- [as_run/experiments/20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json)
- [as_run/experiments/20261003_test_confirmation_r01/results.jsonl](../as_run/experiments/20261003_test_confirmation_r01/results.jsonl)
- [as_run/experiments/20261005_heldout_b_r01/summary.json](../as_run/experiments/20261005_heldout_b_r01/summary.json)
- Analysis: [src/pursuit_audit/reporting/headline.py](../src/pursuit_audit/reporting/headline.py)

```bash
uv run pursuit-audit recompute
```

Held-out contrasts are independently recomputed. Null-team uncertainty is read from sealed summaries (N_I).

### Published environments

Capture events in DGMARL-MVP and PEPCRL-MVP

- [as_run/experiments/20261005_published_env_audit_r01/summary.json](../as_run/experiments/20261005_published_env_audit_r01/summary.json)
- [as_run/experiments/20261005_published_env_pepcrl_r01/summary.json](../as_run/experiments/20261005_published_env_pepcrl_r01/summary.json)
- [THIRD_PARTY.md](../THIRD_PARTY.md)
- Analysis: [as_run/scripts/analyse_published_env.py](../as_run/scripts/analyse_published_env.py)

```bash
uv run python tools/build_site_data.py --check
```

The site cross-check reads sealed summaries. A new simulation needs the upstream repositories at the recorded commits; published learners were not trained.

### Persistence and active escape

Hold audit, completed follow-up and lane-change probe

- [as_run/experiments/20261003_d06_persistence_audit_r01/results.jsonl](../as_run/experiments/20261003_d06_persistence_audit_r01/results.jsonl)
- [as_run/experiments/20261004_audit_addendum_r01/ADDENDUM_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r01/ADDENDUM_SUMMARY.json)
- [as_run/experiments/20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json)
- [as_run/experiments/20261004_audit_addendum_r03/ADDENDUM_R03_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r03/ADDENDUM_R03_SUMMARY.json)
- Analysis: [as_run/scripts/audit_d06_persistence.py](../as_run/scripts/audit_d06_persistence.py)

```bash
cd as_run && uv run python scripts/audit_d06_persistence.py --package /tmp/pursuit_review_replay --limit 6 --workers 2
```

Blocks B1 and P complete/check follow-up; AE is the active probe. Six local replays matched on 14 October 2026, not a fresh repeat of all captures.

### Containment indicators

Joint escape through a gate or out of the network within 60 seconds

- [as_run/experiments/20261004_audit_addendum_r01/results.jsonl](../as_run/experiments/20261004_audit_addendum_r01/results.jsonl)
- [as_run/experiments/20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json)
- Analysis: [as_run/scripts/addendum_reanalysis.py](../as_run/scripts/addendum_reanalysis.py)

```bash
uv run python tools/build_site_data.py --check
```

Site values read the corrected N_I/B2F and B2T summaries. Earlier gate-only analyses remain in the record and are superseded.

### Held-out controller comparisons

PLB versus pursuit and the simpler junction ambush, reported separately for TEST and HELD-OUT B

- [as_run/experiments/20261003_test_confirmation_r01/results.jsonl](../as_run/experiments/20261003_test_confirmation_r01/results.jsonl)
- [as_run/experiments/20261004_audit_addendum_r01/ADDENDUM_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r01/ADDENDUM_SUMMARY.json)
- [as_run/experiments/20261005_heldout_b_r01/results.jsonl](../as_run/experiments/20261005_heldout_b_r01/results.jsonl)
- [as_run/experiments/20261005_heldout_b_r01/summary.json](../as_run/experiments/20261005_heldout_b_r01/summary.json)
- Analysis: [src/pursuit_audit/statistics/contrasts.py](../src/pursuit_audit/statistics/contrasts.py)

```bash
uv run pursuit-audit recompute
```

Independent raw-record recomputation includes family and city–family intervals. No clear PLB advantage over junction ambush was established on HELD-OUT B.

### Coordination ablation

Joint lane assignment versus independent choices

- [as_run/experiments/20261004_audit_addendum_r03/results.jsonl](../as_run/experiments/20261004_audit_addendum_r03/results.jsonl)
- [as_run/experiments/20261004_audit_addendum_r03/ADDENDUM_R03_SUMMARY.json](../as_run/experiments/20261004_audit_addendum_r03/ADDENDUM_R03_SUMMARY.json)
- Analysis: [as_run/scripts/addendum_r03_reanalysis.py](../as_run/scripts/addendum_r03_reanalysis.py)

```bash
uv run python tools/build_site_data.py --check
```

Block AB removes both the joint junction ambush and exclusion of lanes already assigned to teammates. The contrast measures this bundle.

### Learning and corrected implementations

Fine-tuning relative to imitation; final corrected training loop

- [as_run/experiments/20261006_mappo_v4_r01/ANALYSIS.json](../as_run/experiments/20261006_mappo_v4_r01/ANALYSIS.json)
- [as_run/experiments/20261006_mappo_v4_r01/PROTOCOL_EN.md](../as_run/experiments/20261006_mappo_v4_r01/PROTOCOL_EN.md)
- [as_run/experiments/20261006_mappo_v4_r01/SCIENTIFIC_DECISION_EN.md](../as_run/experiments/20261006_mappo_v4_r01/SCIENTIFIC_DECISION_EN.md)
- Analysis: [as_run/scripts/analyse_mappo_v4.py](../as_run/scripts/analyse_mappo_v4.py)

```bash
uv run python tools/build_site_data.py --check
```

Site values read the final sealed analysis. Non-significance does not establish equivalence. Training states require the companion archive.

### Robustness and scope

Alternative kinematics, background traffic and an evader tuned against PLB

- [as_run/experiments/20261005_kinematic_sensitivity_r01/summary.json](../as_run/experiments/20261005_kinematic_sensitivity_r01/summary.json)
- [as_run/experiments/20261005_traffic_sensitivity_r01/summary.json](../as_run/experiments/20261005_traffic_sensitivity_r01/summary.json)
- [as_run/experiments/20261005_tuned_evader_r01/summary.json](../as_run/experiments/20261005_tuned_evader_r01/summary.json)
- Analysis: [tools/build_site_data.py](../tools/build_site_data.py)

```bash
uv run python tools/build_site_data.py --check
```

These are sensitivity studies inside SUMO, not independent simulators or field validation.

## Methods and governance

- [Endpoint parameters](../as_run/configs/domain_v1.json) and [judge](../as_run/src/joint_interception/evaluation/capture_judge.py).
- [Split protocol](../as_run/contracts/SPLIT_PROTOCOL_EN.md), [current split status](../as_run/contracts/SPLIT_STATUS_EN.md) and [HELD-OUT B manifest](../as_run/assets/osm_b/MANIFEST.json).
- [Amendments](../as_run/governance/AMENDMENTS_EN.md) preserve registrations, corrections and post hoc analyses.
- [113 numerical checks](ARTICLE_NUMBERS.md) and [study commands](STUDIES.md). Pattern matching against manuscript text does not establish semantic correctness.

## Package inventory and historical source recovery

89 sealed packages and one unsealed demonstration directory. A protocol-file label only describes the files present; it does not itself establish preregistration. Historical recovery labels are taken from PACKAGE_SOURCE_STATUS.json: partial sometimes means only a manifest is absent from historical archives. Read its per-file explanations.

| Package | Kind | Protocol location | Historical source recovery |
|---|---|---|---|
| `20260920_w01_finite_examples_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w00_novelty_closure_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w00_novelty_closure_r02` | sealed | protocol file | not recorded in source inventory |
| `20260921_w00_novelty_closure_r03` | sealed | protocol file | not recorded in source inventory |
| `20260921_w00_novelty_closure_r04` | sealed | protocol file | not recorded in source inventory |
| `20260921_w02_contracts_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w03_adapter_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w03_evader_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w04_arrival_model_prereq_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w04_arrival_model_prereq_r02` | sealed | protocol file | not recorded in source inventory |
| `20260921_w04_constructive_arrival_r01` | sealed | protocol file | not recorded in source inventory |
| `20260921_w04_interpreter_provenance_r01` | sealed | protocol file | partially recoverable |
| `20260922_w00_open_access_reads_r01` | sealed | protocol file | not recorded in source inventory |
| `20260922_w04_fresh_start_determinism_r01` | sealed | protocol file | partially recoverable |
| `20260922_w04_interaction_fixed_point_r01` | sealed | protocol file | partially recoverable |
| `20260922_w04_traci_first_execution_r01` | sealed | protocol file | partially recoverable |
| `20260922_w05_constructive_on_network_r01` | sealed | protocol file | partially recoverable |
| `20260923_w05_constructive_replication_r01` | sealed | protocol file | partially recoverable |
| `20260924_w04_d06_remedy_r01` | sealed | protocol file | partially recoverable |
| `20260924_w04_o22_collision_semantics_r01` | sealed | protocol file | partially recoverable |
| `20260924_w04_o27_constructions_r01` | sealed | protocol file | partially recoverable |
| `20260924_w05_deficit_mechanism_r01` | sealed | protocol file | fully recoverable |
| `20260924_w05_signal_aware_approach_r01` | sealed | protocol file | partially recoverable |
| `20260925_w04_o27_constructions_r02` | sealed | protocol file | partially recoverable |
| `20260926_w04_capture_failure_modes_x02` | sealed | protocol file | not recorded in source inventory |
| `20260926_w04_capture_robustness_x01` | sealed | protocol file | not recorded in source inventory |
| `20260926_w04_evader_divergence_x03` | sealed | protocol file | not recorded in source inventory |
| `20260926_w04_model_validation_r01` | sealed | protocol file | partially recoverable |
| `20260926_w04_native_replication_n01` | sealed | protocol file | partially recoverable |
| `20260926_w04_native_replication_n02_optimal` | sealed | protocol file | partially recoverable |
| `20260926_w04_native_replication_n03_keepclear` | sealed | protocol file | partially recoverable |
| `20260926_w04_native_replication_n05_interpolated` | sealed | protocol file | partially recoverable |
| `20260926_w04_o27_constructions_r03` | sealed | protocol file | partially recoverable |
| `20260927_native_ladder_stageB2_margin_r01` | sealed | protocol file | partially recoverable |
| `20260927_native_ladder_stageB3_probability_r01` | sealed | protocol file | partially recoverable |
| `20260927_native_ladder_stageB_r01` | sealed | protocol file | partially recoverable |
| `20260929_f1_caging_feasibility_r01` | sealed | protocol file | partially recoverable |
| `20260929_f1_caging_feasibility_r02` | sealed | protocol file | partially recoverable |
| `20260929_f2_caging_sweep_r01` | sealed | protocol file | partially recoverable |
| `20260929_f3_caging_confirm_real_r01` | sealed | protocol file | partially recoverable |
| `20260929_f4_caging_confirm_admission_r01` | sealed | protocol file | partially recoverable |
| `20260929_f4_caging_confirm_admission_r02` | sealed | protocol file | partially recoverable |
| `20260929_marl_pilot_r01` | sealed | protocol file | partially recoverable |
| `20260929_marl_pilot_r02` | sealed | protocol file | partially recoverable |
| `20260929_native_ladder_stageB4_pooled_r01` | sealed | protocol file | partially recoverable |
| `20260929_native_ladder_stageB5_idlefix_r01` | sealed | protocol file | partially recoverable |
| `20260930_cage_certificate_audit_r01` | sealed | protocol file | partially recoverable |
| `20260930_cage_certificate_audit_r02` | sealed | protocol file | partially recoverable |
| `20260930_marl_pilot_r03` | sealed | protocol file | partially recoverable |
| `20260930_marl_trap_pilot_r04` | sealed | protocol file | partially recoverable |
| `20260930_trap_endpoint_r01` | sealed | protocol file | partially recoverable |
| `20261001_ambush_learning_r01` | sealed | protocol file | partially recoverable |
| `20261001_ambush_study_r01` | sealed | protocol file | partially recoverable |
| `20261001_endpoint_validation_r01` | sealed | protocol file | partially recoverable |
| `20261001_final_study_r01` | sealed | protocol file | partially recoverable |
| `20261001_robustness_study_r01` | sealed | protocol file | partially recoverable |
| `20261002_ambush_optimization_r01` | sealed | protocol file | partially recoverable |
| `20261002_kan_capture_law_r01` | sealed | see amendments / decision | not recorded in source inventory |
| `20261002_mappo_r01` | sealed | protocol file | partially recoverable |
| `20261002_sensitivity_r01` | sealed | protocol file | partially recoverable |
| `20261002_sensitivity_r02` | sealed | protocol file | partially recoverable |
| `20261003_commitment_r01` | sealed | protocol file | partially recoverable |
| `20261003_d06_persistence_audit_r01` | sealed | protocol file | partially recoverable |
| `20261003_goal_evader_r01` | sealed | protocol file | partially recoverable |
| `20261003_interpretability_r01` | sealed | see amendments / decision | partially recoverable |
| `20261003_kan_capture_law_test_r01` | sealed | see amendments / decision | not recorded in source inventory |
| `20261003_method_gifs` | demonstration | see amendments / decision | not recorded in source inventory |
| `20261003_test_confirmation_r01` | sealed | protocol file | partially recoverable |
| `20261004_audit_addendum_r01` | sealed | protocol file | partially recoverable |
| `20261004_audit_addendum_r02` | sealed | protocol file | fully recoverable |
| `20261004_audit_addendum_r03` | sealed | protocol file | partially recoverable |
| `20261004_mappo_v2_r01` | sealed | protocol file | partially recoverable |
| `20261004_mechanism_diagnostics_r01` | sealed | see amendments / decision | fully recoverable |
| `20261005_ae_reclassification_r01` | sealed | see amendments / decision | not recorded in source inventory |
| `20261005_capture_instant_scan_r01` | sealed | protocol file | fully recoverable |
| `20261005_fifth_review_delimitation_r01` | sealed | protocol file | fully recoverable |
| `20261005_heldout_b_r01` | sealed | protocol file | partially recoverable |
| `20261005_kinematic_sensitivity_r01` | sealed | protocol file | fully recoverable |
| `20261005_mappo_prox_posthoc_r01` | sealed | see amendments / decision | not recorded in source inventory |
| `20261005_mappo_prox_r01` | sealed | protocol file | partially recoverable |
| `20261005_mappo_v3_r01` | sealed | protocol file | fully recoverable |
| `20261005_published_env_audit_r01` | sealed | protocol file | fully recoverable |
| `20261005_published_env_audit_r02` | sealed | protocol file | fully recoverable |
| `20261005_published_env_pepcrl_r01` | sealed | protocol file | fully recoverable |
| `20261005_traffic_interaction_posthoc_r01` | sealed | see amendments / decision | not recorded in source inventory |
| `20261005_traffic_sensitivity_r01` | sealed | protocol file | fully recoverable |
| `20261005_tuned_evader_r01` | sealed | protocol file | fully recoverable |
| `20261005_v3_first_batch_reconstruction_r01` | sealed | protocol file | fully recoverable |
| `20261006_heldout_sets_posthoc_r01` | sealed | protocol file | partially recoverable |
| `20261006_mappo_v4_r01` | sealed | protocol file | fully recoverable |

Private review correspondence, earlier manuscript drafts and all historical launch-time source versions are not provided here. No exact rerun claim is made for every historical package.
