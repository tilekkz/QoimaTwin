"""Exact dimensional and microsecond hand oracles for static conveyor prerequisites."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.conveyor_models import ConveyorPayload, ConveyorSource
from app.v3.conveyor_primitives import admit_payload, edge_requirements, edge_timing
from app.v3.conveyor_source import load_conveyor_source
from app.v3.inputs import load_v3_bundle


@pytest.fixture(scope="module")
def source() -> ConveyorSource:
    return load_conveyor_source(load_v3_bundle(Path("data/v3-proposal")))


def payload() -> ConveyorPayload:
    return ConveyorPayload(
        "carrier1",
        "order_tote",
        (F(".6"), F(".3"), F(".4")),
        F(15),
        "upright_xyz",
        "order1",
        "explicit-fixture-v1",
    )


def test_exact_boundary_has_no_epsilon_or_tote_recipe_default(source: ConveyorSource) -> None:
    assert admit_payload(source, payload()).eligible
    assert admit_payload(
        source, replace(payload(), dimensions_xyz_m=(F(".6"), F(".34"), F(".4")))
    ).eligible
    assert admit_payload(source, replace(payload(), gross_mass_kg=F("15.00000000001"))).reasons == (
        "PAYLOAD_OVERWEIGHT",
    )
    assert admit_payload(
        source, replace(payload(), dimensions_xyz_m=(F(".60000000001"), F(".3"), F(".4")))
    ).reasons == ("FOOTPRINT_MISMATCH",)
    assert admit_payload(
        source, replace(payload(), dimensions_xyz_m=(F(".6"), F(".40000000001"), F(".4")))
    ).reasons == ("HEIGHT_MISMATCH",)


@pytest.mark.parametrize(
    "kind", ["HEAVY_BOX", "PALLET_LOAD", "IBC", "LONG_BUNDLE", "DRUM", "FRAGILE_CRATE", "unknown"]
)
def test_kind_cannot_be_laundered_with_tiny_visual_dimensions(
    source: ConveyorSource, kind: str
) -> None:
    value = replace(payload(), kind=kind, dimensions_xyz_m=(F(".1"),) * 3, gross_mass_kg=F(1))
    assert admit_payload(source, value).reasons == ("KIND_FORBIDDEN",)


def test_orientation_and_parent_identity_required(source: ConveyorSource) -> None:
    assert admit_payload(source, replace(payload(), orientation="yaw90")).reasons == (
        "ORIENTATION_FORBIDDEN",
    )
    with pytest.raises(ValueError):
        replace(payload(), parent_id="")
    with pytest.raises(ValueError):
        replace(payload(), gross_mass_kg=F(0))


@pytest.mark.parametrize("kind", ["order_tote", "sealed_parcel", "SMALL_CARTON", "STANDARD_CARTON"])
def test_all_four_source_kinds_fit_at_the_exact_height_limit(
    source: ConveyorSource, kind: str
) -> None:
    value = replace(payload(), kind=kind, dimensions_xyz_m=(F(".6"), F(".4"), F(".4")))
    result = admit_payload(source, value)
    assert result.eligible and result.operational_admission is False
    assert F(".6") ** 2 + F(".4") ** 2 == F(".52")
    assert (source.usable_width_m - 2 * source.clearance_m) ** 2 == F(".6084")


def test_pivot_clearance_uses_exact_squared_diagonal(source: ConveyorSource) -> None:
    narrow = replace(source, usable_width_m=F(".76"))
    assert admit_payload(narrow, payload()).reasons == ("PIVOT_CLEARANCE",)
    # .72**2=.5184 is below the .52 rectangle diagonal squared.


def test_unknown_edge_cannot_acquire_declared_resources(source: ConveyorSource) -> None:
    with pytest.raises(ValueError):
        edge_requirements(source, "missing", ())


def test_timing_uses_bound_length_and_preturn_operation(source: ConveyorSource) -> None:
    timing = edge_timing(source, "v3:conv:PK01:divert")
    assert timing.motion_seconds == F(10, 11)  # .5/.55
    assert timing.dwell_seconds == F(4, 5)
    assert (timing.motion_ticks, timing.dwell_ticks, timing.total_ticks) == (
        909091,
        800000,
        1709091,
    )
    assert timing.turn_node_id == "v3:conv:PK01:C"
    assert timing.turn_timing == "before_edge"
    merge = edge_timing(source, "v3:conv:PK01:merge")
    assert merge.turn_timing == "after_edge"
    assert merge.turn_node_id == "v3:conv:PK01:C"
    assert merge.total_ticks == 1709091
    arc = edge_timing(source, "v3:conv:entry-arc")
    assert arc.motion_seconds == F("1.9634954084936207") / F(".55")
    assert arc.motion_ticks == 3569992
    assert arc.dwell_ticks == 0
    with pytest.raises(ValueError):
        edge_timing(source, "missing")


def test_requirements_reserve_cells_and_exclusive_resource_separately(
    source: ConveyorSource,
) -> None:
    curve = source.resources["V3_CURVE_EXCLUSIVE"].cell_ids
    result = edge_requirements(source, "v3:conv:entry-arc", curve[:2])
    assert result.cell_ids == tuple(sorted(curve[:2]))
    assert result.exclusive_resource_ids == ("V3_CURVE_EXCLUSIVE",)
    assert result.live_grant is False
    main_edge = next(e.edge_id for e in source.edges.values() if e.resource_id == "V3_MAIN")
    main = source.resources["V3_MAIN"].cell_ids[:2]
    assert edge_requirements(source, main_edge, main).exclusive_resource_ids == ()
    for cells in ((), ("missing",), main, (curve[0], curve[0])):
        with pytest.raises(ValueError):
            edge_requirements(source, "v3:conv:entry-arc", cells)
