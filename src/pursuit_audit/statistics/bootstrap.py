"""Family-clustered bootstrap intervals for paired differences.

Episodes of one scenario family (a city, a scenario and an evader behaviour) share their starts
across team sizes and simulator seeds, so they are not independent observations. Intervals
therefore resample families, and every cell of a family moves together. The two-stage variant
resamples cities first and families within them.

The procedure reproduces the sealed intervals of the article exactly: the same generator, the
same order of draws and the same percentile indices as the code that produced them.
"""

from __future__ import annotations

import random
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 11
_ROUNDING = 4


@dataclass(frozen=True)
class Interval:
    """A point estimate with a percentile bootstrap interval."""

    estimate: float
    low: float
    high: float

    def as_list(self) -> list[float]:
        """Return ``[estimate, low, high]``, the form stored in the sealed summaries."""
        return [self.estimate, self.low, self.high]

    def excludes_zero(self) -> bool:
        """Tell whether the interval lies entirely on one side of zero."""
        return self.low > 0.0 or self.high < 0.0


def family_bootstrap(
    differences: Mapping[Hashable, Sequence[float]],
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
    two_stage: bool = False,
) -> Interval | None:
    """Estimate a mean paired difference with an interval that resamples families.

    Args:
        differences: Cell differences by family. A family key is a tuple whose first element is
            the city, which the two-stage variant uses.
        resamples: Number of bootstrap resamples.
        seed: Seed of the generator.
        alpha: One minus the level of the interval (0.05 gives 95 %, 0.025 gives 97.5 %).
        two_stage: Resample cities, then families within each drawn city.

    Returns:
        The estimate and its interval, rounded as in the sealed summaries, or ``None`` if there is
        no difference to average.
    """
    keys = sorted(differences)
    values = [x for key in keys for x in differences[key]]
    if not values:
        return None
    generator = random.Random(seed)
    by_city: dict[Hashable, list[Hashable]] = {}
    for key in keys:
        by_city.setdefault(key[0], []).append(key)
    cities = sorted(by_city)
    means = []
    for _ in range(resamples):
        sample: list[float] = []
        if two_stage:
            # A city is drawn, then its families, then the next city: the order of the draws is
            # part of the procedure, since they share one generator.
            for _ in cities:
                families = by_city[generator.choice(cities)]
                for _ in families:
                    sample += differences[generator.choice(families)]
        else:
            for _ in keys:
                sample += differences[generator.choice(keys)]
        means.append(sum(sample) / len(sample))
    means.sort()
    low_index = int(alpha / 2 * resamples)
    high_index = int((1 - alpha / 2) * resamples) - 1
    return Interval(
        round(sum(values) / len(values), _ROUNDING),
        round(means[low_index], _ROUNDING),
        round(means[high_index], _ROUNDING),
    )
