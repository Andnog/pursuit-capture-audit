import json
import shutil

import pytest

from pursuit_audit.cli import main
from pursuit_audit.evidence.inventory import verify_snapshot
from pursuit_audit.evidence.package import EvidencePackage, sha256_of


@pytest.fixture
def copy_fixture(tmp_path):
    snapshot = tmp_path / "as_run"
    package = snapshot / "experiments" / "study"
    package.mkdir(parents=True)
    (package / "results.jsonl").write_text('{"key":"one"}\n')
    heavy = package / "state.pkl"
    heavy.write_bytes(b"fixture, not a pickle")
    files = {name: sha256_of(package / name) for name in ("results.jsonl", "state.pkl")}
    seal = package / "checksums.json"
    seal.write_text(json.dumps({"files": files}))
    manifest = snapshot / "SNAPSHOT.json"
    manifest.write_text(
        json.dumps(
            {
                "archive_only": [
                    {"path": "experiments/study/state.pkl", "sha256": files["state.pkl"]}
                ]
            }
        )
    )
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "snapshot_sha256": sha256_of(manifest),
                "packages": {"study": {"kind": "sealed", "seal_sha256": sha256_of(seal)}},
            }
        )
    )
    heavy.unlink()
    return snapshot, package, inventory


def check(fixture, complete=False):
    snapshot, _, inventory = fixture
    return verify_snapshot(str(snapshot), complete=complete, inventory_path=str(inventory))


def test_only_listed_absences_pass_and_complete_requires_them(copy_fixture):
    assert not check(copy_fixture).errors
    assert check(copy_fixture, complete=True).errors
    _, package, _ = copy_fixture
    (package / "state.pkl").write_bytes(b"fixture, not a pickle")
    assert not check(copy_fixture, complete=True).errors
    (package / "state.pkl").write_bytes(b"changed")
    assert check(copy_fixture).errors


@pytest.mark.parametrize("missing", ["results.jsonl", "checksums.json"])
def test_missing_required_evidence_is_a_cli_failure(copy_fixture, missing):
    snapshot, package, inventory = copy_fixture
    (package / missing).unlink()
    assert main(["verify", "--snapshot", str(snapshot), "--inventory", str(inventory)]) == 1


def test_missing_whole_package_fails(copy_fixture):
    _, package, _ = copy_fixture
    shutil.rmtree(package)
    assert "missing package: study" in check(copy_fixture).errors


def test_removing_an_entry_from_the_seal_does_not_hide_loss(copy_fixture):
    _, package, _ = copy_fixture
    (package / "results.jsonl").unlink()
    seal = package / "checksums.json"
    data = json.loads(seal.read_text())
    del data["files"]["results.jsonl"]
    seal.write_text(json.dumps(data))
    assert any("differs from the inventory" in e for e in check(copy_fixture).errors)


@pytest.mark.parametrize(
    "seal", ["{}", '{"files": []}', '{"files": {}}', "not json", '{"files": {"../escape": "bad"}}']
)
def test_invalid_seal_never_passes(tmp_path, seal):
    (tmp_path / "checksums.json").write_text(seal)
    result = EvidencePackage(str(tmp_path)).verify()
    assert not result.intact and result.errors


def test_a_changed_omissions_manifest_cannot_hide_a_required_file(copy_fixture):
    snapshot, _, _ = copy_fixture
    manifest = snapshot / "SNAPSHOT.json"
    manifest.write_text('{"archive_only": []}')
    assert check(copy_fixture).errors


def test_public_snapshot_passes_but_is_not_complete(snapshot):
    result = verify_snapshot(snapshot)
    assert not result.errors
    assert (result.matched, result.absent, result.archive_absent) == (832, 126, 137)
    assert verify_snapshot(snapshot, complete=True).errors


def test_unsealed_companion_uses_explicit_inventory_hash(copy_fixture):
    snapshot, package, inventory = copy_fixture
    extra = package / "demo.gif"
    extra.write_bytes(b"unsealed demonstration")
    relative = "experiments/study/demo.gif"
    manifest = snapshot / "SNAPSHOT.json"
    data = json.loads(manifest.read_text())
    data["archive_only"].append({"path": relative, "sha256": None})
    manifest.write_text(json.dumps(data))
    reference = json.loads(inventory.read_text())
    reference["snapshot_sha256"] = sha256_of(manifest)
    inventory.write_text(json.dumps(reference))
    assert check(copy_fixture).errors
    reference["companion_hashes"] = {relative: sha256_of(extra)}
    inventory.write_text(json.dumps(reference))
    assert not check(copy_fixture).errors
    extra.write_bytes(b"changed demonstration")
    assert any("companion file differs" in e for e in check(copy_fixture).errors)


def test_historical_source_reference_must_stay_inside_snapshot(copy_fixture):
    snapshot, package, _ = copy_fixture
    scripts = snapshot / "scripts"
    scripts.mkdir()
    source = scripts / "original.py"
    source.write_text("# original source\n")
    seal = package / "checksums.json"
    seal.write_text(json.dumps({"files": {"../../scripts/original.py": sha256_of(source)}}))
    assert EvidencePackage(str(package)).verify().complete
    seal.write_text(json.dumps({"files": {"../../../outside.py": sha256_of(source)}}))
    assert EvidencePackage(str(package)).verify().errors
