# Scientific decision — cage certificate audit r01

**Verdict: VOID (implementation defect in M1).** The protocol defines an escape as the evader *entering* an edge whose
origin junction was a gate at certification. The code also counted the edge the evader was already on at
certification; that edge's rear junction is often a gate (reachable through a U-turn), so many "escapes" were
recorded at 0 s. Reported numbers (M1 0.785) are not interpretable. Other measures are unaffected but are re-run in
r02 with the fix, the same protocol, the same population and the same seeds. Kept for the record.
