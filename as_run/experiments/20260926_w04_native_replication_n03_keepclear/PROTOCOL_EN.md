# Protocol — N03 (EXPLORATORY): native replication under the keep-clear model variant

**Frozen before any N03 case.** Decided by the lead engineer under the Research lead's delegation (A-59), after
N01 returned `W5_PREREQUISITE_NOT_MET`. **Exploratory: it cannot meet or fail the W5 prerequisite**, which N01
decided; its purpose is to measure whether the X02 fixes (SUMO keep-clear; SUMO right of way for merges; virtual
leaders only ahead) change how often model constructions replicate natively.

Identical to N01 except: the declared model with those fixes (hashes in `inputs.json`; regression tests added;
349 tests pass), fresh seeds salt `"n03"`, **900 CPU seconds per map** (60 CPU-minutes total).

Stated in advance: a positive count here is post hoc with respect to N01 and would need a Research-lead decision
(and a pre-registered confirmation) before it could bear on W5. Development check before launch: of the 4 known
native constructions, 3 remain `CONSTRUCTED` under the variant and replicate natively; the seattle r03 one becomes
`NECESSARY_BUT_B1_NULL` under the variant.
