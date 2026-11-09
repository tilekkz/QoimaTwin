"""Frozen inputs and public observations for the manual execution proposal (ADR 0031)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.v3.runtime_graph import CandidateRoute, DirectedGraph

ACTOR_IDS = tuple(
    [f"P{i:02}" for i in range(1, 13)]
    + [f"K{i:02}" for i in range(1, 7)]
    + ["R01", "R02", "S01", "S02", "F01", "F02"]
)
MANUAL_ARCHETYPES = frozenset({"SMALL_CARTON", "STANDARD_CARTON"})
MANUAL_ENGINE_VERSION = "qoima-manual-engine-v3-proposal-2"


@dataclass(frozen=True, slots=True)
class SourceBinding:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class BoundGraph:
    graph: DirectedGraph
    layout_version: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ActorSpec:
    actor_id: str
    home_node_id: str
    skills: frozenset[str]
    speed_m_s: Fraction
    max_gross_mass_kg: Fraction


@dataclass(frozen=True, slots=True)
class HandlingUnit:
    hu_id: str
    sku_id: str
    quantity: int
    archetype: str
    gross_mass_kg: Fraction
    dimensions_xyz_m: tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class PlaceSpec:
    place_id: str
    node_id: str
    usable_dimensions_xyz_m: tuple[Fraction, Fraction, Fraction]
    max_payload_kg: Fraction
    allowed_archetypes: frozenset[str]


@dataclass(frozen=True, slots=True)
class PortSpec:
    port_id: str
    direction: str
    service_node_id: str
    buffer_places: tuple[PlaceSpec, ...]
    service_ticks: tuple[tuple[str, int], ...]
    windows: tuple[tuple[int, int], ...]
    eligible_actor_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class InitialPlacement:
    hu_id: str
    slot_id: str


@dataclass(frozen=True, slots=True)
class TimedJob:
    job_id: str
    arrival_tick: int
    direction: str
    hu_id: str
    port_id: str
    slot_id: str


@dataclass(frozen=True, slots=True)
class HandlingTimes:
    pickup_ticks: int
    place_ticks: int


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    profile_id: str
    layout_version: str
    graph_sha256: str
    source_bindings: tuple[SourceBinding, ...]
    actors: tuple[ActorSpec, ...]
    ports: tuple[PortSpec, ...]
    slots: tuple[PlaceSpec, ...]
    handling_units: tuple[HandlingUnit, ...]
    initial_placements: tuple[InitialPlacement, ...]
    jobs: tuple[TimedJob, ...]
    handling: HandlingTimes
    provenance_note: str


@dataclass(frozen=True, slots=True)
class Motion:
    route: CandidateRoute
    start_tick: int
    end_tick: int


@dataclass(frozen=True, slots=True)
class WorkerView:
    actor_id: str
    node_id: str | None
    motion: Motion | None
    job_id: str | None


@dataclass(frozen=True, slots=True)
class JobView:
    job_id: str
    state: str
    wait_reason: str | None
    actor_id: str | None


@dataclass(frozen=True, slots=True)
class HUOwner:
    hu_id: str
    kind: str
    location_id: str


@dataclass(frozen=True, slots=True)
class Lease:
    resource_id: str
    job_id: str
    acquired_tick: int


@dataclass(frozen=True, slots=True)
class ManualEvent:
    seq: int
    tick: int
    kind: str
    job_id: str
    hu_id: str
    actor_id: str | None = None
    stage: str | None = None
    location_id: str | None = None
    resource_ids: tuple[str, ...] = ()
    motion: Motion | None = None
    owner: HUOwner | None = None
    job: JobView | None = None
    worker: WorkerView | None = None


@dataclass(frozen=True, slots=True)
class ManualSnapshot:
    tick: int
    status: str
    jobs: tuple[JobView, ...]
    workers: tuple[WorkerView, ...]
    owners: tuple[HUOwner, ...]
    leases: tuple[Lease, ...]
    stock_units: tuple[tuple[str, int], ...]
    wip_units: tuple[tuple[str, int], ...]
    outside_units: tuple[tuple[str, int], ...]
    shipped_units: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class ManualOutcome:
    profile_id: str
    events: tuple[ManualEvent, ...]
    at_horizon: ManualSnapshot
    at_end: ManualSnapshot
