"""pursuit_audit: score vehicle-pursuit episodes under proximity and operational-capture endpoints.

Standalone (standard library only). See README.md one level up.
"""

from .endpoints import (
    CaptureParameters,
    CaptureResult,
    ProximityResult,
    operational_capture,
    proximity,
    score_trace,
)
from .geometry import Body, body_gap_m, heading_difference_rad
from .trace import Frame, TraceError, load_trace, validate_trace

__all__ = [
    "Body",
    "CaptureParameters",
    "CaptureResult",
    "Frame",
    "ProximityResult",
    "TraceError",
    "body_gap_m",
    "heading_difference_rad",
    "load_trace",
    "operational_capture",
    "proximity",
    "score_trace",
    "validate_trace",
]
__version__ = "0.1.0"
