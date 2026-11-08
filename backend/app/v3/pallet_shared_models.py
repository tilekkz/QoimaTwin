"""Native shared-ledger local fixture; this is not a source PALLET receipt contract."""

from dataclasses import dataclass, field
from typing import Literal

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_types import ActiveOperation, CycleBridge, CycleTimingProfile, ExactPose
from app.v3.whole_flow_models import (
    WholeFlowEvent,
    WholeFlowOutcome,
    WholeFlowProfile,
    WholeFlowSnapshot,
)

PALLET_SHARED_VERSION = "qoima-shared-local-pallet-v3-proposal-1"


class PalletSharedError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True, slots=True)
class PalletSharedJob:
    job_id: str
    ready_tick: int
    hu_id: str
    operation: str


@dataclass(frozen=True, slots=True)
class PalletSharedProfile:
    world: WholeFlowProfile
    timing: CycleTimingProfile
    jobs: tuple[PalletSharedJob, ...]
    hu_id: str
    platform_id: str
    vehicle_owner_id: str
    driver_anchor: str
    model_sha256: str
    inventory_scope: str
    initial_driver_state: str
    source_approach: bool


@dataclass(frozen=True, slots=True)
class PalletSharedJobView:
    job_id: str
    status: str
    admitted_tick: int | None
    attached_tick: int | None
    released_tick: int | None
    completed_tick: int | None
    completed_steps: int
    wait_reason: str | None


@dataclass(frozen=True, slots=True)
class PalletVehicleView:
    vehicle_id: str
    driver_id: str
    driver_anchor: str
    frame_id: str
    pose: ExactPose
    active_operation: ActiveOperation | None
    job_id: str | None
    hu_id: str | None


@dataclass(frozen=True, slots=True)
class PalletSharedEvent(WholeFlowEvent):
    pallet_job: PalletSharedJobView | None = None
    vehicle: PalletVehicleView | None = None


@dataclass(frozen=True, slots=True)
class PalletSharedSnapshot(WholeFlowSnapshot):
    pallet_jobs: tuple[PalletSharedJobView, ...]
    vehicle: PalletVehicleView


@dataclass(frozen=True, slots=True)
class PalletSharedOutcome(WholeFlowOutcome):
    at_horizon: PalletSharedSnapshot
    at_end: PalletSharedSnapshot
    checkpoints: tuple[PalletSharedSnapshot, ...] = ()
    bridge: CycleBridge | None = None
    geometry_proof: LocalGeometryProof = field(kw_only=True)
    profile_sha256: str = field(kw_only=True)
    requested_end_tick_limit: int = field(kw_only=True)
    engine_version: str = PALLET_SHARED_VERSION
    shared_inventory: Literal[True] = True
    local_geometry_proof: Literal[True] = True
    pallet_receiving: Literal[False] = False
    source_inventory_binding: Literal[False] = False
    full_warehouse: Literal[False] = False
    operational_admission: Literal[False] = False
