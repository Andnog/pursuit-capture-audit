"""Complete state capture and restoration.

The assistance audit depends on this entirely. Its protocol requires restoring "the
complete simulator, controller and guard state and prefix, including pending commands,
memories, current commitments and exogenous randomness", and requires pause/resume to be
validated against uninterrupted execution BEFORE any replay result is used.

A snapshot that silently omits one component does not fail at capture time. It fails later,
as a small divergence in a counterfactual that is then reported as an effect.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from ..policies.memory import CommitmentMemory

SNAPSHOT_VERSION = "snapshot_v1"

# Every component a snapshot must carry. Enumerated so that adding state to the system
# without adding it here fails a test rather than corrupting a replay.
REQUIRED_COMPONENTS = (
    "backend",
    "commitment_memory",
    "decision_index",
    "pending_commands_present",
    "random",
)


@dataclass(frozen=True)
class Snapshot:
    version: str
    backend: dict
    commitment_memory: dict
    decision_index: int
    pending_commands_present: bool
    random: dict

    def as_record(self) -> dict:
        return {
            "version": self.version,
            "backend": self.backend,
            "commitment_memory": self.commitment_memory,
            "decision_index": self.decision_index,
            "pending_commands_present": self.pending_commands_present,
            "random": self.random,
        }

    def fingerprint(self) -> str:
        """A stable hash over the whole snapshot, for exact comparison."""
        return hashlib.sha256(
            json.dumps(self.as_record(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def memory_as_record(memory: CommitmentMemory) -> dict:
    return {
        "committed_opportunity_id": memory.committed_opportunity_id,
        "committed_at": memory.committed_at,
        "last_verdict": memory.last_verdict.value if memory.last_verdict else None,
        "consecutive_unknown": memory.consecutive_unknown,
        "switch_count": memory.switch_count,
    }


def memory_from_record(record: dict) -> CommitmentMemory:
    from ..opportunities.types import Verdict

    return CommitmentMemory(
        committed_opportunity_id=record["committed_opportunity_id"],
        committed_at=record["committed_at"],
        last_verdict=Verdict(record["last_verdict"]) if record["last_verdict"] else None,
        consecutive_unknown=record["consecutive_unknown"],
        switch_count=record["switch_count"],
    )


def capture(backend: Any, memory: CommitmentMemory, decision_index: int) -> Snapshot:
    backend_state = backend.capture_state()
    return Snapshot(
        version=SNAPSHOT_VERSION,
        backend=backend_state,
        commitment_memory=memory_as_record(memory),
        decision_index=decision_index,
        pending_commands_present=bool(backend_state.get("pending_commands")),
        random=dict(backend_state.get("random", {})),
    )


def restore(backend: Any, snapshot: Snapshot) -> tuple[CommitmentMemory, int]:
    missing = [c for c in REQUIRED_COMPONENTS if not hasattr(snapshot, c)]
    if missing:
        raise ValueError(f"snapshot is missing required components: {missing}")
    if snapshot.version != SNAPSHOT_VERSION:
        raise ValueError(
            f"snapshot version {snapshot.version!r} does not match {SNAPSHOT_VERSION!r}; "
            "a changed snapshot format requires a new domain, not a silent read"
        )
    backend.restore_state(snapshot.backend)
    return memory_from_record(snapshot.commitment_memory), snapshot.decision_index


def states_identical(left: Snapshot, right: Snapshot) -> bool:
    return left.fingerprint() == right.fingerprint()


def first_difference(left: Snapshot, right: Snapshot) -> list[str]:
    """Where two snapshots differ, for diagnosis rather than a bare boolean."""
    out: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a:
                    out.append(f"{path}.{key}: missing on the left")
                elif key not in b:
                    out.append(f"{path}.{key}: missing on the right")
                else:
                    walk(a[key], b[key], f"{path}.{key}")
        elif a != b:
            out.append(f"{path}: {a!r} != {b!r}")

    walk(left.as_record(), right.as_record(), "")
    return out
