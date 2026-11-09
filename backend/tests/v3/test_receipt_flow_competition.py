"""Independent arithmetic for shared bays, finite cells and paid receiver waits."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.receipt_flow_models import ReceiptFlowProfile
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import StockOwner
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


def two_receipts(*, two_buffers: bool) -> ReceiptFlowProfile:
    profile = receipt_hand_profile()
    flow, offer = profile.flow, profile.receipts[0]
    actors = tuple(replace(a, home="RH") if a.actor_id == "R02" else a for a in flow.actors)
    owners = (
        *flow.owners,
        StockOwner("actor:R02", "worker", 1),
        StockOwner("second-slot", "slot", 1),
    )
    places = (*profile.places, replace(profile.places[1], owner_id="second-slot", node_id="SLOT2"))
    edges = [("BUFFER", "SLOT2", 5)]
    buffers: tuple[str, ...] = ("receipt-buffer",)
    if two_buffers:
        owners += (StockOwner("second-buffer", "buffer", 1),)
        places += (replace(profile.places[0], owner_id="second-buffer", node_id="BUFFER2"),)
        edges += [("RECEIVE", "BUFFER2", 3), ("BUFFER2", "SLOT2", 5), ("BUFFER2", "SLOT", 5)]
        buffers += ("second-buffer",)
    arcs = list(flow.graph.arcs)
    for a, b, distance in edges:
        for source, target in ((a, b), (b, a)):
            arcs.append(
                Arc(
                    f"{source}-{target}",
                    source,
                    target,
                    F(distance),
                    F(distance),
                    modes=frozenset({"pedestrian"}),
                    cargo_classes=frozenset({"SMALL_CARTON"}),
                    clear_width_m=F(2),
                    clear_height_m=F(3),
                )
            )
    graph = DirectedGraph(
        "two-receipts", sorted({n for a in arcs for n in (a.source, a.target)}), arcs
    )
    definition = replace(offer.definition, receipt_id="R2", hu_id="HU3")
    second = replace(offer, definition=definition, slot_owner_id="second-slot")
    port = replace(profile.ports[0], buffer_ids=buffers, receiver_ids=("R01", "R02"))
    return replace(
        profile,
        flow=replace(flow, graph=graph, actors=actors, owners=owners, orders=()),
        places=places,
        receipts=(offer, second),
        ports=(port,),
    )


def test_single_buffer_reservation_ends_only_at_physical_pickup() -> None:
    result = ReceiptFlowEngine(two_receipts(two_buffers=False), receipt_conveyor()).run(
        100 * SECOND, 100 * SECOND
    )
    first, second = result.at_end.receipts
    assert (first.admitted_tick, first.credited_tick, first.placed_tick, first.returned_tick) == (
        0,
        12 * SECOND,
        23 * SECOND,
        33 * SECOND,
    )
    assert (
        second.admitted_tick,
        second.credited_tick,
        second.placed_tick,
        second.returned_tick,
    ) == (17 * SECOND, 29 * SECOND, 40 * SECOND, 50 * SECOND)
    assert result.status == "complete" and result.at_end.tick == 50 * SECOND
    assert len(result.at_end.inventory.locations) == 72


def test_two_buffers_share_one_bay_and_queue_exposure_is_paid() -> None:
    result = ReceiptFlowEngine(two_receipts(two_buffers=True), receipt_conveyor()).run(
        100 * SECOND, 100 * SECOND
    )
    first, second = result.at_end.receipts
    assert first.credited_tick == 12 * SECOND and second.credited_tick == 22 * SECOND
    assert (second.admitted_tick, second.placed_tick, second.returned_tick) == (
        0,
        33 * SECOND,
        43 * SECOND,
    )
    receiver = next(w for w in result.at_end.workers if w.actor_id == "R02")
    assert receiver.queue_ticks == 10 * SECOND and receiver.paid_ticks == 33 * SECOND
    assert second.paid_exposure_ticks == 43 * SECOND
    acquisitions = [
        (e.tick, e.order_id)
        for e in result.events
        if e.kind == "receipt_resource_acquired"
        and getattr(e, "resource_id", None) == "receipt:port:IN_E_PARCEL"
    ]
    assert acquisitions == [(2 * SECOND, "R1"), (12 * SECOND, "R2")]


def test_queued_service_missing_horizon_is_uncredited_and_keeps_actual_reserved_resources() -> None:
    result = ReceiptFlowEngine(two_receipts(two_buffers=True), receipt_conveyor()).run(
        15 * SECOND, 50 * SECOND
    )
    first, second = result.at_end.receipts
    assert first.returned_tick == 33 * SECOND
    assert second.admitted_tick == 0 and second.credited_tick is None
    assert second.wait_reason == "service_window" and second.paid_exposure_ticks == 50 * SECOND
    assert result.status == "partial" and len(result.at_end.inventory.locations) == 48
    assert all(c.container_id != "HU3" for c in result.at_end.inventory.containers)
    assert ("receipt:worker:R02", "R2") in result.at_end.leases
