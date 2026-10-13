import json
import os

from pursuit_audit.cli import main


def test_verify_reports_no_damage(snapshot, capsys):
    assert main(["verify", "--snapshot", snapshot]) == 0
    assert "0 packages with a file that differs" in capsys.readouterr().out


def test_recompute_agrees(snapshot, capsys):
    assert main(["recompute", "--snapshot", snapshot]) == 0
    assert "13 of 13 recomputed values equal the sealed ones" in capsys.readouterr().out


def test_score_prints_one_row_per_trace(examples, capsys):
    paths = [os.path.join(examples, f"{n}.jsonl") for n in ("blocked_stop", "passing_cars")]
    assert main(["score", *paths]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["oc"] for row in rows] == [True, False]


def test_score_refuses_a_broken_trace(tmp_path, capsys):
    path = tmp_path / "broken.jsonl"
    path.write_text('{"t": 0.0, "vehicles": {}}\n', encoding="utf-8")
    assert main(["score", str(path)]) == 1
    assert "not scored" in capsys.readouterr().err


def test_studies_lists_the_article_packages(capsys):
    assert main(["studies", "--article", "--commands"]) == 0
    out = capsys.readouterr().out
    assert "20261005_heldout_b_r01" in out and "scripts/run_heldout_b.py" in out
