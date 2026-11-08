"""Strict public choices compile to a source-bound validated connected SMALL profile."""

import hashlib
from dataclasses import dataclass
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_decode import decode_choices
from app.v3.flow_profile_schema import validate_document
from app.v3.flow_profile_sources import verified_records
from app.v3.flow_profile_wire import materialized_record, normalized_choices
from app.v3.input_models import V3Bundle
from app.v3.light_flow_models import FlowProfile
from app.v3.light_flow_source import bind_source_profile
from app.v3.light_flow_validate import validate

COMPILER_VERSION = "qoima-light-flow-profile-0.1.0"


@dataclass(frozen=True, slots=True)
class CompiledLightProfile:
    profile: FlowProfile
    horizon_tick: int
    end_tick: int
    frozen_bytes: bytes
    input_hash: str


def compile_light_profile(
    bundle: V3Bundle, conveyor: ConveyorSource, document: Any
) -> CompiledLightProfile:
    validate_document(document)
    horizon, end = document["horizon_tick"], document["end_tick"]
    if end < horizon or any(row["arrival_tick"] >= horizon for row in document["orders"]):
        raise ValueError("Require positive H<=end and all offered arrivals<H")
    sources = verified_records(bundle, conveyor)
    choices = decode_choices(document)
    profile = bind_source_profile(bundle, conveyor, choices)
    ledger = validate(profile, conveyor)
    frozen = canonical_bytes(
        {
            "compiler_version": COMPILER_VERSION,
            "scope": "source_bound_connected_small_proposal",
            "choices": normalized_choices(document),
            **sources,
            **materialized_record(profile, ledger),
        }
    )
    return CompiledLightProfile(profile, horizon, end, frozen, hashlib.sha256(frozen).hexdigest())
