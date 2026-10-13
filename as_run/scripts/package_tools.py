"""Record the inputs of an evidence package at launch, and seal it when its writers have ended.

    uv run python scripts/package_tools.py register --package experiments/X --amendment A-137 \
        --source scripts/a.py --source src/b.py [--note key=value ...]
    uv run python scripts/package_tools.py seal --package experiments/X
    uv run python scripts/package_tools.py verify --package experiments/X
    uv run python scripts/package_tools.py writers --package experiments/X   (or --all)

`register` refuses to overwrite an existing inputs.json; `seal` refuses to overwrite a seal. The
formats are those of the packages sealed by hand before this script existed (A-137).

A-146 (sixth review, F6-2). Until schema version 1, `seal` wrote
`sealed_after_all_writers_ended: true` without checking it, and A-145 showed how leftover simulator
processes that still held a run log wrote to it after sealing. From schema version 2:

- `seal` asks the operating system which processes hold a file of the package open for writing
  (`lsof +D`). If any does, it refuses, names them, and nothing is written. Those processes must
  end first; there is no override.
- If the check cannot be made (no `lsof`), `seal` refuses unless `--operator-certifies` is given.
  The seal then records that the condition was declared by the operator and not checked.
- The seal records the check: method, time and result.

The check is about the moment of sealing. A run should still write its log outside the package and
copy it in at the end, or be sealed only after its simulator processes have ended.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITE_MODES = ("w", "u")  # lsof access: write, or read and write
LSOF_METHOD = "lsof -nP -F pcfan +D <package>"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def register(package, amendment, sources, notes):
    path = os.path.join(ROOT, package, "inputs.json")
    if os.path.exists(path):
        raise SystemExit(f"{path} exists; inputs are recorded once, at launch")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {
        "schema_version": 1,
        "experiment_id": os.path.basename(package.rstrip("/")),
        "recorded_at_launch": now(),
        "amendment": amendment,
        "sources": {s: sha256(os.path.join(ROOT, s)) for s in sorted(set(sources))},
    }
    out.update(notes)
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    return out


def files_of(package):
    base = os.path.join(ROOT, package)
    out = {}
    for folder, _, names in os.walk(base):
        for name in names:
            rel = os.path.relpath(os.path.join(folder, name), base)
            if rel != "checksums.json" and not name.startswith("."):
                out[rel] = sha256(os.path.join(folder, name))
    return dict(sorted(out.items()))


def parse_lsof(text, own_pid=None):
    """Handles open for writing in `lsof -F pcfan` output: [{pid, command, fd, access, name}]."""
    out, pid, command, fd, access = [], None, None, None, None
    for line in text.splitlines():
        if not line:
            continue
        tag, value = line[0], line[1:]
        if tag == "p":
            pid, command, fd, access = int(value), None, None, None
        elif tag == "c":
            command = value
        elif tag == "f":
            fd, access = value, None
        elif tag == "a":
            access = value.strip()
        elif tag == "n" and access in WRITE_MODES and pid != own_pid:
            out.append({"pid": pid, "command": command, "fd": fd, "access": access, "name": value})
    return out


def open_for_writing(package):
    """Handles that processes hold open for writing on files of the package, or None if this
    cannot be known (no `lsof`)."""
    lsof = shutil.which("lsof") or ("/usr/sbin/lsof" if os.path.exists("/usr/sbin/lsof") else None)
    if lsof is None:
        return None
    base = os.path.realpath(os.path.join(ROOT, package))
    # lsof exits with 1 when it lists nothing; only its output is used.
    done = subprocess.run(
        [lsof, "-nP", "-F", "pcfan", "+D", base], capture_output=True, text=True, check=False
    )
    return parse_lsof(done.stdout, own_pid=os.getpid())


def seal(package, operator_certifies=False):
    path = os.path.join(ROOT, package, "checksums.json")
    if os.path.exists(path):
        raise SystemExit(f"{path} exists; a sealed package is not resealed")
    writers = open_for_writing(package)
    if writers:
        listed = "; ".join(f"pid {w['pid']} ({w['command']}) -> {w['name']}" for w in writers[:10])
        raise SystemExit(
            f"not sealed: {len(writers)} handle(s) are open for writing in {package}: {listed}. "
            "End those processes first."
        )
    if writers is None and not operator_certifies:
        raise SystemExit(
            "not sealed: lsof is not available, so it cannot be checked that every writer has "
            "ended. Use --operator-certifies to seal on the operator's declaration."
        )
    checked = writers is not None
    out = {
        "schema_version": 2,
        "experiment_id": os.path.basename(package.rstrip("/")),
        "sealed_at": now(),
        "algorithm": "sha256",
        "sealed_after_all_writers_ended": True
        if checked
        else "declared by the operator; not checked",
        "writers_check": {
            "method": LSOF_METHOD,
            "performed": checked,
            "checked_at": now(),
            "open_for_writing": [] if checked else None,
        },
        "excludes_itself": True,
        "files": files_of(package),
    }
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    return out


def verify(package):
    with open(os.path.join(ROOT, package, "checksums.json"), encoding="utf-8") as h:
        sealed = json.load(h)["files"]
    current = files_of(package)
    return {
        "files": len(sealed),
        "changed": sorted(k for k in sealed if k in current and current[k] != sealed[k]),
        "missing": sorted(k for k in sealed if k not in current),
        "unsealed": sorted(k for k in current if k not in sealed),
    }


def sealed_packages():
    base = os.path.join(ROOT, "experiments")
    return [
        os.path.join("experiments", name)
        for name in sorted(os.listdir(base))
        if os.path.isfile(os.path.join(base, name, "checksums.json"))
    ]


def writers_report(packages):
    """Which of the packages have a file open for writing by some process, now."""
    out = {"checked_at": now(), "method": LSOF_METHOD, "performed": True, "packages": {}}
    for package in packages:
        handles = open_for_writing(package)
        if handles is None:
            out["performed"] = False
            return out
        if handles:
            out["packages"][package] = handles
    out["packages_checked"] = len(packages)
    out["packages_with_a_writer"] = len(out["packages"])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["register", "seal", "verify", "writers"])
    parser.add_argument("--package")
    parser.add_argument("--all", action="store_true", help="writers: every sealed package")
    parser.add_argument("--amendment", default="")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--operator-certifies", action="store_true")
    parser.add_argument("--out", help="writers: also write the report to this file")
    args = parser.parse_args()
    if not args.package and not (args.action == "writers" and args.all):
        parser.error("--package is required")
    if args.action == "register":
        notes = dict(n.split("=", 1) for n in args.note)
        out = register(args.package, args.amendment, args.source, notes)
        print(json.dumps({"registered": len(out["sources"])}))
    elif args.action == "seal":
        out = seal(args.package, args.operator_certifies)
        print(
            json.dumps({"sealed_files": len(out["files"]), "writers_check": out["writers_check"]})
        )
    elif args.action == "writers":
        report = writers_report(sealed_packages() if args.all else [args.package])
        if args.out:
            with open(os.path.join(ROOT, args.out), "w", encoding="utf-8") as h:
                json.dump(report, h, indent=1)
        print(json.dumps({k: v for k, v in report.items() if k != "packages"}))
        for package, handles in report["packages"].items():
            print(package, json.dumps(handles[:5]))
        return 1 if report["packages"] or not report["performed"] else 0
    else:
        out = verify(args.package)
        print(json.dumps(out))
        return 1 if out["changed"] or out["missing"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
