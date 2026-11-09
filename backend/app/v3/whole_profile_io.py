"""Compile reviewable source choices into the unchanged whole publication envelope."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.flow_profile_sources import _pinned_reference, verified_records
from app.v3.input_models import V3Bundle
from app.v3.whole_profile_io_choices import normalize
from app.v3.whole_profile_io_decode import decode
from app.v3.whole_profile_schema import validate_document
from app.v3.whole_profile_source import bind_whole_source
from app.v3.whole_run_inputs import WholeRunInputs, freeze_whole_source, load_whole_inputs

COMPILER_VERSION = "qoima-whole-flow-public-profile-0.1.0"


@dataclass(frozen=True, slots=True)
class CompiledWholeProfile:
    run_inputs: WholeRunInputs
    choices_bytes: bytes
    choices_sha256: str
    compiler_version: str = COMPILER_VERSION


def compile_whole_profile(
    bundle: V3Bundle, conveyor: ConveyorSource, document: Any
) -> CompiledWholeProfile:
    validate_document(document)
    value = normalize(document)
    verified_records(bundle, conveyor)
    raw = canonical_bytes(value)
    inputs = load_whole_inputs(_compile_source_bytes(raw))
    return CompiledWholeProfile(inputs, raw, sha256(raw).hexdigest())


@lru_cache(maxsize=2)
def _compile_source_bytes(raw: bytes) -> bytes:
    """Cache immutable validated bytes only; callers always obtain a fresh typed profile."""
    value = parse_json(raw)
    validate_document(value)
    if canonical_bytes(normalize(value)) != raw:
        raise ValueError("Whole public choices must use normalized canonical bytes")
    bundle, conveyor, _ = _pinned_reference()
    try:
        profile, buffers = decode(bundle, conveyor, value)
        bound = bind_whole_source(bundle, conveyor, profile, buffers)
        inputs = freeze_whole_source(bound, value["horizon_tick"], value["end_tick"])
    except KeyError as exc:
        raise ValueError(f"Unknown source or declared whole profile reference: {exc}") from exc
    return inputs.frozen_bytes
