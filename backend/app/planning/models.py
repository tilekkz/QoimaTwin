"""JSON-ready planning artifacts (ADR 0016). Seconds/metres are exported as floats of exact values;
replay times are also given as exact integer ticks.
"""

from __future__ import annotations

from typing import Literal

from app.contracts.assignment import Assignment
from app.contracts.base import FrozenModel

PLAN_ARTIFACT_VERSION = "qoima-plan-v1"
NoopReason = Literal["budget_zero", "no_positive_net_gain"]


class PlanParameters(FrozenModel):
    objective: Literal["surrogate-j-v1"]
    budget_swaps: int
    shortlist_size: int
    max_pairs_per_iteration: int
    walk_speed_mps: float
    take_or_place_s: float
    handlings_per_swap: int
    relocation_home_node_id: str
    relocation_buffer_node_id: str
    home_node_ids: tuple[str, ...]


class ShortlistEntry(FrozenModel):
    sku_id: str
    expected_visits: float
    baseline_load: float
    abs_load_change: float


class PairEvaluation(FrozenModel):
    sku_a: str
    sku_b: str
    slot_a: str
    slot_b: str
    gross_gain_s: float
    relocation_labor_s: float
    net_gain_s: float


class IterationRecord(FrozenModel):
    iteration: int
    evaluated_pairs: int
    best: PairEvaluation | None
    selected: bool


class SwapSelection(FrozenModel):
    iteration: int
    sku_a: str
    sku_b: str
    slot_a: str
    slot_b: str
    orientation: Literal["a_first", "b_first"]
    stops: tuple[str, ...]
    route_distance_m: float
    alternate_route_distance_m: float
    walk_s: float
    handling_s: float
    relocation_labor_s: float
    gross_gain_s: float
    net_gain_s: float


class PredictedObjective(FrozenModel):
    """J = sum(expected_visits * mean_home_roundtrip_m / walk_speed) + relocation_labor_s."""

    baseline_j_s: float
    candidate_visit_j_s: float
    relocation_labor_s: float
    candidate_j_s: float
    expected_net_gain_s: float


class RelocationAction(FrozenModel):
    action_id: str
    actor_id: str
    swap_index: int
    state: Literal["TRAVEL", "BUSY_SERVICE"]
    operation: Literal["relocation_walk", "relocation_take", "relocation_place"]
    start_tick: int
    end_tick: int
    start_s: float
    end_s: float
    node_ids: tuple[str, ...]
    lot_id: str | None


class TransferRecord(FrozenModel):
    transfer_id: str
    swap_index: int
    step: int
    lot_id: str
    sku_id: str
    quantity: int
    from_location: str
    to_location: str
    take_start_tick: int
    take_end_tick: int
    place_start_tick: int
    place_end_tick: int


class RelocationSchedule(FrozenModel):
    """Before-shift relocation on its own calendar: offsets from the relocation window start.

    The window ends no later than the shift start; the shift calendar (arrivals) is unchanged.
    """

    calendar: Literal["pre_shift"]
    actor_id: str
    ticks_per_second: int
    shift_start_s: float
    window_ticks: int
    window_s: float
    actions: tuple[RelocationAction, ...]
    transfers: tuple[TransferRecord, ...]


class PlanArtifact(FrozenModel):
    artifact_version: Literal["qoima-plan-v1"]
    plan_id: str
    layout_version: str
    forecast_id: str
    baseline_assignment_id: str
    baseline_assignment_hash: str
    training_visits_sha256: str
    expected_visits_sha256: str
    parameters: PlanParameters
    budget_swaps: int
    is_noop: bool
    noop_reason: NoopReason | None
    shortlist: tuple[ShortlistEntry, ...]
    iterations: tuple[IterationRecord, ...]
    selected_pairs: tuple[SwapSelection, ...]
    best_rejected: PairEvaluation | None
    relocation_distance_m: float
    relocation_labor_s: float
    relocation_labor_ticks: int
    predicted: PredictedObjective
    relocation: RelocationSchedule
    final_assignment: Assignment
    final_assignment_hash: str
