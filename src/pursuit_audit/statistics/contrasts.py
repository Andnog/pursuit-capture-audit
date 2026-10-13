"""Paired contrasts between methods, from the per-episode records of an evidence package.

A record key reads ``block|method|city|scenario|seed|evader|team``. Rates are averaged over
simulator seeds within a cell (a city, a scenario, an evader behaviour and a team size), and two
methods are compared cell by cell, on the cells that both completed.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

CellKey = tuple[str, int, str, int]  # city, scenario, evader behaviour, team size
FamilyKey = tuple[str, int, str]  # city, scenario, evader behaviour


@dataclass(frozen=True)
class EpisodeKey:
    """The parsed key of one episode record."""

    block: str
    method: str
    city: str
    scenario: int
    seed: str
    evader: str
    team: int

    @classmethod
    def parse(cls, key: str) -> EpisodeKey:
        """Parse ``block|method|city|scenario|seed|evader|team``."""
        block, method, city, scenario, seed, evader, team = key.split("|")
        return cls(block, method, city, int(scenario), seed, evader, int(team))

    @property
    def cell(self) -> CellKey:
        """Return the cell that the episode belongs to."""
        return (self.city, self.scenario, self.evader, self.team)


def cell_means(
    records: Mapping[str, Mapping], field: str, block: str, method: str
) -> dict[CellKey, float]:
    """Average a field over simulator seeds, per cell, for one block and one method.

    Records of failed episodes (those that carry a ``failed`` entry) and records without the
    field are left out.
    """
    values: dict[CellKey, list[float]] = {}
    for key, record in records.items():
        if "failed" in record or field not in record:
            continue
        if not key.startswith(f"{block}|{method}|"):
            continue
        values.setdefault(EpisodeKey.parse(key).cell, []).append(float(record[field]))
    return {cell: sum(v) / len(v) for cell, v in values.items()}


def paired_differences(
    first: Mapping[CellKey, float],
    second: Mapping[CellKey, float],
    evaders: Collection[str],
    city: str | None = None,
    team: int | None = None,
) -> dict[FamilyKey, list[float]]:
    """Return ``first - second`` on shared cells, grouped by family.

    Args:
        first: Cell means of the first method.
        second: Cell means of the second method.
        evaders: Evader behaviours to keep.
        city: Keep one city only.
        team: Keep one team size only.
    """
    families: dict[FamilyKey, list[float]] = {}
    for cell in sorted(set(first) & set(second)):
        cell_city, _scenario, cell_evader, cell_team = cell
        if cell_evader not in evaders:
            continue
        if city not in (None, cell_city) or team not in (None, cell_team):
            continue
        families.setdefault(cell[:3], []).append(first[cell] - second[cell])
    return families


def pooled_rate(means: Mapping[CellKey, float], evaders: Collection[str]) -> float | None:
    """Average the cell means of the given evader behaviours."""
    values = [value for cell, value in means.items() if cell[2] in evaders]
    return round(sum(values) / len(values), 4) if values else None
