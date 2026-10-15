"""The sealed evidence, the catalogue and the headline results."""

import json
import os

import pytest

from pursuit_audit.evidence.catalogue import load_catalogue
from pursuit_audit.evidence.inventory import load_inventory
from pursuit_audit.evidence.package import EvidencePackage, packages, sha256_of
from pursuit_audit.reporting.headline import headline_checks


def test_every_present_sealed_file_matches_its_checksum(experiments):
    present = 0
    inventory = load_inventory()["packages"]
    for package in packages(experiments):
        if inventory[package.name]["kind"] == "demonstration":
            continue
        result = package.verify()
        assert result.intact, f"{package.name}: {result.mismatched}"
        present += len(result.matched)
    assert present > 800


def test_a_changed_file_is_detected(tmp_path):
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    sealed = {"files": {"summary.json": sha256_of(tmp_path / "summary.json"), "run.log": "0" * 64}}
    (tmp_path / "checksums.json").write_text(json.dumps(sealed), encoding="utf-8")
    package = EvidencePackage(str(tmp_path))
    assert package.verify().intact and not package.verify().complete
    assert package.verify().absent == ["run.log"]
    (tmp_path / "summary.json").write_text('{"changed": true}', encoding="utf-8")
    assert package.verify().mismatched == ["summary.json"]


def test_the_headline_results_follow_from_the_raw_records(experiments):
    checks = headline_checks(experiments)
    assert len(checks) == 13
    for check in checks:
        assert check.recomputed == check.sealed, check.label


def test_the_primary_results_are_those_of_the_article(experiments):
    by_label = {check.label: check.recomputed for check in headline_checks(experiments)}
    assert by_label["TEST: PLB - pursuit, family 97.5 %"] == [0.1453, 0.0855, 0.2073]
    assert by_label["HELD-OUT B: PLB - pursuit, family 97.5 %"] == [0.0643, 0.0145, 0.1139]


def test_the_catalogue_covers_every_package(experiments, snapshot):
    catalogue = {study.package: study for study in load_catalogue()}
    on_disk = {package.name for package in packages(experiments)}
    assert set(catalogue) == on_disk
    for study in catalogue.values():
        for script in (study.script, *study.analysis_scripts):
            if script:
                assert os.path.exists(os.path.join(snapshot, "scripts", script)), script


def test_every_study_behind_the_article_names_its_script():
    without = [s.package for s in load_catalogue() if s.in_article and not s.script]
    # One package is a descriptive reclassification written by hand; see its decision document.
    assert without == ["20261005_ae_reclassification_r01"]


@pytest.mark.parametrize("name", ["20261003_test_confirmation_r01", "20261005_heldout_b_r01"])
def test_the_held_out_evaluations_are_single_packages_with_records(experiments, name):
    package = EvidencePackage(os.path.join(experiments, name))
    assert package.has("PROTOCOL_EN.md") and package.has("SCIENTIFIC_DECISION_EN.md")
    assert len(package.records()) > 4000
