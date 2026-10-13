"""Recompute the headline results of the article from the per-episode records.

The sealed summaries were written by the scripts of the studies. This module starts again from
the raw records of the two held-out evaluations and computes the same contrasts with the
library's own statistics. Agreement to the last stored digit is the check that the clean code and
the code that ran describe the same analysis.
"""

from __future__ import annotations

import os
from collections.abc import Collection
from dataclasses import dataclass

from ..evidence.package import EvidencePackage
from ..statistics.bootstrap import family_bootstrap
from ..statistics.contrasts import cell_means, paired_differences

PLB, AMBUSH, PURSUIT = "plus_opt", "ambush_a95", "pursuit"
OC, BODY_GAP, CENTRE = "d06", "prox_5m", "prox_5m_centre"
PRIMARY_EVADERS = ("AVOIDANT", "RANDOM")
OPTIMAL = ("OPTIMAL_ESCAPE",)
ALL_EVADERS = (*PRIMARY_EVADERS, *OPTIMAL)

TEST_PACKAGE = "20261003_test_confirmation_r01"
TEST_REANALYSIS = "20261004_audit_addendum_r01"
HELDOUT_B_PACKAGE = "20261005_heldout_b_r01"


@dataclass(frozen=True)
class Check:
    """One recomputed quantity next to its sealed value."""

    label: str
    recomputed: list[float] | None
    sealed: list[float] | None

    @property
    def agrees(self) -> bool:
        """Tell whether the recomputed value equals the sealed one."""
        return self.recomputed == self.sealed


class HeldOutEvaluation:
    """The paired contrasts of one single-shot evaluation, from its records."""

    def __init__(self, package: EvidencePackage, block: str) -> None:
        self._records = package.records()
        self._block = block
        self._cache: dict[tuple[str, str], dict] = {}

    def _cells(self, field: str, method: str) -> dict:
        key = (field, method)
        if key not in self._cache:
            self._cache[key] = cell_means(self._records, field, self._block, method)
        return self._cache[key]

    def contrast(
        self,
        first: tuple[str, str],
        second: tuple[str, str],
        evaders: Collection[str] = PRIMARY_EVADERS,
        alpha: float = 0.05,
        two_stage: bool = False,
    ) -> list[float] | None:
        """Return ``[estimate, low, high]`` for ``first - second``.

        Args:
            first: The ``(method, field)`` of the first term.
            second: The ``(method, field)`` of the second term.
            evaders: Evader behaviours pooled in the contrast.
            alpha: One minus the level of the interval.
            two_stage: Resample cities, then families.
        """
        differences = paired_differences(
            self._cells(first[1], first[0]), self._cells(second[1], second[0]), evaders
        )
        interval = family_bootstrap(differences, alpha=alpha, two_stage=two_stage)
        return interval.as_list() if interval else None


def _test_checks(root: str) -> list[Check]:
    evaluation = HeldOutEvaluation(EvidencePackage(os.path.join(root, TEST_PACKAGE)), "TX")
    sealed = EvidencePackage(os.path.join(root, TEST_REANALYSIS)).summary("ADDENDUM_SUMMARY.json")
    sealed = sealed["B4"]
    plb, ambush, pursuit = (PLB, OC), (AMBUSH, OC), (PURSUIT, OC)
    primary = sealed["TEST_H1_plb_minus_pursuit"]
    gap = sealed["TEST_H2_prox5_minus_pc_pursuit"]
    return [
        Check(
            "TEST: PLB - pursuit, family 97.5 %",
            evaluation.contrast(plb, pursuit, alpha=0.025),
            primary["family_97.5"],
        ),
        Check(
            "TEST: PLB - pursuit, family 95 %",
            evaluation.contrast(plb, pursuit),
            primary["family_95"],
        ),
        Check(
            "TEST: PLB - pursuit, city and family 95 %",
            evaluation.contrast(plb, pursuit, two_stage=True),
            primary["city_family_95"],
        ),
        Check(
            "TEST: PLB - junction ambush, family 95 %",
            evaluation.contrast(plb, ambush),
            sealed["TEST_S1_plb_minus_a95"]["family_95"],
        ),
        Check(
            "TEST: PLB - pursuit, optimal evader, family 95 %",
            evaluation.contrast(plb, pursuit, evaders=OPTIMAL),
            sealed["TEST_S2_optimal_plb_minus_pursuit"]["family_95"],
        ),
        Check(
            "TEST: body gap 5 m - OC, pursuit team, family 97.5 %",
            evaluation.contrast((PURSUIT, BODY_GAP), pursuit, evaders=ALL_EVADERS, alpha=0.025),
            gap["family_97.5"],
        ),
    ]


def _heldout_b_checks(root: str) -> list[Check]:
    package = EvidencePackage(os.path.join(root, HELDOUT_B_PACKAGE))
    evaluation = HeldOutEvaluation(package, "HB")
    sealed = package.summary()
    plb, ambush, pursuit = (PLB, OC), (AMBUSH, OC), (PURSUIT, OC)
    return [
        Check(
            "HELD-OUT B: PLB - pursuit, family 97.5 %",
            evaluation.contrast(plb, pursuit, alpha=0.025),
            sealed["B1_plb_minus_pursuit_family_97.5"],
        ),
        Check(
            "HELD-OUT B: PLB - pursuit, city and family 95 %",
            evaluation.contrast(plb, pursuit, two_stage=True),
            sealed["B1_city_family_95"],
        ),
        Check(
            "HELD-OUT B: body gap 5 m - OC, pursuit team, family 97.5 %",
            evaluation.contrast((PURSUIT, BODY_GAP), pursuit, alpha=0.025),
            sealed["B2_prox5_minus_oc_pursuit_family_97.5"],
        ),
        Check(
            "HELD-OUT B: PLB - junction ambush, family 95 %",
            evaluation.contrast(plb, ambush),
            sealed["plb_minus_ambush_family_95"],
        ),
        Check(
            "HELD-OUT B: PLB - pursuit, optimal evader, family 95 %",
            evaluation.contrast(plb, pursuit, evaders=OPTIMAL),
            sealed["optimal_plb_minus_pursuit_family_95"],
        ),
        Check(
            "HELD-OUT B: PLB - pursuit under the 5 m body-gap rule",
            evaluation.contrast((PLB, BODY_GAP), (PURSUIT, BODY_GAP)),
            sealed["plb_minus_pursuit_under_body_gap_5m"],
        ),
        Check(
            "HELD-OUT B: PLB - pursuit under the 5 m centre-distance rule",
            evaluation.contrast((PLB, CENTRE), (PURSUIT, CENTRE)),
            sealed["plb_minus_pursuit_under_centre_5m"],
        ),
    ]


def headline_checks(experiments_root: str) -> list[Check]:
    """Recompute the headline contrasts of both held-out evaluations.

    Args:
        experiments_root: The directory of the sealed packages (``as_run/experiments``).
    """
    return _test_checks(experiments_root) + _heldout_b_checks(experiments_root)
