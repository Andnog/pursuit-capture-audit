# Results

Every table on this page is computed from the sealed per-episode records by the library of this repository
(`tools/build_site_data.py`), and each contrast below equals the value sealed by the study to the last stored
digit. `uv run pursuit-audit recompute` repeats the comparison.

## Headline contrasts

Paired differences in success rate, with percentile bootstrap intervals that resample scenario families. The level
of each interval is in its label.

--8<-- "generated/contrasts.md"

A family is a city, a scenario and an evader behaviour; the team sizes of a family share their start positions, so
they are resampled together. The intervals over cities and families resample the four cities first: with four
cities in each set, inference about cities in general remains limited.

## Success under each endpoint

**TEST**, avoidant and random evaders:

--8<-- "generated/test_endpoints.md"

**HELD-OUT B**, avoidant and random evaders:

--8<-- "generated/heldout_b_endpoints.md"

## Operational capture by evader and team size

**TEST**

--8<-- "generated/test_by_team.md"

**HELD-OUT B**

--8<-- "generated/heldout_b_by_team.md"

## Everything else

- [Every number of the article](https://github.com/Andnog/pursuit-capture-audit/blob/main/results/ARTICLE_NUMBERS.md):
  the 113 values that the article states and that are checked against a sealed summary.
- [The evidence map](https://github.com/Andnog/pursuit-capture-audit/blob/main/results/EVIDENCE_MAP.md): for every
  claim, the package, the file and the key that hold it, and the amendments that registered and reported it.
- [The 90 sealed studies](https://github.com/Andnog/pursuit-capture-audit/blob/main/results/STUDIES.md), with the
  script and the command of each.

## How much was simulated

The studies behind the article completed 197 655 evaluation episodes. A further 16 403 were used to select
parameters or candidates and are not evaluation data; 22 455 were replays of earlier episodes for audits; and
6 483 scheduled tasks failed, almost all because the scenario generator could not place the team, which affects
every method of a condition identically. The audits of the two published environments add 2 484 episodes and
1 709 replays. `as_run/scripts/count_episodes.py` produces these counts.
