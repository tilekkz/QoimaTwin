"""Business WIP and receipt queue integrals; future offers and paid returns are excluded."""

from app.v3.coordinator_metrics_observed_values import elapsed
from app.v3.coordinator_metrics_values import integer, ratio
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.interface import Json


def queues(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> Json:
    del outcome  # Completed transition facts in this exact snapshot are sufficient.
    unit = sum(
        elapsed(o.admitted_tick, o.shipped_tick, point.tick)
        for o in point.orders
        if o.admitted_tick is not None
    )
    whole = sum(
        elapsed(o.admitted_tick, o.shipped_tick, point.tick)
        for o in point.whole_orders
        if o.admitted_tick is not None
    )
    arrivals = {r.definition.receipt_id: r.arrival_tick for r in profile.world.receipts.receipts}
    if {r.receipt_id for r in point.receipts} != set(arrivals):
        raise ValueError("KPI receipt identities differ")
    waiting = unplaced = 0
    for receipt in point.receipts:
        for tick in (receipt.admitted_tick, receipt.credited_tick, receipt.placed_tick):
            if tick is not None and integer(tick) > point.tick:
                raise ValueError("KPI receipt transition exceeds observation")
        waiting += elapsed(arrivals[receipt.receipt_id], receipt.admitted_tick, point.tick)
        if receipt.credited_tick is not None:
            unplaced += elapsed(receipt.credited_tick, receipt.placed_tick, point.tick)
    return {
        "unit_admitted_business_wip_ticks": unit,
        "unit_mean_admitted_business_wip": ratio(unit, point.tick),
        "whole_admitted_business_wip_ticks": whole,
        "whole_mean_admitted_business_wip": ratio(whole, point.tick),
        "receipt_unadmitted_ticks": waiting,
        "mean_unadmitted_receipts": ratio(waiting, point.tick),
        "credited_unplaced_hu_ticks": unplaced,
        "mean_credited_unplaced_hus": ratio(unplaced, point.tick),
        "scope": "business_not_paid_return; unit_and_whole_unadmitted_in_existing_business_metrics",
    }
