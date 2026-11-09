"""Immutable N1 manual-transfer proposal; no scheduler or stock mutation."""

from dataclasses import dataclass
from fractions import Fraction

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.light_flow_models import FlowActor
from app.v3.light_flow_state import HumanStep
from app.v3.receipt_flow_models import ReceiptPlace
from app.v3.stock_models import ContainerRecipe

RELOCATION_VERSION = "qoima-manual-relocation-proposal-1"


@dataclass(frozen=True, slots=True)
class RelocationJob:
    job_id: str
    arrival_tick: int
    hu_id: str
    from_slot_id: str
    to_slot_id: str
    actor_id: str
    take_ticks: int
    place_ticks: int


@dataclass(frozen=True, slots=True)
class RelocationPlace(ReceiptPlace):
    module_id: str
    module_max_gross_kg: Fraction
    module_max_hus: int


@dataclass(frozen=True, slots=True)
class RelocationChoices:
    profile_id: str
    provenance: str
    jobs: tuple[RelocationJob, ...]
    permitted_actor_ids: tuple[str, ...]
    route_policy: str
    min_width_m: Fraction
    min_height_m: Fraction


@dataclass(frozen=True, slots=True)
class RelocationProfile:
    profile_id: str
    provenance: str
    coordinator: CoordinatorProfile
    jobs: tuple[RelocationJob, ...]
    permitted_actor_ids: tuple[str, ...]
    places: tuple[RelocationPlace, ...]
    route_policy: str
    min_width_m: Fraction
    min_height_m: Fraction


@dataclass(frozen=True, slots=True)
class RelocationPlan:
    job: RelocationJob
    actor: FlowActor
    source: RelocationPlace
    target: RelocationPlace
    cargo: ContainerRecipe
    unit_ids: tuple[str, ...]
    sku_id: str
    lot_id: str
    gross_mass_kg: Fraction
    steps: tuple[HumanStep, ...]


@dataclass(frozen=True, slots=True)
class BoundRelocation:
    profile: RelocationProfile
    plans: tuple[RelocationPlan, ...]
    choices: RelocationChoices
    common_inputs: bytes
    frozen_bytes: bytes
    input_hash: str
