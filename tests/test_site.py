"""The web page draws only what its data files hold."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def read(*parts):
    with open(os.path.join(DOCS, *parts), encoding="utf-8") as handle:
        return handle.read()


def test_every_chart_and_number_of_the_page_has_a_source():
    page, script = read("index.html"), read("assets", "js", "site.js")
    for chart in set(re.findall(r'data-chart="([^"]+)"', page)):
        assert re.search(rf'["\']?{re.escape(chart)}["\']?: \(\) =>', script), chart
    for fill in set(re.findall(r'data-fill="([^"]+)"', page)):
        assert re.search(rf'["\']?{re.escape(fill)}["\']?:', script), fill


def test_every_animation_has_its_data_file():
    page = read("index.html")
    sources = re.findall(r'"src": "([^"]+)"', page) + re.findall(r'data-src="([^"]+)"', page)
    assert len(sources) >= 6
    for source in sources:
        data = json.loads(read(*source.split("/")))
        assert len(data["times"]) == len(data["frames"]) == len(data["mask"]) == len(data["run"])
        assert set(data["results"]) >= {"oc", "body_5m", "centre_5m", "front_5m"}


def test_the_chart_data_carry_the_results_of_the_article():
    charts = json.loads(read("assets", "data", "charts.json"))
    primary = [entry for entry in charts["advantage"] if entry.get("primary")]
    assert [(e["v"], e["lo"], e["hi"]) for e in primary] == [
        (0.1453, 0.0855, 0.2073),
        (0.0643, 0.0145, 0.1139),
    ]
    assert charts["published_events"] == 3379
    assert charts["hold"] == {"captures": 1433, "escapes_held": 0, "escapes_probe": 15}
    assert charts["counts"]["evaluation"] == 197655


def test_the_page_states_no_result_as_typed_text():
    """Percentages and intervals come from the data files, through `data-fill` or a chart."""
    text = re.sub(r"<(script|style|pre)\b.*?</\1>", " ", read("index.html"), flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    assert not re.search(r"\d+(\.\d+)?\s?%\s*\[", text)
    assert not re.search(r"[+−-]0\.\d{3}", text)
