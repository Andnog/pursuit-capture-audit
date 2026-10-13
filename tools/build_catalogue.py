"""Build the catalogue of studies from the frozen snapshot.

For every sealed package: its title, the amendment that registered it, the script that produced
it with the options that the script accepts, whether it needs the simulator, and whether the
article rests on it. The options are read from the source of each script, which is not executed.

    python tools/build_catalogue.py            # writes src/pursuit_audit/evidence/studies.json
"""

from __future__ import annotations

import ast
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "as_run")
OUTPUT = os.path.join(ROOT, "src", "pursuit_audit", "evidence", "studies.json")
EVIDENCE_MAP = os.path.join(ROOT, "results", "EVIDENCE_MAP.md")
SCRIPT = re.compile(r"scripts/([a-z0-9_]+\.py)")
SIMULATES = re.compile(r"run_episode|import traci|native\.engine|\bPool\(|rollout")
RUNNER_PREFIXES = ("run_", "train_", "audit_")
# The scripts of the studies behind the article, checked by hand: the script that ran the study
# first, then the scripts that analysed its package.
CURATED = {
    "20261002_kan_capture_law_r01": ["kan_capture_law.py"],
    "20261003_interpretability_r01": [
        "interpretability_capture_law.py",
        "interpretability_policy_heads.py",
    ],
    "20261004_audit_addendum_r01": ["audit_addendum.py", "addendum_reanalysis.py"],
    "20261004_audit_addendum_r02": ["audit_addendum_r02.py", "addendum_r02_reanalysis.py"],
    "20261004_audit_addendum_r03": ["audit_addendum_r03.py", "addendum_r03_reanalysis.py"],
    "20261005_capture_instant_scan_r01": ["scan_capture_instants.py"],
    "20261005_heldout_b_r01": ["run_heldout_b.py", "build_heldout_b_maps.py"],
    "20261005_kinematic_sensitivity_r01": ["run_kinematic_sensitivity.py"],
    "20261005_published_env_audit_r01": ["audit_published_env.py", "analyse_published_env.py"],
    "20261005_published_env_audit_r02": [
        "audit_published_env_r02.py",
        "analyse_published_env_r02.py",
    ],
    "20261005_published_env_pepcrl_r01": [
        "audit_published_env_pepcrl.py",
        "report_published_env_pepcrl.py",
    ],
    "20261005_traffic_sensitivity_r01": ["run_traffic_sensitivity.py"],
    "20261005_tuned_evader_r01": ["run_tuned_evader_study.py"],
    "20261005_v3_first_batch_reconstruction_r01": ["reconstruct_v3_first_batches.py"],
    "20261006_mappo_v4_r01": ["train_mappo_v4.py", "analyse_mappo_v4.py"],
    "20261003_method_gifs": ["render_capture_gif.py"],
}
THIRD_PARTY = ("20261005_published_env_",)


def read(path: str) -> str:
    """Return the text of a file, or an empty string if it does not exist."""
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def options_of(script: str) -> list[dict]:
    """Return the command-line options that a script declares, without running it."""
    source = read(os.path.join(SNAPSHOT, "scripts", script))
    if not source:
        return []
    options = []
    for node in ast.walk(ast.parse(source)):
        is_option = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        )
        if not is_option:
            continue
        keywords = {k.arg: k.value for k in node.keywords}
        default = keywords.get("default")
        options.append(
            {
                "name": node.args[0].value,
                "default": ast.unparse(default) if default is not None else None,
                "flag": isinstance(keywords.get("action"), ast.Constant),
                "help": keywords["help"].value
                if isinstance(keywords.get("help"), ast.Constant)
                else None,
            }
        )
    return options


def candidates_of(package_dir: str) -> list[str]:
    """Return the scripts that the records of a package name."""
    found = []
    inputs = read(os.path.join(package_dir, "inputs.json"))
    if inputs:
        found += [
            m.group(1) for p in json.loads(inputs).get("sources", {}) if (m := SCRIPT.fullmatch(p))
        ]
    for name in ("PROTOCOL_EN.md", "SCIENTIFIC_DECISION_EN.md", "DEVIATIONS_EN.md"):
        found += SCRIPT.findall(read(os.path.join(package_dir, name)))
    existing = [f for f in found if os.path.exists(os.path.join(SNAPSHOT, "scripts", f))]
    return list(dict.fromkeys(existing))


def scripts_of(package_dir: str, amendment: str | None) -> list[str]:
    """Return the scripts of a package, the one that ran the study first.

    A curated entry wins. Otherwise the candidates are ranked: a script whose header names the
    amendment of the package, whose name shares words with the package, and which is a runner.
    """
    package = os.path.basename(package_dir)
    if package in CURATED:
        return CURATED[package]
    words = set(re.split(r"[_\d]+", package)) - {"", "r", "w"}

    def score(script: str) -> tuple:
        header = read(os.path.join(SNAPSHOT, "scripts", script))[:600]
        names_amendment = bool(amendment) and re.search(rf"\b{amendment}\b", header) is not None
        shared = len(words & set(script[:-3].split("_")))
        return (names_amendment, shared, script.startswith(RUNNER_PREFIXES))

    ranked = sorted(candidates_of(package_dir), key=score, reverse=True)
    return ranked[:1]


def command_for(script: str | None, package: str) -> str | None:
    """Return the command that runs a script again, writing to a new package if it takes one."""
    if script is None:
        return None
    names = {option["name"] for option in options_of(script)}
    command = f"uv run python scripts/{script}"
    for candidate in ("--package", "--out", "package"):
        if candidate in names:
            target = f"experiments/{package}_rerun"
            command += f" {target}" if candidate == "package" else f" {candidate} {target}"
            break
    return command


def simulates(script: str | None) -> bool:
    """Tell whether a script starts the simulator, from its source."""
    return bool(script) and bool(SIMULATES.search(read(os.path.join(SNAPSHOT, "scripts", script))))


def main() -> int:
    """Write the catalogue."""
    with open(os.path.join(SNAPSHOT, "SNAPSHOT.json"), encoding="utf-8") as handle:
        archive_only = json.load(handle)["archive_only"]
    cited = set(re.findall(r"\b(20\d{6}_[a-z0-9_]+)", read(EVIDENCE_MAP)))
    studies = []
    experiments = os.path.join(SNAPSHOT, "experiments")
    for package in sorted(os.listdir(experiments)):
        directory = os.path.join(experiments, package)
        if not os.path.isdir(directory):
            continue
        protocol = read(os.path.join(directory, "PROTOCOL_EN.md"))
        decision = read(os.path.join(directory, "SCIENTIFIC_DECISION_EN.md"))
        heading = re.search(r"^#\s+(.+)$", protocol or decision, re.M)
        amendment = re.search(r"\bA-\d+\b", protocol or decision)
        scripts = scripts_of(directory, amendment.group(0) if amendment else None)
        script = scripts[0] if scripts else None
        held_back = [e for e in archive_only if e["path"].startswith(f"experiments/{package}/")]
        studies.append(
            {
                "package": package,
                "date": f"{package[:4]}-{package[4:6]}-{package[6:8]}",
                "title": heading.group(1).strip() if heading else package,
                "amendment": amendment.group(0) if amendment else None,
                "registered": "pre-registered" in (protocol + decision).lower(),
                "script": script,
                "command": command_for(script, package),
                "options": options_of(script) if script else [],
                "analysis_scripts": scripts[1:],
                "needs_simulator": simulates(script),
                "needs_third_party_code": package.startswith(THIRD_PARTY),
                "in_article": package in cited,
                "archive_only_files": len(held_back),
                "archive_only_bytes": sum(e["bytes"] for e in held_back),
            }
        )
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(studies, handle, indent=1)
        handle.write("\n")
    with_script = sum(1 for s in studies if s["script"])
    in_article = sum(1 for s in studies if s["in_article"])
    print(f"{len(studies)} studies; {with_script} with a script; {in_article} behind the article")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
