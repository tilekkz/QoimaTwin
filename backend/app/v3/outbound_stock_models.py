"""Compilation allocations are declarations, never stock credit or runtime claims."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.outbound_shift_models import OutboundShiftInputs
from app.v3.workload_models import WorkloadJob

STOCK_VERSION = "qoima-n1-outbound-stock-0.1.0"
ALLOCATION_POLICY = "original_first_declared_receipt_dependency_visible_shortage"
AllocationStatus = Literal["original_bound", "receipt_dependency", "unallocated"]
ShortageReason = Literal["DECLARED_STOCK_EXHAUSTED"]


@dataclass(frozen=True, slots=True)
class StockHU:
    hu_id: str
    sku_id: str
    archetype_id: str
    lot_id: str
    unit_ids: tuple[str, ...]
    quantity_units: int
    gross_mass_kg: Fraction
    initial_owner_id: str | None
    receipt_job_id: str | None
    receipt_arrival_tick: int | None


@dataclass(frozen=True, slots=True)
class StockAllocation:
    offer: WorkloadJob
    status: AllocationStatus
    hu: StockHU | None
    reason: ShortageReason | None
    receipt_arrives_after_offer: bool | None

    @property
    def operational_admission(self) -> Literal[False]:
        return False


@dataclass(frozen=True, slots=True)
class BoundOutboundStock:
    inputs: OutboundShiftInputs
    original_stock: tuple[StockHU, ...]
    declared_receipts: tuple[StockHU, ...]
    allocations: tuple[StockAllocation, ...]
    source_stock_hash: str
    frozen_bytes: bytes
    input_hash: str

    @property
    def operational_admission(self) -> Literal[False]:
        return False

    @property
    def full_n1_acceptance(self) -> Literal[False]:
        return False
