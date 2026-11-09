"""Independent observation arithmetic and malformed-input probes; no source DES."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any, cast

import pytest

from app.v3.storage_fullness_models import ModuleCapacity, SlotCapacity, SlotLoad
from app.v3.storage_fullness_projection import project_storage


def hand_capacity() -> tuple[tuple[SlotCapacity, ...], tuple[ModuleCapacity, ...]]:
    slots = (
        SlotCapacity("a", "m1", "x", True, False, False, 2, F(10), F(2)),
        SlotCapacity("b", "m1", "x", True, False, False, 2, F(14), F(3)),
        SlotCapacity("c", "m2", "y", True, False, False, 1, F(9), F(2)),
        SlotCapacity("d", "m2", "y", False, True, True, 1, F(7), F(1)),
    )
    return slots, (ModuleCapacity("m1", 3, F(20)), ModuleCapacity("m2", 2, F(12)))


def hand_loads() -> tuple[SlotLoad, ...]:
    return (
        SlotLoad("a", 2, 3, F(8), F(3, 2)),
        SlotLoad("c", 1, 0, F(1, 4), F(1, 2)),
        SlotLoad("d", 1, 1, F(7), F(1, 2)),
    )


def test_peer_distinct_denominators_and_overlapping_reserved_occupied() -> None:
    report = project_storage(*hand_capacity(), hand_loads(), ("a", "b", "d"))
    total = report["total"]
    assert (total["physical_slots"], total["occupied_slots"], total["empty_slots"]) == (4, 3, 1)
    assert (total["active_slots"], total["active_occupied_slots"], total["active_empty_slots"]) == (
        3,
        2,
        1,
    )
    assert (total["containers"], total["units"], total["reserved_slots"]) == (4, 4, 3)
    assert total["unreserved_active_empty_slots"] == 0
    assert total["occupied_fraction"] == {"numerator": 3, "denominator": 4}
    assert total["active_occupied_fraction"] == {"numerator": 2, "denominator": 3}
    assert total["slot_payload_fraction"] == {"numerator": 61, "denominator": 160}
    assert total["volume_fraction"] == {"numerator": 5, "denominator": 16}
    modules = {r["module_id"]: r for r in report["modules"]}
    assert modules["m1"]["slot_payload_fraction"] == {"numerator": 1, "denominator": 3}
    assert modules["m1"]["module_payload_fraction"] == {"numerator": 2, "denominator": 5}
    assert modules["m2"]["module_payload_fraction"] == {"numerator": 29, "denominator": 48}
    assert modules["m1"]["hu_capacity"] == 4
    assert modules["m1"]["module_hu_capacity"] == 3
    empty_wrapper = next(s for s in report["slots"] if s["slot_id"] == "c")
    assert empty_wrapper["occupied"] is True and empty_wrapper["units"] == 0
    assert empty_wrapper["gross_mass_kg"] == {"numerator": 1, "denominator": 4}
    assert report["operational_admission"] is False


def test_peer_permuted_inputs_and_explicit_empty_observation_are_identical() -> None:
    slots, modules = hand_capacity()
    first = project_storage(slots, modules, hand_loads(), ("b", "a"))
    second = project_storage(
        tuple(reversed(slots)),
        tuple(reversed(modules)),
        (*reversed(hand_loads()), SlotLoad("b", 0, 0, F(0), F(0))),
        ("a", "b"),
    )
    assert first == second


def test_peer_zero_capacity_universe_uses_unavailable_ratios() -> None:
    report = project_storage((), (), (), ())
    assert report["slots"] == [] and report["modules"] == [] and report["zones"] == []
    for name in (
        "occupied_fraction",
        "active_occupied_fraction",
        "slot_payload_fraction",
        "volume_fraction",
    ):
        assert report["total"][name] is None


def test_peer_module_hu_cap_is_not_sum_of_slot_hu_caps() -> None:
    slots, modules = hand_capacity()
    loads = (SlotLoad("a", 2, 1, F(1), F(1)), SlotLoad("b", 2, 1, F(1), F(1)))
    with pytest.raises(ValueError, match="module HU"):
        project_storage(slots, modules, loads, ())


def test_peer_module_payload_is_not_sum_of_slot_payloads() -> None:
    slots, modules = hand_capacity()
    loads = (SlotLoad("a", 1, 1, F(9), F(1)), SlotLoad("b", 1, 1, F(12), F(1)))
    with pytest.raises(ValueError, match="module payload"):
        project_storage(slots, modules, loads, ())


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot_id", None),
        ("module_id", False),
        ("zone_id", "  "),
        ("active", 1),
        ("reserve_only", 0),
        ("blocked", 0),
        ("hu_capacity", True),
        ("hu_capacity", F(2)),
        ("payload_kg", 10),
        ("usable_volume_m3", 2.0),
        ("usable_volume_m3", F(0)),
    ],
)
def test_peer_bad_capacity_scalar_rejects(field: str, value: Any) -> None:
    slots, modules = hand_capacity()
    with pytest.raises(ValueError):
        project_storage((replace(slots[0], **{field: value}), *slots[1:]), modules, (), ())


@pytest.mark.parametrize(
    "field,value",
    [
        ("module_id", True),
        ("hu_capacity", True),
        ("payload_kg", 20),
        ("payload_kg", F(-1)),
    ],
)
def test_peer_bad_module_scalar_rejects(field: str, value: Any) -> None:
    slots, modules = hand_capacity()
    with pytest.raises(ValueError):
        project_storage(slots, (replace(modules[0], **{field: value}), modules[1]), (), ())


@pytest.mark.parametrize(
    "field,value",
    [
        ("containers", False),
        ("units", False),
        ("gross_mass_kg", 8),
        ("outer_volume_m3", 1.5),
        ("units", F(3)),
        ("gross_mass_kg", F(-1)),
    ],
)
def test_peer_bad_observation_scalar_rejects(field: str, value: Any) -> None:
    load = replace(hand_loads()[0], **{field: value})
    with pytest.raises(ValueError):
        project_storage(*hand_capacity(), (load,), ())


def test_peer_mutable_outer_collections_and_duplicate_capacity_reject() -> None:
    slots, modules = hand_capacity()
    with pytest.raises(ValueError):
        project_storage(cast(Any, list(slots)), modules, (), ())
    with pytest.raises(ValueError):
        project_storage(slots, modules, cast(Any, []), ())
    with pytest.raises(ValueError):
        project_storage(slots, modules, (), cast(Any, []))
    with pytest.raises(ValueError):
        project_storage(slots, (*modules, modules[0]), (), ())


def test_peer_unknown_or_duplicate_reservations_reject() -> None:
    with pytest.raises(ValueError):
        project_storage(*hand_capacity(), (), ("m1",))
    with pytest.raises(ValueError):
        project_storage(*hand_capacity(), (), ("a", "a"))


@pytest.mark.parametrize("kind", ["mutable_pair", "string_subclass"])
def test_peer_source_fingerprints_require_exact_immutable_rows(kind: str) -> None:
    from app.v3.storage_fullness_source import source_capacities
    from tests.v3.test_storage_fullness_source import source_profile

    class Alias(str):
        pass

    value = source_profile()
    receipts = value.world.receipts
    flow = receipts.flow
    path, digest = flow.source_hashes[0]
    changed: Any = [path, digest] if kind == "mutable_pair" else (path, Alias(digest))
    flow = replace(flow, source_hashes=(changed, *flow.source_hashes[1:]))
    value = replace(value, world=replace(value.world, receipts=replace(receipts, flow=flow)))
    with pytest.raises(ValueError):
        source_capacities(value)


@pytest.mark.parametrize("prefix", ["receipt", "whole", "relocation"])
def test_peer_current_storage_place_lease_is_observed(prefix: str) -> None:
    from app.v3.storage_fullness_observation import slot_reservations
    from tests.v3.test_coordinator_kpi_fixtures import point, profile

    observed = point(profile(), 0)
    slot = "v3:slot:hand"
    observed = replace(
        observed,
        leases=(
            (prefix + ":place:" + slot, "J"),
            (prefix + ":place:buffer-hand", "J"),
            ("role:worker:S01", "J"),
        ),
    )
    assert slot_reservations(observed, frozenset((slot,))) == (slot,)


@pytest.mark.parametrize(
    "leases",
    [
        (("new:place:v3:slot:hand", "J"),),
        (("receipt:place:v3:slot:missing", "J"),),
        (("receipt:place:v3:slot:hand", "J"), ("receipt:place:v3:slot:hand", "J")),
        (("receipt:place:v3:slot:hand", False),),
    ],
)
def test_peer_malformed_or_unknown_storage_lease_rejects(leases: Any) -> None:
    from app.v3.storage_fullness_observation import slot_reservations
    from tests.v3.test_coordinator_kpi_fixtures import point, profile

    observed = replace(point(profile(), 0), leases=leases)
    with pytest.raises(ValueError):
        slot_reservations(observed, frozenset(("v3:slot:hand",)))


def test_peer_outer_volume_uses_actual_container_not_unit_count() -> None:
    from app.v3.coordinator_metrics_inventory import inventory
    from app.v3.storage_fullness_observation import slot_loads
    from tests.v3.test_coordinator_kpi_fixtures import outcome, point, profile

    value = profile()
    observed = point(value, 0)
    owners = inventory(value, outcome(observed), observed)["owners"]
    slots = frozenset(row["owner_id"] for row in owners if row["kind"] == "slot")
    loads = slot_loads(observed, owners, slots)
    expected = {key: F(0) for key in slots}
    for container in observed.stock.containers:
        if container.owner_id in slots:
            x, y, z = container.recipe.outer
            expected[container.owner_id] += x * y * z
    assert {row.slot_id: row.outer_volume_m3 for row in loads} == expected
    assert all(row.outer_volume_m3 > 0 for row in loads if row.containers)


def test_peer_missing_analytical_denominator_is_not_invented() -> None:
    from app.v3.storage_fullness import coordinator_storage_fullness
    from tests.v3.test_coordinator_kpi_fixtures import outcome, point, profile

    value = profile()
    observed = point(value, 0)
    report = coordinator_storage_fullness(value, outcome(observed), observed)
    assert report["available"] is False and report["value"] is None
    assert "total" not in report
