"""Prospective source receipt and explicit unresolved physical obligations, not a credit grant."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.pallet_cycle_types import CycleBridge, CycleOperation
from app.v3.stock_receipts import ReceiptDefinition
from app.v3.vehicle_types import VehicleArc

REQUIREMENTS_VERSION = "qoima-pallet-receipt-requirements-0.1.0"
ProofCode = Literal[
    "STAGING_PICKUP_GEOMETRY_MISSING",
    "STAGING_VEHICLE_CONNECTOR_MISSING",
    "LOADED_ROUTE_ACTUAL_MODEL_PROOF_REQUIRED",
    "TARGET_PUTAWAY_PROOF_REQUIRED",
    "SHARED_RECEIPT_PROCESS_POLICY_REQUIRED",
]


class PalletReceiptError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True, slots=True)
class PalletReceiptRequest:
    receipt_id: str
    hu_id: str
    lot_id: str
    template_hu_id: str
    port_id: str
    slot_id: str
    receiver_id: str
    arrival_tick: int
    horizon_tick: int
    end_tick: int


@dataclass(frozen=True, slots=True)
class ProofObligation:
    code: ProofCode
    stage: str
    missing_fields: tuple[str, ...]
    source_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReceiptPortRequirement:
    port_id: str
    service_node_id: str
    service_tick: int
    bay_capacity: int
    buffer_capacity: int
    staging_zones: tuple[tuple[str, int], ...]
    windows: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class RouteStop:
    node_id: str
    before_arc: str
    after_arc: str
    reasons: tuple[str, ...]
    source_stop_allowed: bool | None


@dataclass(frozen=True, slots=True)
class PalletRouteCandidate:
    node_ids: tuple[str, ...]
    arcs: tuple[VehicleArc, ...]
    root_length_m: Fraction
    stops: tuple[RouteStop, ...]
    resource_capacities: tuple[tuple[str, int], ...]
    meaning: str = "conditional_service_pose_to_prehandle_not_staging_pickup"
    operational_admission: Literal[False] = False


@dataclass(frozen=True, slots=True)
class PalletReceiptRequirements:
    request: PalletReceiptRequest
    receipt: ReceiptDefinition
    port: ReceiptPortRequirement
    route: PalletRouteCandidate
    source_revision: str
    source_hashes: tuple[tuple[str, str], ...]
    baseline_hus: int
    baseline_units: int
    gross_mass_kg: Fraction
    actor_ids: tuple[str, ...]
    receiver_ids: tuple[str, ...]
    driver_id: str
    vehicle_id: str
    blockers: tuple[ProofObligation, ...]
    requirements_hash: str
    version: str = REQUIREMENTS_VERSION
    receipt_credit_allowed: Literal[False] = False
    operational_admission: Literal[False] = False


@dataclass(frozen=True, slots=True)
class PutawayPrimitive:
    steps: tuple[CycleOperation, ...]
    release_offset_tick: int
    duration_tick: int
    proof_hashes: tuple[tuple[str, str], ...]
    loaded_bridge_checks: int
    bridge: CycleBridge | None
    proof_method_version: str
    source_binding: Literal["local_fixture_only", "source_prehandle_bound"]
    version: str = "qoima-pallet-putaway-primitive-0.1.0"
    initial_custody: str = "vehicle:FL01"
    final_custody: str = "v3:slot:HEAVY_E:001:L1:B1"
    receipt_credit_allowed: Literal[False] = False
    operational_admission: Literal[False] = False
