"""The catalogue of studies: which package holds what, and how to run it again."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources


@dataclass(frozen=True)
class Option:
    """One command-line option of the script of a study."""

    name: str
    default: str | None = None
    flag: bool = False
    help: str | None = None


@dataclass(frozen=True)
class Study:
    """One catalogue entry: a study, an analysis or a demonstration.

    Attributes:
        package: Name of the evidence package, which starts with its date.
        date: Date of the package.
        title: Title of its protocol.
        amendment: The amendment of the registration record that introduced it.
        registered: Whether its protocol says that it was registered before the runs.
        script: The script that produced it, under ``as_run/scripts``.
        command: The command that runs that script again, from ``as_run``.
        options: The options that the script accepts.
        analysis_scripts: Scripts that analysed the package after the runs.
        needs_simulator: Whether running it again needs SUMO.
        needs_third_party_code: Whether it runs the released code of another study.
        in_article: Whether the article rests on it.
        archive_only_files: Number of its files that are only in the data archive.
        archive_only_bytes: Size of those files.
    """

    package: str
    date: str
    title: str
    amendment: str | None = None
    registered: bool = False
    script: str | None = None
    command: str | None = None
    options: tuple[Option, ...] = field(default_factory=tuple)
    analysis_scripts: tuple[str, ...] = field(default_factory=tuple)
    needs_simulator: bool = False
    needs_third_party_code: bool = False
    in_article: bool = False
    archive_only_files: int = 0
    archive_only_bytes: int = 0


def load_catalogue() -> list[Study]:
    """Return every study, in date order."""
    text = resources.files(__package__).joinpath("studies.json").read_text(encoding="utf-8")
    studies = []
    for raw in json.loads(text):
        options = tuple(Option(**option) for option in raw.pop("options", []))
        analysis = tuple(raw.pop("analysis_scripts", []))
        studies.append(Study(options=options, analysis_scripts=analysis, **raw))
    return studies
