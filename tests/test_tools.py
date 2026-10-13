import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_records(directory, records):
    directory.mkdir()
    lines = [json.dumps({"key": key, **record}) for key, record in records.items()]
    (directory / "results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(directory)


def test_identical_and_differing_records_are_counted(tmp_path, capsys):
    tool = load_tool("compare_runs")
    sealed = write_records(tmp_path / "sealed", {"a": {"d06": True}, "b": {"d06": False}})
    same = write_records(tmp_path / "same", {"a": {"d06": True}})
    other = write_records(tmp_path / "other", {"a": {"d06": False}, "c": {"d06": True}})
    assert tool.main([sealed, same]) == 0
    assert "1 of 1 shared records are identical" in capsys.readouterr().out
    assert tool.main([sealed, other]) == 1
    assert "d06: differs in 1 records" in capsys.readouterr().out


def test_packages_without_a_common_record_are_flagged(tmp_path, capsys):
    tool = load_tool("compare_runs")
    one = write_records(tmp_path / "one", {"a": {"d06": True}})
    two = write_records(tmp_path / "two", {"z": {"d06": True}})
    assert tool.main([one, two]) == 1
    assert "no record in common" in capsys.readouterr().out


def test_the_committed_result_tables_are_current():
    tool = load_tool("build_results")
    for name, build in (("ARTICLE_NUMBERS.md", tool.article_numbers), ("STUDIES.md", tool.studies)):
        with open(os.path.join(ROOT, "results", name), encoding="utf-8") as handle:
            assert handle.read() == build(), f"{name} is out of date: run `make results`"


def test_the_article_numbers_table_has_every_checked_value():
    tool = load_tool("build_results")
    values = dict(tool.sealed_values())
    assert len(values) == 113
    assert values["H1 family 97.5"] == "[0.086, 0.207]"
    assert values["Published events, both environments"] == "none of 3379 captures"
