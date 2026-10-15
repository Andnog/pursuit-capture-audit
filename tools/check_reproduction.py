"""Run complete-archive checks and sampled replay in a new output directory.

Requires an installed frozen environment and SUMO. No study is trained or re-sealed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pursuit_audit.evidence.inventory import verify_snapshot  # noqa: E402


def main() -> int:
    """Fail on incomplete evidence, failed tests or a differing sampled replay."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python", required=True, help="Python of the installed frozen environment"
    )
    parser.add_argument("--snapshot", default=str(ROOT / "as_run"))
    parser.add_argument("--output", required=True, help="new directory outside the snapshot")
    args = parser.parse_args()
    snapshot = Path(args.snapshot).resolve()
    output = Path(args.output).resolve()
    interpreter = str(Path(args.python).absolute())
    if output == snapshot or snapshot in output.parents:
        parser.error("output must be outside the preserved snapshot")
    if output.exists():
        parser.error("output must be a new directory")
    result = verify_snapshot(str(snapshot), complete=True)
    if result.errors:
        for error in result.errors:
            print(error)
        return 1
    output.mkdir(parents=True)
    report = {
        "snapshot": str(snapshot),
        "python": interpreter,
        "checks": [],
        "complete_archive": True,
    }
    commands = [
        ("preflight", [interpreter, "scripts/preflight.py"]),
        (
            "historical-tests",
            [interpreter, "-m", "unittest", "discover", "-s", "tests", "-t", "tests"],
        ),
        (
            "replay",
            [
                interpreter,
                "scripts/audit_d06_persistence.py",
                "--package",
                str(output / "replay"),
                "--limit",
                "6",
                "--workers",
                "2",
            ],
        ),
        (
            "comparison",
            [
                sys.executable,
                str(ROOT / "tools/compare_runs.py"),
                str(snapshot / "experiments/20261003_d06_persistence_audit_r01"),
                str(output / "replay"),
            ],
        ),
    ]
    for name, command in commands:
        with (output / f"{name}.log").open("w") as log:
            run = subprocess.run(
                command, cwd=snapshot, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        report["checks"].append({"name": name, "exit_code": run.returncode})
        (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{name}: exit {run.returncode}", flush=True)
        if run.returncode:
            return 1
    records = [
        json.loads(line)
        for line in (output / "replay/results.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if len(records) != 6 or not all(row.get("reproduced") for row in records):
        print("Sample incomplete or capture not reproduced")
        return 1
    print("Complete archive, historical tests and six identical sampled replays verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
