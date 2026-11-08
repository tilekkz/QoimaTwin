"""Native shared whole-HU proposal, separate from the frozen unit-only publications."""

from dataclasses import dataclass

from app.v3.receipt_flow_models import (
    ReceiptFlowEvent,
    ReceiptFlowOutcome,
    ReceiptFlowProfile,
    ReceiptFlowSnapshot,
    ReceiptPlace,
)

WHOLE_FLOW_ENGINE_VERSION = "qoima-whole-flow-v3-proposal-1"
MANUAL_WHOLE_CLASSES = frozenset({"SMALL_CARTON", "STANDARD_CARTON"})


@dataclass(frozen=True, slots=True)
class WholeHUOrder:
    job_id: str
    arrival_tick: int
    hu_id: str
    port_id: str


@dataclass(frozen=True, slots=True)
class WholeHUPort:
    port_id: str
    node_id: str
    service_ticks: tuple[tuple[str, int], ...]
    windows: tuple[tuple[int, int], ...]
    buffer_ids: tuple[str, ...]
    shipper_ids: tuple[str, ...]
    shipped_owner: str


@dataclass(frozen=True, slots=True)
class WholeFlowProfile:
    receipts: ReceiptFlowProfile
    orders: tuple[WholeHUOrder, ...]
    ports: tuple[WholeHUPort, ...]
    places: tuple[ReceiptPlace, ...]
    pickup_tick: int
    place_tick: int


@dataclass(frozen=True, slots=True)
class WholeHUView:
    job_id: str
    status: str
    actor_id: str | None
    buffer_owner_id: str | None
    admitted_tick: int | None
    picked_tick: int | None
    buffered_tick: int | None
    buffer_picked_tick: int | None
    port_reserved_tick: int | None
    service_started_tick: int | None
    shipped_tick: int | None
    returned_tick: int | None
    wait_reason: str | None
    paid_exposure_ticks: int
    port_reservation_ticks: int
    port_service_ticks: int


@dataclass(frozen=True, slots=True)
class WholeFlowEvent(ReceiptFlowEvent):
    whole_order: WholeHUView | None = None


@dataclass(frozen=True, slots=True)
class WholeFlowSnapshot(ReceiptFlowSnapshot):
    whole_orders: tuple[WholeHUView, ...]


@dataclass(frozen=True, slots=True)
class WholeFlowOutcome(ReceiptFlowOutcome):
    at_horizon: WholeFlowSnapshot
    at_end: WholeFlowSnapshot
    checkpoints: tuple[WholeFlowSnapshot, ...] = ()
