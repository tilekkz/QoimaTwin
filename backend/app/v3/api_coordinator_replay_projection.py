"""Typed mutable snapshot projection reuses the native input-bound compact vocabulary."""

from typing import cast

from app.v3.coordinator_models import CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_native_decode import decode, encode
from app.v3.coordinator_run_definitions import Definitions
from app.v3.coordinator_run_projection import _compact, _expand
from app.v3.flow_profile_sources import _same_types
from app.v3.interface import Json


def project_snapshot(profile: CoordinatorProfile, point: CoordinatorSnapshot) -> Json:
    """Project already verified settled state; this does not grant source or runtime admission."""
    if type(profile) is not CoordinatorProfile or type(point) is not CoordinatorSnapshot:
        raise ValueError("Exact coordinator profile and snapshot required")
    decoded = decode(CoordinatorSnapshot, encode(point))
    if not _same_types(point, decoded):
        raise ValueError("Coordinator replay state has a substituted native type")
    compact = _compact(decoded)
    expanded = _expand(CoordinatorSnapshot, compact, Definitions(profile))
    restored = decode(CoordinatorSnapshot, expanded)
    if encode(restored) != encode(point):
        raise ValueError("Coordinator replay definitions differ from exact input authority")
    return cast(Json, compact)
