"""Plan artifact assembly: greedy selection, relocation schedule, final assignment, stable ID."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from app.contracts.assignment import Assignment
from app.planning.abc import active_lots
from app.planning.apply import assignment_hash, plan_content_hash, replay_transfers
from app.planning.geometry import PlanningGeometry
from app.planning.greedy import (
    DEFAULT_BUDGETS,
    MAX_PAIRS_PER_ITERATION,
    SHORTLIST_SIZE,
    Candidate,
    PlanningInputs,
    PlanningState,
    check_budget,
    greedy_select,
    shortlist,
)
from app.planning.models import (
    PLAN_ARTIFACT_VERSION,
    IterationRecord,
    PlanArtifact,
    PlanParameters,
    PredictedObjective,
    RelocationSchedule,
    SwapSelection,
)
from app.planning.routes import HANDLINGS_PER_SWAP, WorkerRates
from app.planning.schedule import build_schedule
from app.planning.visits import visits_hash
from app.simulation.clock import TimeGrid
from app.storage.canonical_json import sha256_hex


def plan_swaps(
    inputs: PlanningInputs, budget: int, *, geometry: PlanningGeometry | None = None
) -> PlanArtifact:
    """One plan with at most `budget` disjoint swaps; no-op when nothing pays for itself."""
    check_budget(budget)
    state = PlanningState.prepare(inputs, geometry)
    entries = shortlist(state)
    chosen: list[tuple[int, Candidate]] = []
    records: list[IterationRecord] = []
    rejected: Candidate | None = None
    if budget:
        chosen, records, rejected = greedy_select(state, [e.sku_id for e in entries], budget)
    schedule = _schedule(state, [c for _, c in chosen])
    final = _final_assignment(state, chosen, schedule)
    relocation_s = sum((c.swap.labor_s for _, c in chosen), Fraction(0))
    plan = PlanArtifact.model_validate(
        {
            "artifact_version": PLAN_ARTIFACT_VERSION,
            "plan_id": "",
            "layout_version": inputs.layout.layout_version,
            "forecast_id": inputs.forecast_id,
            "baseline_assignment_id": inputs.baseline_assignment.assignment_id,
            "baseline_assignment_hash": assignment_hash(inputs.baseline_assignment),
            "training_visits_sha256": visits_hash(inputs.training_visits),
            "expected_visits_sha256": visits_hash(inputs.expected_visits),
            "parameters": _parameters(state, budget),
            "budget_swaps": budget,
            "is_noop": not chosen,
            "noop_reason": None
            if chosen
            else ("no_positive_net_gain" if budget else "budget_zero"),
            "shortlist": entries,
            "iterations": tuple(records),
            "selected_pairs": tuple(selection(i, c) for i, c in chosen),
            "best_rejected": rejected.evaluation() if rejected and not chosen else None,
            "relocation_distance_m": float(sum((c.swap.chosen.distance_m for _, c in chosen), 0)),
            "relocation_labor_s": float(relocation_s),
            "relocation_labor_ticks": schedule.window_ticks,
            "predicted": _predicted(state, final, relocation_s),
            "relocation": schedule,
            "final_assignment": final,
            "final_assignment_hash": assignment_hash(final),
        }
    )
    return plan.model_copy(update={"plan_id": plan_content_hash(plan)})


def plan_budgets(
    inputs: PlanningInputs,
    budgets: Sequence[int] = DEFAULT_BUDGETS,
    *,
    geometry: PlanningGeometry | None = None,
) -> tuple[PlanArtifact, ...]:
    """The 0/2/8 plan family from one forecast, sharing the graph geometry."""
    geo = geometry or PlanningGeometry.from_layout(inputs.layout)
    return tuple(plan_swaps(inputs, budget, geometry=geo) for budget in budgets)


def _parameters(state: PlanningState, budget: int) -> PlanParameters:
    config = state.inputs.config
    return PlanParameters(
        objective="surrogate-j-v1",
        budget_swaps=budget,
        shortlist_size=SHORTLIST_SIZE,
        max_pairs_per_iteration=MAX_PAIRS_PER_ITERATION,
        walk_speed_mps=config.walk_speed_mps,
        take_or_place_s=config.relocation_take_or_place_s,
        handlings_per_swap=HANDLINGS_PER_SWAP,
        relocation_home_node_id=state.geo.home_node,
        relocation_buffer_node_id=state.geo.buffer_node,
        home_node_ids=state.geo.homes,
    )


def selection(iteration: int, candidate: Candidate) -> SwapSelection:
    swap = candidate.swap
    return SwapSelection(
        iteration=iteration,
        sku_a=candidate.sku_a,
        sku_b=candidate.sku_b,
        slot_a=swap.slot_a,
        slot_b=swap.slot_b,
        orientation=swap.chosen.orientation,
        stops=swap.chosen.stops,
        route_distance_m=float(swap.chosen.distance_m),
        alternate_route_distance_m=float(swap.alternate.distance_m),
        walk_s=float(swap.walk_s),
        handling_s=float(swap.handling_s),
        relocation_labor_s=float(swap.labor_s),
        gross_gain_s=float(candidate.gross_s),
        net_gain_s=float(candidate.net_s),
    )


def _schedule(state: PlanningState, chosen: Sequence[Candidate]) -> RelocationSchedule:
    layout, config = state.inputs.layout, state.inputs.config
    tps = TimeGrid.for_inputs(layout, config).ticks_per_second
    lots = active_lots(state.inputs.baseline_assignment)
    routes = [c.swap.chosen for c in chosen]
    return build_schedule(state.geo, WorkerRates.of(config), tps, routes, lots)


def _final_assignment(
    state: PlanningState, chosen: Sequence[tuple[int, Candidate]], schedule: RelocationSchedule
) -> Assignment:
    baseline = state.inputs.baseline_assignment
    swaps = [(c.sku_a, c.sku_b, c.swap.slot_a, c.swap.slot_b) for _, c in chosen]
    new_id = f"{baseline.assignment_id}~swaps-{sha256_hex(swaps)[:16]}"
    return replay_transfers(baseline, schedule.transfers, state.geo.buffer_node, new_id)


def _predicted(
    state: PlanningState, final: Assignment, relocation_s: Fraction
) -> PredictedObjective:
    baseline_j = state.visit_j(state.slot_of)
    candidate_visit_j = state.visit_j(final.slot_of())
    candidate_j = candidate_visit_j + relocation_s
    return PredictedObjective(
        baseline_j_s=float(baseline_j),
        candidate_visit_j_s=float(candidate_visit_j),
        relocation_labor_s=float(relocation_s),
        candidate_j_s=float(candidate_j),
        expected_net_gain_s=float(baseline_j - candidate_j),
    )
