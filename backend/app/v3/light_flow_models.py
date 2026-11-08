"""Explicit immutable light-workflow choices and observations; no hidden recipe or clock."""

from dataclasses import dataclass
from fractions import Fraction

from app.v3.belt_models import BeltEvent, BeltSnapshot
from app.v3.runtime_graph import CandidateRoute, DirectedGraph
from app.v3.stock_models import (
    Container,
    Placement,
    StockBalance,
    StockDelta,
    StockOwner,
    StockSeed,
    StockSnapshot,
)

LIGHT_FLOW_ENGINE_VERSION = "qoima-light-flow-v3-proposal-1"


@dataclass(frozen=True, slots=True)
class FlowActor:
    actor_id: str
    home: str
    speed_m_s: Fraction
    max_gross_kg: Fraction
    available_tick: int


@dataclass(frozen=True, slots=True)
class FlowCart:
    cart_id: str
    home: str
    park: str
    owner_id: str
    speed_m_s: Fraction
    max_gross_kg: Fraction
    width_m: Fraction


@dataclass(frozen=True, slots=True)
class FlowStation:
    station_id: str
    node: str
    bench_owner: str
    empty_owner: str


@dataclass(frozen=True, slots=True)
class FlowPort:
    port_id: str
    node: str
    service_tick: int
    windows: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class FlowTimes:
    attach: int
    pick_per_unit: int
    park: int
    detach: int
    deposit: int
    pack: int
    clear: int
    pickup: int


@dataclass(frozen=True, slots=True)
class FlowOrder:
    order_id: str
    arrival_tick: int
    source_hu: str
    source_node: str
    carrier_id: str
    package_id: str
    carrier_placements: tuple[Placement, ...]
    package_placements: tuple[Placement, ...]
    cart_source_node: str | None = None


@dataclass(frozen=True, slots=True)
class FlowProfile:
    profile_id: str
    provenance: str
    graph: DirectedGraph
    stock: StockSeed
    owners: tuple[StockOwner, ...]
    materials: tuple[Container, ...]
    actors: tuple[FlowActor, ...]
    picker_id: str
    packer_id: str
    shipper_id: str
    cart: FlowCart
    station: FlowStation
    port: FlowPort
    intake_node: str
    output_node: str
    carrier_pool_owner: str
    package_pool_owner: str
    shipped_owner: str
    belt_route: tuple[str, ...]
    times: FlowTimes
    orders: tuple[FlowOrder, ...]
    source_revision: str | None = None
    source_hashes: tuple[tuple[str, str], ...] = ()
    path_clearance_m: Fraction | None = None


@dataclass(frozen=True, slots=True)
class FlowOperation:
    kind: str
    order_id: str
    start_tick: int
    planned_end_tick: int
    source_node: str
    target_node: str
    route: CandidateRoute | None
    carrying_id: str | None = None
    cart_id: str | None = None


@dataclass(frozen=True, slots=True)
class FlowWorker:
    actor_id: str
    node: str | None
    order_id: str | None
    operation: FlowOperation | None
    waiting_since: int | None
    queue_ticks: int
    paid_ticks: int


@dataclass(frozen=True, slots=True)
class FlowOrderView:
    order_id: str
    status: str
    admitted_tick: int | None
    shipped_tick: int | None


@dataclass(frozen=True, slots=True)
class FlowCartView:
    cart_id: str
    node: str | None
    operation: FlowOperation | None
    order_id: str | None


@dataclass(frozen=True, slots=True)
class FlowEvent:
    seq: int
    tick: int
    kind: str
    order_id: str
    actor_id: str | None = None
    operation: FlowOperation | None = None
    delta: StockDelta | None = None
    belt_event: BeltEvent | None = None


@dataclass(frozen=True, slots=True)
class FlowSnapshot:
    tick: int
    stock: StockSnapshot
    balance: StockBalance
    workers: tuple[FlowWorker, ...]
    orders: tuple[FlowOrderView, ...]
    leases: tuple[tuple[str, str], ...]
    belt: BeltSnapshot
    last_seq: int
    cart: FlowCartView


@dataclass(frozen=True, slots=True)
class FlowOutcome:
    status: str
    events: tuple[FlowEvent, ...]
    at_horizon: FlowSnapshot
    at_end: FlowSnapshot
    checkpoints: tuple[FlowSnapshot, ...] = ()
