# Deviations

Experiment: `20260921_w03_adapter_r01`. Stage W3.

**No frozen expectation was edited. No SUMO process was started. No case was removed.**

Two process rules carried from earlier stages were followed rather than breached, and are recorded so the
correction is visible: the protocol was written **before** any W3 implementation existed (correcting W2
deviation D-06), and lint and format were run to completion **before** the run that produced this package
(correcting amendment A-09).

---

## D-13 — The module tree was extended beyond the names in the master plan

**What happened.** Master plan §4 lists `simulator/sumo_adapter.py`, `simulator/evader.py`,
`simulator/snapshot.py`, `opportunities/generator.py`, `evidence/records.py` and `evidence/provenance.py`.
This stage added two modules the plan does not name: `simulator/backend.py` and, at W2,
`domain/geometry.py`.

**Why.** `backend.py` defines the protocol that makes offline validation meaningful. Without it the
adapter would have to import `traci` directly, and the only way to test it would be to start a simulator —
which the W3 gate forbids. `geometry.py` is shared by the safety admission interface and the capture judge;
duplicating it would let the two drift apart and disagree about whether two vehicles touch.

**Effect on results.** None. The plan's tree is a required minimum, not a prohibition, and every path it
names for W3 exists. The addition is recorded rather than left for a reader to notice.

---

## D-14 — `simulator/evader.py` was not created

**What happened.** The master plan names `simulator/evader.py` as a W3 artifact. It does not exist.

**Why.** Decision D08 — the evader's public-information policy, its sustainable-continuation rule and its
endpoint semantics — is **UNRESOLVED** and belongs to the Research lead. Writing an evader now would mean
inventing the policy whose properties the master plan requires be justified, and every later result would
inherit that invention.

**Effect on results.** The adapter drives pursuers only; the evader is a passive body in the deterministic
backend. Nothing in this package depends on evader behaviour. **W4 cannot proceed without D08.**

---

## D-15 — `TraciBackend` is declared but not implemented

**What happened.** `TraciBackend` exists as a class with its interface and constraints documented, and
raises `NotImplementedError` on construction.

**Why.** Implementing it without executing it would produce untested code that looks finished; executing it
would start a SUMO process, which is a native step before its gate. Declaring it records the interface so
W4 begins from a written design rather than an improvised one, while the raise makes the unfinished state
impossible to use by accident.

**Effect on results.** The TraCI call surface is **unvalidated**. This is stated in the protocol, the
result summary, the inputs manifest and the scientific decision, rather than being left implicit.

---

## D-16 — A test runner script was added that the plan does not name

**What happened.** `scripts/run_adapter_checks.py` was added. Master plan §4 names `run_feasibility.py`,
`train_pilot.py` and others, but no W3 check runner.

**Effect on results.** None. It maps each frozen check to the test classes that decide it, so a check
cannot silently lose its evidence by a test being renamed away.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. No legacy
runtime module imported, executed, or placed on `sys.path` — the last is now checked by a test. No
inherited counter reset. No sealed package written to. No historical file, dirty file or untracked file in
either legacy runtime root modified.
