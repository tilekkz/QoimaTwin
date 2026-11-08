"""Reverify raw pinned inputs; retained hashes and cached typed objects are not authority."""

from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.conveyor_source import load_conveyor_source
from app.v3.flow_profile_sources import _same_types
from app.v3.flow_profile_wire import record, source_record
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle


def authoritative_sources() -> tuple[V3Bundle, ConveyorSource]:
    root = Path(__file__).resolve().parents[2] / "data"
    bundle = load_v3_bundle(root / "v3-proposal")
    return bundle, load_conveyor_source(bundle, root / "v3-conveyor-proposal")


def verified(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
) -> tuple[V3Bundle, ConveyorSource, dict[str, Any]]:
    if type(bundle) is not V3Bundle or type(conveyor) is not ConveyorSource:
        raise ValueError("Exact typed source bundle and conveyor required")
    actual_bundle, actual_conveyor = authoritative_sources()
    _compare(bundle, actual_bundle, source_record(bundle), source_record(actual_bundle))
    _compare(conveyor, actual_conveyor, record(conveyor), record(actual_conveyor))
    return (
        actual_bundle,
        actual_conveyor,
        {
            "source": source_record(actual_bundle),
            "conveyor": record(actual_conveyor),
        },
    )


def _compare(given: Any, actual: Any, supplied_record: Any, actual_record: Any) -> None:
    if not _same_types(given, actual):
        raise ValueError("Coordinator source exact typed authority mismatch")
    if canonical_bytes(supplied_record) != canonical_bytes(actual_record):
        raise ValueError("Coordinator source raw/typed facts differ from pinned authority")
