"""Reuse pinned offline loaders to prevent typed objects from inheriting stale raw hashes."""

import hashlib
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from functools import cache
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.flow_profile_wire import record, source_record
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle


@cache
def _pinned_reference() -> tuple[V3Bundle, ConveyorSource, tuple[str, str]]:
    root = Path(__file__).resolve().parents[2] / "data"
    bundle = load_v3_bundle(root / "v3-proposal")
    conveyor = load_conveyor_source(bundle, root / "v3-conveyor-proposal")
    return bundle, conveyor, (_digest(source_record(bundle)), _digest(record(conveyor)))


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _same_types(actual: Any, expected: Any) -> bool:
    """Preserve exact nested types and the verified canonical document byte representation."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, bytes):
        return bool(actual == expected)
    if is_dataclass(expected) and not isinstance(expected, type):
        return all(
            _same_types(getattr(actual, f.name), getattr(expected, f.name))
            for f in fields(expected)
        )
    if isinstance(expected, Mapping):
        return actual.keys() == expected.keys() and all(
            _same_types(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(
            _same_types(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return True


def verified_records(bundle: V3Bundle, conveyor: ConveyorSource) -> dict[str, Any]:
    reference_bundle, reference_conveyor, digests = _pinned_reference()
    if not _same_types(bundle, reference_bundle) or not _same_types(conveyor, reference_conveyor):
        raise ValueError("Supplied typed source shape differs from verified pinned inputs")
    source, belt = source_record(bundle), record(conveyor)
    if (_digest(source), _digest(belt)) != digests:
        raise ValueError("Supplied source facts/documents differ from verified pinned inputs")
    return {"source": source, "conveyor": belt}
