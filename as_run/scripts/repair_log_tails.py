"""Restore sealed log files to which a leftover simulator process appended lines (A-145).

A run started as `python ... >> package/run.log` passes the log's file descriptor to the SUMO
processes it spawns. A SUMO process that outlives its run (an orphan) keeps that descriptor open,
and when it later receives a termination signal it writes

    Interrupt signal received, trying to exit gracefully.

to the log, even if the package was sealed days before. The sealed bytes are then still there, as
a prefix of the file, followed by those lines.

This script acts on a sealed `.log` file only if BOTH hold:
1. some prefix of the file has exactly the sealed SHA-256 (so the sealed content is intact);
2. everything after that prefix consists of the line above, repeated (and NUL bytes, which a
   non-append descriptor leaves when the file has been truncated under it).

Default: report. With `--apply`: save the appended bytes under `provenance/log_tails/<stamp>/`,
record them in `MANIFEST.json` there, truncate the file to the sealed length and verify the hash.
Any other mismatch is reported and never touched.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")
LINE = b"Interrupt signal received, trying to exit gracefully."
SEARCH = 1 << 20  # the sealed length is searched in the last megabyte


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sealed_length(data: bytes, digest: str) -> int | None:
    """Length of the prefix whose SHA-256 is `digest`, searched at line ends near the end."""
    start = max(0, len(data) - SEARCH)
    cuts = {start + i + 1 for i, ch in enumerate(data[start:]) if ch == 10}
    cuts |= set(range(max(start, len(data) - 8192), len(data) + 1))
    h, last = hashlib.sha256(data[:start]), start
    for cut in sorted(cuts):
        h.update(data[last:cut])
        last = cut
        if h.copy().hexdigest() == digest:
            return cut
    return None


def only_interrupt_lines(tail: bytes) -> bool:
    lines = [x for x in tail.replace(b"\x00", b"").split(b"\n") if x]
    return bool(lines) and all(x == LINE for x in lines)


def inspect():
    """Every sealed .log file whose hash differs, with what can be said about it."""
    out = []
    for package in sorted(os.listdir(EXP)):
        manifest = os.path.join(EXP, package, "checksums.json")
        if not os.path.isfile(manifest):
            continue
        with open(manifest, encoding="utf-8") as h:
            files = json.load(h).get("files", {})
        for rel, digest in files.items():
            path = os.path.normpath(os.path.join(EXP, package, rel))
            if not rel.endswith(".log") or not os.path.isfile(path):
                continue
            with open(path, "rb") as h:
                data = h.read()
            if sha256_bytes(data) == digest:
                continue
            cut = sealed_length(data, digest)
            row = {"package": package, "file": rel, "sealed_sha256": digest, "size": len(data)}
            if cut is None:
                row["status"] = "no prefix has the sealed hash: not repairable here"
            elif not only_interrupt_lines(data[cut:]):
                row.update(
                    status="appended bytes are not interrupt lines: not touched", sealed_length=cut
                )
            else:
                tail = data[cut:]
                row.update(
                    status="repairable",
                    sealed_length=cut,
                    appended_bytes=len(tail),
                    appended_lines=tail.count(LINE),
                    tail_sha256=sha256_bytes(tail),
                )
            out.append(row)
    return out


def apply(rows):
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    folder = os.path.join(ROOT, "provenance", "log_tails", stamp)
    os.makedirs(folder)
    done = []
    for row in rows:
        if row["status"] != "repairable":
            continue
        path = os.path.join(EXP, row["package"], row["file"])
        with open(path, "rb") as h:
            data = h.read()
        cut = row["sealed_length"]
        if sha256_bytes(data[:cut]) != row["sealed_sha256"]:  # the file changed since inspection
            row["status"] = "changed during repair: not touched"
            continue
        name = f"{row['package']}__{row['file'].replace('/', '_')}.tail"
        with open(os.path.join(folder, name), "wb") as h:
            h.write(data[cut:])
        os.truncate(path, cut)
        with open(path, "rb") as h:
            row["restored"] = sha256_bytes(h.read()) == row["sealed_sha256"]
        row["tail_file"] = os.path.relpath(os.path.join(folder, name), ROOT)
        done.append(row)
    with open(os.path.join(folder, "MANIFEST.json"), "w", encoding="utf-8") as h:
        json.dump({"repaired_at": stamp, "line": LINE.decode(), "files": done}, h, indent=1)
    return folder, done


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = inspect()
    for row in rows:
        print(json.dumps({k: v for k, v in row.items() if k != "sealed_sha256"}))
    repairable = [r for r in rows if r["status"] == "repairable"]
    print(json.dumps({"mismatching_logs": len(rows), "repairable": len(repairable)}))
    if args.apply and repairable:
        folder, done = apply(rows)
        print(
            json.dumps(
                {
                    "saved_in": os.path.relpath(folder, ROOT),
                    "restored": sum(r["restored"] for r in done),
                }
            )
        )
    return 0 if len(repairable) == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
