# Split status (current)

`split_manifest.json` is a historical, hashed manifest and is not rewritten. Its `CLOSED` state for TEST describes the
split before A-110.

| Split | Cities | Status (2026-10-04) |
|---|---|---|
| TRAINING | adelaide_cbd, toronto_downtown, washington_downtown, seattle_downtown | used for development, search and training |
| DEVELOPMENT | phoenix_downtown, portland_downtown, sapporo_grid | used for evaluation; informed design decisions after A-88, so not an untouched hold-out |
| TEST | chicago_loop, melbourne_cbd, salt_lake_city, minneapolis_downtown | opened once (A-110, Research lead), single-shot confirmation sealed in `experiments/20261003_test_confirmation_r01` (A-111); **spent**. Only deterministic replays completing follow-up of those sealed audits are admissible (A-115); no new TEST evaluation. |

## Added 2026-10-06 (A-138, A-141)

| Split | Cities | Status (2026-10-06) |
|---|---|---|
| HELD-OUT B | denver_downtown, vancouver_downtown, barcelona_eixample, buenos_aires_microcentro | created after every method, endpoint and analysis was frozen (A-138); networks in `assets/osm_b/`, not in `split_manifest.json`; evaluated once, sealed in `experiments/20261005_heldout_b_r01` (A-141); **spent**. No new evaluation, search, training or tuning on these cities. Re-analysis of the sealed results and deterministic replays of its recorded episodes are admissible. |

- `brisbane_cbd` was built as a reserve because of a download error, was never simulated and is not a map of the
  project (`assets/osm_b/raw/brisbane_cbd.unused.net.xml`). The other registered reserves (Kyoto, Mexico City,
  Lisbon) were never downloaded.
- The two held-out sets are reported side by side and are not pooled (A-138).
- This file was edited after `provenance/SOURCE_ARCHIVE_20261006.tar.gz` was made; the archived copy does not
  contain this section.
