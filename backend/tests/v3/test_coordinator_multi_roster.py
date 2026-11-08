"""All six stations and twelve original pickers share two explicitly finite carts."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units_models import UnitAssignment
from app.v3.light_flow_models import FlowOrder
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import Placement
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_light_flow_fixtures import hand_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def roster_orders() -> tuple[FlowOrder, ...]:
    result = []
    for index in range(12):
        units = tuple(
            Placement(f"U{2 * index + j + 1}", (F(7 * j, 100), F(0), F(0))) for j in range(2)
        )
        result.append(
            FlowOrder(
                f"O{index + 1}",
                200 * SECOND,
                "HU1",
                "SLOT",
                f"C{index + 1}",
                f"P{index + 1}",
                units,
                units,
            )
        )
    return tuple(result)


def roster_profile() -> CoordinatorProfile:
    p, material = multi_profile(candidate=False, two_carts=True), hand_profile(orders=12)
    r, flow = p.unit_resources, p.world.receipts.flow
    assert r is not None
    capacities = {o.owner_id: o.capacity for o in material.owners}
    owners = tuple(replace(o, capacity=capacities.get(o.owner_id, o.capacity)) for o in flow.owners)
    owners += tuple(o for o in material.owners if o.owner_id not in {v.owner_id for v in owners})
    materials = tuple(
        replace(c, owner_id="pool" + f"{(int(c.container_id[1:]) - 1) % 6 + 1:02}")
        if c.container_id.startswith("P") and int(c.container_id[1:]) % 6
        else c
        for c in material.materials
    )
    arcs = list(flow.graph.arcs)
    for home, distance in (("H11", 4), ("H12", 6)):
        for a, b in ((home, "H"), ("H", home)):
            arcs.append(
                Arc(
                    f"roster:{a}:{b}",
                    a,
                    b,
                    F(distance),
                    F(distance),
                    modes=frozenset({"pedestrian"}),
                )
            )
    flow = replace(
        flow,
        graph=DirectedGraph("roster-hand", flow.graph.node_ids, arcs),
        owners=owners,
        materials=materials,
        orders=roster_orders(),
    )
    assignments = tuple(
        UnitAssignment(
            f"O{i}",
            f"P{i:02}",
            f"CART{(i - 1) % 2 + 1:02}",
            f"PK{(i - 1) % 6 + 1:02}",
            f"S{(i - 1) % 2 + 1:02}",
            flow.port.port_id,
        )
        for i in range(1, 13)
    )
    return replace(
        p,
        unit_resources=replace(r, assignments=assignments),
        world=replace(p.world, receipts=replace(p.world.receipts, flow=flow)),
    )


@pytest.mark.slow
def test_six_stations_twelve_pickers_use_one_inventory_and_two_actual_carts() -> None:
    result = CoordinatorEngine(roster_profile(), receipt_conveyor()).run(
        1000 * SECOND, 2000 * SECOND
    )
    assert result.status == "complete" and result.staffing_status == "valid"
    assert {c.picker_id for c in result.at_end.unit_contexts} == {f"P{i:02}" for i in range(1, 13)}
    assert {p.station_id for p in result.at_end.packing} == {f"PK{i:02}" for i in range(1, 7)}
    assert {p.actor_id for p in result.at_end.packing} == {f"K{i:02}" for i in range(1, 7)}
    assert len(result.at_end.workers) == 24 and len(result.at_end.carts) == 2
    assert len(result.at_end.orders) == 12 and not result.at_end.leases
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 24}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert result.at_end.balance.gross_mass_kg == F("3.94")
    assert all(
        c.node == "H" and c.order_id is None and c.operation is None for c in result.at_end.carts
    )
