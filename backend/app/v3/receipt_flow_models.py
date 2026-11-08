"""Native receipt-flow proposal values; future definitions are outside baseline stock."""

from dataclasses import dataclass
from fractions import Fraction

from app.v3.light_flow_models import FlowEvent, FlowOutcome, FlowProfile, FlowSnapshot
from app.v3.stock_claims import StockClaim
from app.v3.stock_models import Vec3
from app.v3.stock_receipts import InventorySnapshot, ReceiptDefinition

RECEIPT_FLOW_ENGINE_VERSION = "qoima-receipt-flow-v3-proposal-1"


@dataclass(frozen=True, slots=True)
class ReceiptPlace:
    owner_id: str
    node_id: str
    dimensions: Vec3
    max_gross_kg: Fraction
    clearance_m: Fraction


@dataclass(frozen=True, slots=True)
class ReceiptPort:
    port_id: str
    node_id: str
    service_tick: int
    windows: tuple[tuple[int, int], ...]
    buffer_ids: tuple[str, ...]
    receiver_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReceiptOffer:
    definition: ReceiptDefinition
    arrival_tick: int
    port_id: str
    slot_owner_id: str


@dataclass(frozen=True, slots=True)
class ReceiptFlowProfile:
    flow: FlowProfile
    ports: tuple[ReceiptPort, ...]
    places: tuple[ReceiptPlace, ...]
    receipts: tuple[ReceiptOffer, ...]
    pickup_tick: int
    place_tick: int


@dataclass(frozen=True, slots=True)
class ReceiptView:
    receipt_id: str
    status: str
    actor_id: str | None
    buffer_owner_id: str | None
    admitted_tick: int | None
    credited_tick: int | None
    placed_tick: int | None
    returned_tick: int | None
    wait_reason: str | None
    paid_exposure_ticks: int


@dataclass(frozen=True, slots=True)
class ReceiptFlowEvent(FlowEvent):
    receipt: ReceiptView | None = None
    inventory_claim: StockClaim | None = None
    released_claim_id: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReceiptFlowSnapshot(FlowSnapshot):
    inventory: InventorySnapshot
    receipts: tuple[ReceiptView, ...]


@dataclass(frozen=True, slots=True)
class ReceiptFlowOutcome(FlowOutcome):
    at_horizon: ReceiptFlowSnapshot
    at_end: ReceiptFlowSnapshot
    checkpoints: tuple[ReceiptFlowSnapshot, ...] = ()
