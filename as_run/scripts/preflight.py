#!/usr/bin/env python3
"""Physical preflight: verify the simulator environment WITHOUT running an episode.

This script starts no simulation, steps no vehicle and writes no trace. It only asks
each component to report its own version and checks that the parts agree.

Why it exists: on this platform the SUMO *binary* and the SUMO *Python bindings* come
from different distribution channels, so they can drift apart silently. A binding that
speaks a different TraCI version from the binary produces wrong state rather than an
error, which would corrupt every downstream physical claim.

Exit code 0 means the environment is consistent. Any non-zero exit means dependent
native work is blocked.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

REQUIRED_SUMO_VERSION = "1.21.0"
REQUIRED_PYTHON = (3, 14)


def find_sumo_binary() -> str | None:
    """Locate the sumo binary: SUMO_HOME first, then PATH."""
    home = os.environ.get("SUMO_HOME")
    if home:
        candidate = os.path.join(home, "bin", "sumo")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("sumo")


def binary_version(path: str) -> str | None:
    """Ask the binary for its version. This launches no simulation."""
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=60)
    except Exception:  # noqa: BLE001
        return None
    for line in (proc.stdout or "").splitlines():
        if "Version" in line:
            return line.split("Version", 1)[1].strip()
    return None


def main() -> int:
    report: dict = {"checks": {}, "problems": [], "blocking": []}

    version = sys.version_info
    report["checks"]["python_version"] = ".".join(str(p) for p in version[:3])
    if version[:2] != REQUIRED_PYTHON:
        report["blocking"].append(
            f"interpreter is {version[:2]}, contract requires {REQUIRED_PYTHON}"
        )

    binary = find_sumo_binary()
    report["checks"]["sumo_binary_path"] = binary
    report["checks"]["sumo_home"] = os.environ.get("SUMO_HOME")
    if binary is None:
        report["blocking"].append(
            "sumo binary not found; set SUMO_HOME or place sumo on PATH. "
            "On macOS arm64 there is no eclipse-sumo wheel, so the binary comes from the "
            "Eclipse SUMO macOS distribution and is NOT installed by uv sync."
        )
        found_binary_version = None
    else:
        found_binary_version = binary_version(binary)
        report["checks"]["sumo_binary_version"] = found_binary_version
        if found_binary_version != REQUIRED_SUMO_VERSION:
            report["blocking"].append(
                f"sumo binary reports {found_binary_version!r}, contract pins "
                f"{REQUIRED_SUMO_VERSION!r}"
            )

    for module in ("traci", "sumolib"):
        try:
            imported = __import__(module)
        except ImportError as exc:  # noqa: PERF203
            report["blocking"].append(f"cannot import {module}: {exc}")
            continue
        declared = getattr(imported, "__version__", None)
        if declared is None:
            try:
                from importlib.metadata import version as dist_version

                declared = dist_version(module)
            except Exception:  # noqa: BLE001
                declared = None
        report["checks"][f"{module}_version"] = declared
        if declared is not None and declared != REQUIRED_SUMO_VERSION:
            report["blocking"].append(
                f"{module} reports {declared!r}, contract pins {REQUIRED_SUMO_VERSION!r}"
            )

    if found_binary_version is not None:
        bindings = [
            report["checks"].get("traci_version"),
            report["checks"].get("sumolib_version"),
        ]
        if any(b is not None and b != found_binary_version for b in bindings):
            report["blocking"].append(
                "SUMO binary and Python bindings disagree. A binding that speaks a "
                "different TraCI version returns wrong state instead of failing, so every "
                "dependent physical claim would be unsound."
            )

    report["checks"]["libsumo_available"] = False
    try:
        __import__("libsumo")
        report["checks"]["libsumo_available"] = True
    except ImportError:
        report["problems"].append(
            "libsumo is not available; the adapter must use the TraCI socket interface. "
            "This is a performance and determinism consideration, not a blocker."
        )

    report["episode_executed"] = False
    report["optimizer_run"] = False
    report["ok"] = not report["blocking"]

    # stdout carries ONLY the machine-readable report, so another tool can parse it.
    # Human-facing lines go to stderr. Mixing the two on stdout made this report
    # unparsable to the W2 runner.
    print(json.dumps(report, indent=2))
    if report["blocking"]:
        print(f"BLOCKED: {len(report['blocking'])} blocking problem(s)", file=sys.stderr)
        return 1
    print("OK: simulator environment consistent; no episode was run", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
