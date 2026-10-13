"""pursuit_audit: score a vehicle-pursuit study under more than one capture endpoint.

Many multi-vehicle pursuit studies declare a capture when a pursuer comes within a few metres of
the evader. In microscopic traffic that rule is also met by two cars that pass each other in
opposite lanes. This library scores the same episode under proximity rules and under an
operational capture rule, reads the sealed evidence of the accompanying article, and recomputes
its headline results.

    import pursuit_audit as pa

    frames = pa.load_trace("episode.jsonl")
    row = pa.score_trace(frames, evader="e1")
"""

from .domain.geometry import Body, body_gap_m, centre_distance_m, front_distance_m
from .domain.trace import Frame, TraceError, load_trace, parse_trace, validate_trace
from .endpoints.operational import (
    CaptureParameters,
    CaptureResult,
    contact_specification,
    operational_capture,
)
from .endpoints.proximity import ProximityResult, ProximityRule, proximity, register_distance
from .endpoints.scoring import score_trace
from .evidence.package import EvidencePackage, Verification
from .statistics.bootstrap import Interval, family_bootstrap

__version__ = "1.0.0"

__all__ = [
    "Body",
    "CaptureParameters",
    "CaptureResult",
    "EvidencePackage",
    "Frame",
    "Interval",
    "ProximityResult",
    "ProximityRule",
    "TraceError",
    "Verification",
    "body_gap_m",
    "centre_distance_m",
    "contact_specification",
    "family_bootstrap",
    "front_distance_m",
    "load_trace",
    "operational_capture",
    "parse_trace",
    "proximity",
    "register_distance",
    "score_trace",
    "validate_trace",
]
