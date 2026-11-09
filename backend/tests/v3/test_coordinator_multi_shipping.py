"""Shared terminal capacity must be reserved across distinct parcel port services."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units_models import ParcelPort
from app.v3.runtime_graph import Arc, DirectedGraph
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def finite_terminal_profile() -> CoordinatorProfile:
    p = multi_profile(two_carts=True)
    flow, r = p.world.receipts.flow, p.unit_resources
    assert r is not None
    arcs = (
        *flow.graph.arcs,
        *(
            Arc(
                f"secondport:{a}:{b}",
                a,
                b,
                F(3),
                F(3),
                modes=frozenset({"pedestrian"}),
                clear_width_m=F(2),
                clear_height_m=F(3),
            )
            for a, b in (("OUT", "PORT2"), ("PORT2", "OUT"))
        ),
    )
    flow = replace(
        flow,
        graph=DirectedGraph("two-ports-one-terminal", (*flow.graph.node_ids, "PORT2"), arcs),
        orders=(flow.orders[0], replace(flow.orders[1], arrival_tick=98 * SECOND)),
        owners=tuple(replace(o, capacity=1) if o.owner_id == "shipped" else o for o in flow.owners),
    )
    port = ParcelPort(replace(flow.port, port_id="OUT_W_RETAIL", node="PORT2"), "shipped")
    r = replace(
        r,
        ports=(*r.ports, port),
        assignments=(
            r.assignments[0],
            replace(r.assignments[1], shipper_id="S02", port_id=port.port.port_id),
        ),
    )
    return replace(
        p,
        unit_resources=r,
        world=replace(p.world, ports=(), receipts=replace(p.world.receipts, flow=flow)),
    )


def test_distinct_ports_cannot_both_reserve_last_terminal_position() -> None:
    # Independent timings: first service250.17..270.17; second reaches its port268.17.
    result = CoordinatorEngine(finite_terminal_profile(), receipt_conveyor()).run(
        269 * SECOND, 269 * SECOND
    )
    workers = {w.actor_id: w for w in result.at_end.workers}
    first, second = workers["S01"], workers["S02"]
    assert first.operation is not None and first.operation.kind == "shipping_service"
    assert second.order_id == "O2" and second.operation is None
    assert second.waiting_since == 268_170_000
    assert dict(result.at_end.leases).get("port:OUT_S_EXPRESS") == "O1"
    assert "port:OUT_W_RETAIL" not in dict(result.at_end.leases)
    assert not dict(result.at_end.balance.shipped_units_by_sku)
