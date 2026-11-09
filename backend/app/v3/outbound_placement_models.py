"""One explicit original-HU candidate; no optimizer, operational claim or new stock."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.outbound_shift_models import BaselinePlacement
from app.v3.outbound_stock_models import BoundOutboundStock, StockHU
from app.v3.runtime_graph import CandidateRoute
from app.v3.workload_models import WorkloadJob

VERSION = "qoima-n1-placement-decision-0.1.0"
SELECTION_POLICY = "one_candidate_full_uncontended_paid_cost_noop_on_tie_v1"


@dataclass(frozen=True, slots=True)
class PlacementActor:
    actor_id: str
    home_node_id: str
    speed_m_s: Fraction
    max_gross_kg: Fraction


@dataclass(frozen=True, slots=True)
class PlacementCustomer:
    offer_id: str
    port_id: str
    buffer_choice: bytes
    pickup_ticks: int
    place_ticks: int
    service_ticks: int


@dataclass(frozen=True, slots=True)
class PlacementCandidate:
    hu_id: str
    from_slot_id: str
    to_slot_id: str
    actor: PlacementActor
    take_ticks: int
    place_ticks: int
    customer: PlacementCustomer | None


@dataclass(frozen=True, slots=True)
class PlacementReceiptTarget:
    receipt_job_id: str
    hu_id: str
    slot_id: str


@dataclass(frozen=True, slots=True)
class PlacementChoices:
    policy_id: str
    candidates: tuple[PlacementCandidate, ...]
    permitted_actor_ids: tuple[str, ...]
    route_policy: str
    min_width_m: Fraction
    min_height_m: Fraction
    path_clearance_m: Fraction
    receipt_targets: tuple[PlacementReceiptTarget, ...]


@dataclass(frozen=True, slots=True)
class PlacementCostFacts:
    actor: PlacementActor
    source_node: str
    target_node: str
    buffer_node: str
    port_node: str
    archetype: str
    dimensions: tuple[Fraction, Fraction, Fraction]
    take_ticks: int
    place_ticks: int
    pickup_ticks: int
    customer_place_ticks: int
    service_ticks: int
    min_width_m: Fraction
    min_height_m: Fraction
    path_clearance_m: Fraction


@dataclass(frozen=True, slots=True)
class PlacementOperation:
    kind: str
    seconds: Fraction
    ticks: int
    route: CandidateRoute | None


@dataclass(frozen=True, slots=True)
class PlacementCost:
    relocation: tuple[PlacementOperation, ...]
    baseline: tuple[PlacementOperation, ...]
    adapted: tuple[PlacementOperation, ...]
    relocation_ticks: int
    baseline_ticks: int
    adapted_ticks: int
    gross_saving_ticks: int
    net_saving_ticks: int


@dataclass(frozen=True, slots=True)
class PlacementEvaluation:
    candidate: PlacementCandidate
    hu: StockHU | None
    affected_offer: WorkloadJob | None
    status: Literal["infeasible", "not_evaluable", "evaluated"]
    reasons: tuple[str, ...]
    cost: PlacementCost | None


@dataclass(frozen=True, slots=True)
class N1PlacementDecision:
    stock: BoundOutboundStock
    choices: PlacementChoices
    evaluations: tuple[PlacementEvaluation, ...]
    selected: PlacementCandidate | None
    no_op: bool
    selection_reason: str
    placements: tuple[BaselinePlacement, ...]
    choices_bytes: bytes
    frozen_bytes: bytes
    input_hash: str
    operational_admission: Literal[False] = False
    full_n1_acceptance: Literal[False] = False
