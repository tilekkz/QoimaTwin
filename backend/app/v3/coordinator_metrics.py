"""Native C metrics preserve multiple physical resources and staffing completion boundaries."""

from app.v3.coordinator_metrics_observed import observed_kpis
from app.v3.coordinator_metrics_ports import ports
from app.v3.coordinator_metrics_staff import assignment, labor
from app.v3.coordinator_metrics_values import business, integer
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.flow_profile_wire import record
from app.v3.interface import Json

METRICS_VERSION = "qoima-staff-coordinator-metrics-v2"


def _whole_offers(profile: CoordinatorProfile) -> dict[str, tuple[int, int]]:
    quantities: dict[str, int] = {}
    for token in profile.world.receipts.flow.stock.units:
        quantities[token.origin_hu] = quantities.get(token.origin_hu, 0) + 1
    for offer in profile.world.receipts.receipts:
        quantities[offer.definition.hu_id] = offer.definition.quantity_units
    return {
        order.job_id: (order.arrival_tick, quantities[order.hu_id])
        for order in profile.world.orders
    }


def _receipts(profile: CoordinatorProfile, snapshot: CoordinatorSnapshot) -> Json:
    offers = {r.definition.receipt_id: r for r in profile.world.receipts.receipts}
    if len(snapshot.receipts) != len(offers) or {r.receipt_id for r in snapshot.receipts} != set(
        offers
    ):
        raise ValueError("Coordinator metric receipt identities differ")
    arrived = sum(r.arrival_tick <= snapshot.tick for r in offers.values())
    credited = [r for r in snapshot.receipts if r.credited_tick is not None]
    placed = [r for r in snapshot.receipts if r.placed_tick is not None]
    returned = [r for r in snapshot.receipts if r.returned_tick is not None]
    return {
        "arrived_receipts": arrived,
        "credited_receipts": len(credited),
        "credited_units": sum(offers[r.receipt_id].definition.quantity_units for r in credited),
        "putaway_receipts": len(placed),
        "returned_receipts": len(returned),
        "pending_putaway": arrived - len(placed),
        "pending_return": arrived - len(returned),
    }


def _resources(profile: CoordinatorProfile, snapshot: CoordinatorSnapshot) -> Json:
    resources = profile.unit_resources
    cart_ids = (
        {c.cart.cart_id for c in resources.carts}
        if resources
        else {profile.world.receipts.flow.cart.cart_id}
    )
    if len(snapshot.carts) != len(cart_ids) or {c.cart_id for c in snapshot.carts} != cart_ids:
        raise ValueError("Coordinator metrics cannot drop or duplicate physical carts")
    return {
        "worker_count": len(snapshot.workers),
        "cart_count": len(snapshot.carts),
        "busy_cart_count": sum(
            c.operation is not None or c.order_id is not None for c in snapshot.carts
        ),
        "active_claims": len(snapshot.inventory.claims),
        "active_engine_leases": len(snapshot.leases),
        "active_belt_leases": len(snapshot.belt.leases),
        "active_role_bindings": len(snapshot.role_bindings),
    }


def _window(
    profile: CoordinatorProfile, outcome: CoordinatorOutcome, point: CoordinatorSnapshot
) -> Json:
    tick = integer(point.tick)
    flow = profile.world.receipts.flow
    offers = {o.order_id: (o.arrival_tick, len(o.package_placements)) for o in flow.orders}
    return {
        "tick": tick,
        "unit": business(record(point.orders), offers, "order_id", tick),
        "whole": business(record(point.whole_orders), _whole_offers(profile), "job_id", tick),
        "receipts": _receipts(profile, point),
        "labor": labor(profile, outcome, point),
        "role_assignment": assignment(point),
        "resources": _resources(profile, point),
        "ports": ports(profile, outcome, point),
        "observed": observed_kpis(profile, outcome, point),
    }


def summary(profile: CoordinatorProfile, outcome: CoordinatorOutcome) -> Json:
    return {
        "metrics_version": METRICS_VERSION,
        "counts_boundary": "settled_tick_inclusive",
        "integral_window": "[0,T)",
        "cycle_completion": "actual_business_handover_excluding_paid_return",
        "at_horizon": _window(profile, outcome, outcome.at_horizon),
        "at_end": _window(profile, outcome, outcome.at_end),
        "completion": {
            "business_complete_tick": outcome.business_complete_tick,
            "resource_drained_tick": outcome.resource_drained_tick,
            "observation_end_tick": outcome.observation_end_tick,
            "staffing_status": outcome.staffing_status,
            "constraint_violations": record(outcome.constraint_violations),
        },
    }
