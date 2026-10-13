# Reclassification of the active-escape probe (A-125, offline, sealed r03 rows read only)

Third independent review, finding R3-1: the r03 analysis grouped captures by whether a lane-change request was ever
recorded, and described the groups as "with / without an adjacent onward lane". That is not a geometric inventory.

| Recorded probe requests | Episodes | Escapes |
|---|---|---|
| Lane-change requests | 115 | 15 |
| Reroute requests only | 1,316 | 0 |
| Control errors only (inconclusive) | 2 | 0 |
| Total | 1,433 | 15 |

The two control-error episodes are `AE|test|plus_opt|portland_downtown|13|109513|RANDOM|7` and
`AE|test|plus_opt|portland_downtown|13|9513|RANDOM|7`, with 61 errors each and no successful request. They are not
replaced.

**Erratum to the sealed r03 decision text.** The statements "none of the 1,318 captures without one escaped" and "a
stricter variant, OC with no free adjacent onward lane, had no observed escape" are withdrawn. The supported statement
is: 15 escapes were observed under the active probe; lane-change requests were recorded in 115 episodes; two episodes
are inconclusive; and the absence of a recorded request does not prove that no adjacent exit existed.
