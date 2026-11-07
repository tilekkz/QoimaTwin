"""Full verification of a plan artifact against the layout graph (05 §9 P2, P5; ADR 0016).

Every travel hop must be a picker-graph edge on a shortest path. Every selected pair, the whole
relocation schedule, the paid labor totals and the final assignment are regenerated from the
graph, the plan parameters and the shortlisted expected visits, and must match exactly.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise

from app.contracts.assignment import InitialLot
from app.contracts.base import exact
from app.contracts.layout import Layout
from app.planning.apply import assignment_hash, plan_content_hash
from app.planning.errors import PlanningInputError
from app.planning.geometry import PlanningGeometry
from app.planning.greedy import Candidate
from app.planning.models import PlanArtifact, RelocationAction, SwapSelection
from app.planning.plan import selection
from app.planning.routes import WorkerRates, evaluate_swap_at
from app.planning.schedule import build_schedule


def verify_plan(
    plan: PlanArtifact, layout: Layout, *, geometry: PlanningGeometry | None = None
) -> None:
    """Reject plans that leave the graph, misstate distances, labor or lots, or were edited."""
    geo = geometry or PlanningGeometry.from_layout(layout)
    if plan.layout_version != layout.layout_version:
        raise PlanningInputError(f"plan layout {plan.layout_version} != {layout.layout_version}")
    rates = WorkerRates(
        exact(plan.parameters.walk_speed_mps), exact(plan.parameters.take_or_place_s)
    )
    tps = plan.relocation.ticks_per_second
    for action in plan.relocation.actions:
        _verify_travel(geo, action, rates.walk_speed_mps, tps)
    _verify_header(plan)
    candidates = [_verify_pair(geo, rates, plan, pair) for pair in plan.selected_pairs]
    _verify_schedule(geo, rates, plan, candidates)
    if plan_content_hash(plan) != plan.plan_id:
        raise PlanningInputError("plan_id does not match the plan content")


def _verify_header(plan: PlanArtifact) -> None:
    pairs = len(plan.selected_pairs)
    if plan.is_noop != (pairs == 0) or pairs > plan.budget_swaps:
        raise PlanningInputError("no-op flag or budget disagrees with the selected pairs")
    if plan.parameters.budget_swaps != plan.budget_swaps:
        raise PlanningInputError("parameters.budget_swaps disagrees with budget_swaps")
    if assignment_hash(plan.final_assignment) != plan.final_assignment_hash:
        raise PlanningInputError("final_assignment_hash does not match the final assignment")
    skus = [s for pair in plan.selected_pairs for s in (pair.sku_a, pair.sku_b)]
    if len(skus) != len(set(skus)):
        raise PlanningInputError("selected pairs must touch disjoint SKUs")


def _verify_travel(
    geo: PlanningGeometry, action: RelocationAction, speed: Fraction, tps: int
) -> None:
    if action.state != "TRAVEL":
        return
    total = Fraction(0)
    for a, b in pairwise(action.node_ids):
        length = geo.edge_lengths.get((a, b))
        if length is None:
            raise PlanningInputError(f"{action.action_id}: {a}->{b} is not a picker_graph edge")
        total += length
    if total != geo.distance(action.node_ids[0], action.node_ids[-1]):
        raise PlanningInputError(f"{action.action_id}: path is not a shortest graph path")
    if Fraction(action.end_tick - action.start_tick, tps) != total / speed:
        raise PlanningInputError(f"{action.action_id}: duration disagrees with the distance")


def _verify_pair(
    geo: PlanningGeometry, rates: WorkerRates, plan: PlanArtifact, pair: SwapSelection
) -> Candidate:
    """Both orientations are recomputed on the graph; gains come from shortlisted visits."""
    swap = evaluate_swap_at(geo, rates, pair.slot_a, pair.slot_b)
    if float(swap.chosen.distance_m) != pair.route_distance_m:
        raise PlanningInputError(
            f"swap {pair.slot_a}<->{pair.slot_b}: stated distance {pair.route_distance_m} m "
            f"!= graph {swap.chosen.distance_m}"
        )
    expected = {e.sku_id: Fraction(e.expected_visits) for e in plan.shortlist}
    if pair.sku_a not in expected or pair.sku_b not in expected:
        raise PlanningInputError(f"pair {pair.sku_a}/{pair.sku_b} is not on the shortlist")
    cost_gap = geo.slot_cost(pair.slot_a) - geo.slot_cost(pair.slot_b)
    gross = (expected[pair.sku_a] - expected[pair.sku_b]) * cost_gap / rates.walk_speed_mps
    candidate = Candidate(pair.sku_a, pair.sku_b, swap, gross)
    if selection(pair.iteration, candidate) != pair or candidate.net_s <= 0:
        raise PlanningInputError(f"pair {pair.sku_a}/{pair.sku_b} disagrees with graph and visits")
    final = plan.final_assignment.slot_of()
    if (final.get(pair.sku_a), final.get(pair.sku_b)) != (pair.slot_b, pair.slot_a):
        raise PlanningInputError(f"final assignment does not swap {pair.sku_a}/{pair.sku_b}")
    return candidate


def _verify_schedule(
    geo: PlanningGeometry, rates: WorkerRates, plan: PlanArtifact, candidates: list[Candidate]
) -> None:
    final_lots = {lot.slot_id: lot for lot in plan.final_assignment.initial_lots}
    lots: dict[str, InitialLot] = {}
    for candidate in candidates:
        slot_a, slot_b = candidate.swap.slot_a, candidate.swap.slot_b
        lots[slot_a], lots[slot_b] = final_lots[slot_b], final_lots[slot_a]
    routes = [c.swap.chosen for c in candidates]
    expected = build_schedule(geo, rates, plan.relocation.ticks_per_second, routes, lots)
    if expected != plan.relocation:
        raise PlanningInputError("relocation schedule disagrees with the selected routes")
    labor = sum((c.swap.labor_s for c in candidates), Fraction(0))
    metres = sum((c.swap.chosen.distance_m for c in candidates), Fraction(0))
    totals = (plan.relocation_labor_ticks, plan.relocation_labor_s, plan.relocation_distance_m)
    if totals != (expected.window_ticks, float(labor), float(metres)):
        raise PlanningInputError("relocation labor or distance totals disagree with the routes")
