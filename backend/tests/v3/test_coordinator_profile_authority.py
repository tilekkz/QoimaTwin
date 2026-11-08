"""Raw and typed source authority probes, scheduled for the final assembled checks."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import coordinator_document, coordinator_sources

__all__ = ["coordinator_sources"]


def test_supplied_conveyor_typed_fraction_cannot_impersonate_dict(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    bundle, source = coordinator_sources
    changed = deepcopy(dict(source.edges))
    edge = next(iter(changed.values()))
    object.__setattr__(edge, "length_m", {"numerator": 1, "denominator": 1})
    forged = replace(source, edges=changed)
    with pytest.raises(ValueError):
        compile_coordinator_profile(bundle, forged, coordinator_document())


def test_same_size_raw_evidence_change_is_not_hidden_by_retained_bundle(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_bytes = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = read_bytes(path)
        if path.name == "port-resource-policy-v3.json":
            return raw.replace(b'"P01"', b'"P13"', 1)
        return raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, coordinator_document())


@pytest.mark.parametrize(
    "table,key",
    [
        ("carts", "cart_id"),
        ("goods_stations", "station_id"),
        ("unit_assignments", "order_id"),
        ("parcel_ports", "port_id"),
    ],
)
def test_duplicate_resource_identity_is_rejected(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    table: str,
    key: str,
) -> None:
    value = coordinator_document()
    duplicate = deepcopy(value[table][0])
    assert duplicate[key]
    value[table].append(duplicate)
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, value)


@pytest.mark.parametrize("value", [True, 1.0, {"numerator": 1, "denominator": 1}])
def test_nested_registry_clock_types_are_never_coerced(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    value: Any,
) -> None:
    choices = coordinator_document()
    choices["registry"]["unavailability"][0]["start_tick"] = value
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, choices)
