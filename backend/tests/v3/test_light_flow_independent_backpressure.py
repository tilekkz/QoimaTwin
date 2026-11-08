"""Finite humans, station storage and sink occupancy must produce physical waiting."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile
from tests.v3.test_light_flow_independent_helpers import (
    SECOND,
    assert_whole_material_mass,
    container,
    run_flow,
    transaction_ticks,
    unit_ids,
)


def test_unavailable_packer_retains_station_spur_and_blocks_the_second_carrier() -> None:
    result = run_flow(
        hand_profile(orders=2, packer_ready=1000 * SECOND), 100 * SECOND, 100 * SECOND
    )
    snapshot = result.at_end
    first = next(c for c in snapshot.belt.carriers if c.payload_id == "C1")
    assert first.pose is not None and first.pose.edge_id == "v3:conv:PK06:spur-in"
    assert first.pose.progress == 1 and first.motion is None
    spur = "resource:" + source_catalog().stations["PK06"].spur_resource_id
    assert (spur, first.job_id) in snapshot.belt.leases
    assert len(snapshot.belt.carriers) == 2 and snapshot.belt.queue_ticks > 0
    assert not transaction_ticks(result, "pack") and not transaction_ticks(result, "ship")
    assert result.status == "partial"
    assert unit_ids(snapshot, "C1") == {"U1", "U2", "U3"}
    assert unit_ids(snapshot, "C2") == {"U4", "U5", "U6"}
    assert_whole_material_mass(snapshot, F(36, 25))


def test_unavailable_shipper_holds_physical_sink_and_propagates_backpressure() -> None:
    result = run_flow(
        hand_profile(orders=2, shipper_ready=1000 * SECOND), 210 * SECOND, 210 * SECOND
    )
    snapshot = result.at_end
    first = next(c for c in snapshot.belt.carriers if c.payload_id == "P1")
    assert first.pose is not None and first.pose.edge_id == "v3:conv:main-tail"
    assert first.pose.progress == 1 and first.motion is None and first.occupied_cells
    for cell in first.occupied_cells:
        assert ("cell:" + cell, first.job_id) in snapshot.belt.leases
    second = next(c for c in snapshot.belt.carriers if c.payload_id == "P2")
    assert second.motion is None and snapshot.belt.queue_ticks > 0
    assert not transaction_ticks(result, "ship") and result.status == "partial"
    assert container(snapshot, "P1").owner_id == "belt:O1"
    assert_whole_material_mass(snapshot, F(36, 25))


def test_full_empty_carrier_rack_prevents_second_pack_without_return_teleport() -> None:
    profile = hand_profile(orders=2)
    owners = tuple(replace(o, capacity=1) if o.owner_id == "empties" else o for o in profile.owners)
    result = run_flow(replace(profile, owners=owners), 300 * SECOND, 300 * SECOND)
    snapshot = result.at_end
    assert result.status == "partial" and transaction_ticks(result, "ship") == (192_170_000,)
    assert container(snapshot, "C1").owner_id == "empties"
    assert container(snapshot, "C2").owner_id == "belt:O2"
    assert unit_ids(snapshot, "C2") == {"U4", "U5", "U6"}
    assert container(snapshot, "P2").sealed_for is None
    assert sum(c.owner_id == "empties" for c in snapshot.stock.containers) == 1
    assert_whole_material_mass(snapshot, F(36, 25))


def test_unknown_required_parcel_material_is_rejected_instead_of_created() -> None:
    profile = hand_profile(orders=2)
    materials = tuple(c for c in profile.materials if c.container_id != "P2")
    with pytest.raises(ValueError):
        run_flow(replace(profile, materials=materials), 300 * SECOND, 300 * SECOND)
