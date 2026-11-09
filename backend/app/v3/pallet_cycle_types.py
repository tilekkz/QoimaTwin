"""Explicit synthetic timing and observations for one bounded PALLET component."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.execution_types import ACTOR_IDS
from app.v3.mesh_proof_fixture import LocalGeometryProof

PALLET_CYCLE_VERSION = "qoima-local-pallet-cycle-1"
DRIVER_ID = "F01"
VEHICLE_ID = "FL01"
PLATFORM_ID = "v3:slot:HEAVY_E:001:L1:B1"
FIXED_ACTORS = ACTOR_IDS


@dataclass(frozen=True, slots=True)
class CycleTimingProfile:
    profile_id: str
    root_speed_m_s: Fraction
    lift_speed_m_s: Fraction
    reach_speed_m_s: Fraction
    attach_s: Fraction
    release_s: Fraction
    hold_s: Fraction
    provenance_note: str
    source_kind: Literal["synthetic"] = "synthetic"
    driver_initial_state: Literal["seated_in_FL01"] = "seated_in_FL01"


@dataclass(frozen=True, slots=True)
class ExactPose:
    root_z: Fraction
    fork_top: Fraction
    reach: Fraction


@dataclass(frozen=True, slots=True)
class CycleOperation:
    ordinal: int
    kind: Literal["motion", "hold", "attach", "release", "bridge"]
    phase: str
    duration_ticks: int
    start_pose: ExactPose
    end_pose: ExactPose
    attached: bool
    source_arc_id: str | None = None


@dataclass(frozen=True, slots=True)
class CycleJob:
    job_id: str
    ready_tick: int
    hu_id: str


@dataclass(frozen=True, slots=True)
class PhysicalPallet:
    hu_id: str
    cargo_class: str
    units: int
    gross_mass_kg: Fraction
    model_sha256: str


@dataclass(frozen=True, slots=True)
class PalletOwner:
    hu_id: str
    kind: Literal["platform", "vehicle"]
    resource_id: str


@dataclass(frozen=True, slots=True)
class CycleLease:
    resource_id: str
    job_id: str
    acquired_tick: int


@dataclass(frozen=True, slots=True)
class CycleJobView:
    job_id: str
    state: Literal["not_arrived", "waiting", "active", "complete"]
    wait_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ActiveOperation:
    job_id: str
    operation: CycleOperation
    started_tick: int
    planned_end_tick: int


@dataclass(frozen=True, slots=True)
class CycleEvent:
    seq: int
    tick: int
    kind: str
    job_id: str
    operation: ActiveOperation | None = None
    owner: PalletOwner | None = None
    lease: CycleLease | None = None
    job: CycleJobView | None = None


@dataclass(frozen=True, slots=True)
class CycleSnapshot:
    tick: int
    status: Literal["complete", "partial"]
    jobs: tuple[CycleJobView, ...]
    owner: PalletOwner
    leases: tuple[CycleLease, ...]
    active_operation: ActiveOperation | None
    observed_pose: ExactPose
    actor_busy_ticks: tuple[tuple[str, int], ...]
    queue_exposure_tick_jobs: int
    completed_count: int


@dataclass(frozen=True, slots=True)
class CycleBridge:
    source_revision: str
    source_hashes: tuple[tuple[str, str], ...]
    entry_arc_id: str
    exit_arc_id: str
    prehandle_xyz: tuple[Fraction, Fraction, Fraction]
    action_start_xyz: tuple[Fraction, Fraction, Fraction]
    distance_m: Fraction
    entry_fraction: tuple[Fraction, Fraction]
    exit_fraction: tuple[Fraction, Fraction]
    resource_ids: tuple[str, ...]
    entry_cover_checks: int = 0
    exit_cover_checks: int = 0


@dataclass(frozen=True, slots=True)
class CycleOutcome:
    profile_id: str
    events: tuple[CycleEvent, ...]
    at_horizon: CycleSnapshot
    at_end: CycleSnapshot
    proof_bindings: tuple[tuple[str, str], ...]
    source_approach: bool
    geometry_proof: LocalGeometryProof
    physical_registry: tuple[PhysicalPallet, ...]
    requested_end_tick_limit: int
    bridge: CycleBridge | None = None
    frame_id: str = "pallet_fixture_local"
    inventory_integration: Literal[False] = False
    operational_admission: Literal[False] = False
