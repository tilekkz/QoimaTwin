"""A single original HU is consumed once; missing bindings are visible and unpriced."""

from app.v3.input_models import V3Bundle
from app.v3.outbound_placement_cost import price_candidate
from app.v3.outbound_placement_feasibility import physical_reasons, reservation_reasons
from app.v3.outbound_placement_models import (
    PlacementCandidate,
    PlacementChoices,
    PlacementEvaluation,
)
from app.v3.outbound_placement_source import customer_source_facts
from app.v3.outbound_stock_models import BoundOutboundStock
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.placement_inventory import PlacementInventory
from app.v3.workload_models import WorkloadSource


def evaluate_candidate(
    bundle: V3Bundle,
    stock: BoundOutboundStock,
    choices: PlacementChoices,
    candidate: PlacementCandidate,
) -> PlacementEvaluation:
    return evaluate_source_candidate(
        bundle, stock, stock.inputs.scenario.baseline, choices, candidate
    )


def evaluate_source_candidate(
    bundle: V3Bundle,
    stock: PlacementInventory,
    source: WorkloadSource,
    choices: PlacementChoices,
    candidate: PlacementCandidate,
) -> PlacementEvaluation:
    """Internal reuse only: the caller authenticates its inventory and source namespace."""
    original = [h for h in stock.original_stock if h.hu_id == candidate.hu_id]
    if len(original) != 1:
        return PlacementEvaluation(
            candidate, None, None, "infeasible", ("SOURCE_HU_NOT_ORIGINAL",), None
        )
    hu = original[0]
    rows = [
        r
        for r in stock.allocations
        if r.status == "original_bound" and r.hu is not None and r.hu.hu_id == hu.hu_id
    ]
    require(len(rows) <= 1, "Original whole HU cannot fund multiple customer cycles")
    offer = rows[0].offer if rows else None
    reasons = physical_reasons(bundle, stock, choices, candidate, hu)
    if reasons:
        return PlacementEvaluation(candidate, hu, offer, "infeasible", reasons, None)
    reasons = reservation_reasons(bundle, stock, choices, candidate, hu)
    if reasons:
        return PlacementEvaluation(candidate, hu, offer, "not_evaluable", reasons, None)
    if offer is None:
        return PlacementEvaluation(
            candidate, hu, None, "not_evaluable", ("NO_AFFECTED_ORIGINAL_OFFER",), None
        )
    try:
        graph, facts = customer_source_facts(bundle, source, choices, candidate, hu, offer)
        cost = price_candidate(graph, facts)
    except ValueError as error:
        return PlacementEvaluation(candidate, hu, offer, "not_evaluable", (str(error),), None)
    reason = "NET_COST_IMPROVEMENT" if cost.net_saving_ticks > 0 else "NET_COST_NOT_BETTER"
    return PlacementEvaluation(candidate, hu, offer, "evaluated", (reason,), cost)
