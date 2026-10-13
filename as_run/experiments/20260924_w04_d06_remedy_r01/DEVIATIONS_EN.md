# Deviations

## D-1. The contract the arms ran under differs from the one at the start of the day

Both are in the package: `domain_before.json` and `domain.json`. The change is the Research lead's decision
(A-46) and is limited to the vehicle's per-class min_gap and a new frozen `simulator` section. D06's
parameters are byte-identical.

## D-2. A latent geometry defect was fixed before the judge was trusted

Front-bumper positions were being passed to centred rectangles. Found by checking the judge's input
convention before feeding it a simulator trace. Fixed in `TraciBackend.vehicle_state`, with tests showing it
cancels on one lane and does not across a junction.

## D-3. Nothing relaxed; limit respected

Safety checks on. Three of six permitted starts, no void run.
