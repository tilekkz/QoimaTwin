"""Written before the compiler; execution deferred to the final assembled gate."""

from copy import deepcopy
from typing import Any

import pytest

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_profile import compile_coordinator_profile, load_coordinator_inputs
from app.v3.input_models import V3Bundle
from tests.v3.test_coordinator_profile_fixtures import (
    coordinator_document,
    coordinator_sources,
    with_whole_receipt,
)

__all__ = ["coordinator_sources"]


def test_source_bound_resources_preserve_24_workers_and_original_stock(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    compiled = compile_coordinator_profile(*coordinator_sources, coordinator_document())
    profile = compiled.profile
    resources = profile.unit_resources
    assert resources is not None
    assert len(resources.stations) == 6 and len(resources.pickers) == 12
    assert len(profile.world.receipts.flow.actors) == 24 and len(resources.carts) == 2
    assert len(profile.world.receipts.flow.stock.units) == 12_256
    assert len(profile.world.receipts.flow.stock.containers) == 530
    for station in resources.stations:
        assert station.station.node == "v3:service:" + station.station.station_id
        source = coordinator_sources[1].stations[station.station.station_id]
        edges = coordinator_sources[1].edges
        assert sum(edges[key].target == source.work_node_id for key in station.belt_route) == 1
    restored = load_coordinator_inputs(compiled.frozen_bytes)
    assert restored.input_hash == compiled.input_hash
    assert restored.profile is not compiled.profile


def test_all_declared_materials_and_whole_receipts_share_one_world(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    compiled = compile_coordinator_profile(
        *coordinator_sources, with_whole_receipt(coordinator_document())
    )
    world = compiled.profile.world
    assert len(world.receipts.receipts) == len(world.orders) == 1
    assert world.orders[0].hu_id == world.receipts.receipts[0].definition.hu_id
    assert len(world.receipts.flow.stock.units) == 12_256
    assert world.receipts.receipts[0].definition.hu_id not in {
        row.container_id for row in world.receipts.flow.stock.containers
    }


def test_unordered_tables_have_stable_frozen_identity(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    value = coordinator_document()
    changed = deepcopy(value)
    for key in (
        "actors",
        "owners",
        "orders",
        "materials",
        "recipes",
        "carts",
        "goods_stations",
        "picker_bindings",
        "parcel_ports",
        "unit_assignments",
    ):
        changed[key].reverse()
    for key in ("workers", "unavailability", "station_bindings"):
        changed["registry"][key].reverse()
    left = compile_coordinator_profile(*coordinator_sources, value)
    right = compile_coordinator_profile(*coordinator_sources, changed)
    assert left.frozen_bytes == right.frozen_bytes


@pytest.mark.parametrize("change", ["release", "horizon", "break", "assignment"])
def test_real_choices_change_full_identity_without_inventing_common_ab_hash(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    change: str,
) -> None:
    value, changed = coordinator_document(), coordinator_document()
    if change == "release":
        changed["carts"][0]["release_tick"] += 1
    elif change == "horizon":
        changed["horizon_tick"] -= 1
    elif change == "break":
        changed["registry"]["unavailability"][0]["reason"] = "different declared break"
    else:
        changed["unit_assignments"][0]["picker_id"] = "P03"
    left = compile_coordinator_profile(*coordinator_sources, value)
    right = compile_coordinator_profile(*coordinator_sources, changed)
    assert left.input_hash != right.input_hash
    assert (left.registry_common_hash != right.registry_common_hash) == (change == "break")


@pytest.mark.parametrize("field", ["graph", "stock", "input_hash", "registry_common_hash"])
def test_no_caller_derived_authority_fields(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    field: str,
) -> None:
    value = coordinator_document()
    value[field] = {}
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, value)


@pytest.mark.parametrize("bad", [True, 1.0, -1])
def test_exact_nested_cart_duration(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
    bad: Any,
) -> None:
    value = coordinator_document()
    value["carts"][0]["release_tick"] = bad
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, value)


def test_legacy_alias_restriction_does_not_force_actual_picker_assignment(
    coordinator_sources: tuple[V3Bundle, ConveyorSource],
) -> None:
    value = coordinator_document()
    value["unit_assignments"][0]["picker_id"] = "P03"
    compiled = compile_coordinator_profile(*coordinator_sources, value)
    assert compiled.profile.world.receipts.flow.picker_id == "P01"
    assert compiled.profile.unit_resources is not None
    assert compiled.profile.unit_resources.assignments[0].picker_id == "P03"
    value["default_assignment"] = {"picker_id": "P03"}
    with pytest.raises(ValueError):
        compile_coordinator_profile(*coordinator_sources, value)
