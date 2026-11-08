"""Source-bound namespace3 inputs; registry identity is not full physical A/B sameness."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import COORDINATOR_VERSION, CoordinatorProfile
from app.v3.coordinator_profile_authority import authoritative_sources, verified
from app.v3.coordinator_profile_bind import bind
from app.v3.coordinator_profile_choices import normalized
from app.v3.coordinator_profile_schema import validate_document
from app.v3.coordinator_profile_wire import materialized
from app.v3.flow_profile_sources import _same_types
from app.v3.flow_profile_wire import record
from app.v3.input_models import V3Bundle

COMPILER_VERSION = "qoima-coordinator-profile-0.1.0"
INPUT_SCOPE = "source_bound_coordinator_namespace3_proposal"


@dataclass(frozen=True, slots=True)
class CompiledCoordinatorProfile:
    profile: CoordinatorProfile
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes
    input_hash: str
    registry_common_hash: str


def compile_coordinator_profile(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    document: Any,
) -> CompiledCoordinatorProfile:
    validate_document(document)
    value = normalized(document)
    source, belt, facts = verified(bundle, conveyor)
    try:
        profile, graph, ledger = bind(source, belt, value)
    except (KeyError, StopIteration) as exc:
        raise ValueError("Unknown source or declared coordinator resource reference") from exc
    registry = profile.registry.canonical_bytes
    common_hash = sha256(registry).hexdigest()
    frozen = canonical_bytes(
        {
            "compiler_version": COMPILER_VERSION,
            "engine_version": COORDINATOR_VERSION,
            "scope": INPUT_SCOPE,
            "choices": value,
            **facts,
            **materialized(profile, ledger),
            "graph_document": graph,
            "registry": parse_json(registry),
            "registry_common_hash": common_hash,
            "horizon_tick": value["horizon_tick"],
            "end_tick": value["end_tick"],
        }
    )
    return CompiledCoordinatorProfile(
        profile,
        value["horizon_tick"],
        value["end_tick"],
        frozen,
        sha256(frozen).hexdigest(),
        common_hash,
    )


def load_coordinator_inputs(raw: bytes) -> CompiledCoordinatorProfile:
    if type(raw) is not bytes:
        raise ValueError("Frozen coordinator inputs require immutable exact bytes")
    value = parse_json(raw)
    if type(value) is not dict or value.get("compiler_version") != COMPILER_VERSION:
        raise ValueError("Unsupported coordinator compiler envelope")
    if value.get("engine_version") != COORDINATOR_VERSION or value.get("scope") != INPUT_SCOPE:
        raise ValueError("Coordinator runtime/scope identity mismatch")
    bundle, conveyor = authoritative_sources()
    expected = compile_coordinator_profile(bundle, conveyor, value.get("choices"))
    if expected.frozen_bytes != raw:
        raise ValueError("Frozen coordinator input differs from exact canonical source binding")
    return expected


def validate_compiled_coordinator(
    compiled: CompiledCoordinatorProfile,
    conveyor: ConveyorSource,
) -> None:
    if type(compiled) is not CompiledCoordinatorProfile:
        raise ValueError("Exact compiled coordinator input type required")
    expected = load_coordinator_inputs(compiled.frozen_bytes)
    bundle, _ = authoritative_sources()
    verified(bundle, conveyor)
    if not _same_types(compiled, expected):
        raise ValueError("Retained coordinator profile exact typed identity mismatch")
    # Includes graph adjacency and exact native types, not dataclass bool/int equality.
    if (
        compiled.input_hash != expected.input_hash
        or compiled.registry_common_hash != expected.registry_common_hash
        or compiled.horizon_tick != expected.horizon_tick
        or compiled.end_tick != expected.end_tick
        or canonical_bytes(record(compiled.profile)) != canonical_bytes(record(expected.profile))
    ):
        raise ValueError("Retained coordinator profile differs from its verified frozen inputs")
