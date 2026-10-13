"""Compare the per-episode records of two evidence packages, key by key.

    python tools/compare_runs.py <sealed package> <new package> [--records results.jsonl]

For a study that was run again, or for a replay of part of one: how many records of the new
package have a record with the same key in the sealed one, how many of those are identical, and
which fields differ in the others. Exit status 1 if a shared record differs.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pursuit_audit.evidence.package import EvidencePackage  # noqa: E402


def compare(sealed: dict[str, dict], new: dict[str, dict]) -> tuple[int, int, Counter]:
    """Return the number of shared keys, of identical records, and the fields that differ."""
    shared = sorted(set(sealed) & set(new))
    identical = 0
    differing: Counter = Counter()
    for key in shared:
        if sealed[key] == new[key]:
            identical += 1
            continue
        for field in sorted(set(sealed[key]) | set(new[key])):
            if sealed[key].get(field) != new[key].get(field):
                differing[field] += 1
    return len(shared), identical, differing


def main(argv: list[str] | None = None) -> int:
    """Print the comparison and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sealed", help="the sealed package")
    parser.add_argument("new", help="the package that was run again")
    parser.add_argument("--records", default="results.jsonl", help="name of the records file")
    args = parser.parse_args(argv)
    sealed = EvidencePackage(args.sealed).records(args.records)
    new = EvidencePackage(args.new).records(args.records)
    shared, identical, differing = compare(sealed, new)
    print(f"{len(sealed)} sealed records, {len(new)} new records, {shared} with the same key")
    print(f"{identical} of {shared} shared records are identical")
    for field, count in differing.most_common():
        print(f"  {field}: differs in {count} records")
    if not shared:
        print("no record in common: are these the same study?")
    return 1 if differing or not shared else 0


if __name__ == "__main__":
    raise SystemExit(main())
