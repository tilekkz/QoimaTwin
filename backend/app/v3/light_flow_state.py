"""Mutable coordinator bookkeeping; observations expose only frozen values."""

from dataclasses import dataclass, field

from app.v3.light_flow_models import FlowActor, FlowCart, FlowOperation, FlowOrder, FlowWorker
from app.v3.runtime_graph import CandidateRoute


@dataclass(frozen=True, slots=True)
class HumanStep:
    kind: str
    target: str
    duration: int
    route: CandidateRoute | None = None
    carrying_id: str | None = None
    cart_id: str | None = None


@dataclass
class HumanState:
    spec: FlowActor
    node: str | None
    order_id: str | None = None
    operation: FlowOperation | None = None
    task: str = "idle"
    steps: list[HumanStep] = field(default_factory=list)
    waiting_since: int | None = None
    closed_queue: int = 0
    closed_paid: int = 0

    def stop_waiting(self, tick: int) -> None:
        if self.waiting_since is not None:
            self.closed_queue += tick - self.waiting_since
            self.waiting_since = None

    def view(self, tick: int) -> FlowWorker:
        queue = self.closed_queue + (
            tick - self.waiting_since if self.waiting_since is not None else 0
        )
        paid = self.closed_paid + (tick - self.operation.start_tick if self.operation else 0)
        return FlowWorker(
            self.spec.actor_id,
            self.node,
            self.order_id,
            self.operation,
            self.waiting_since,
            queue,
            paid,
        )


@dataclass
class OrderState:
    spec: FlowOrder
    status: str = "unreleased"
    admitted_tick: int | None = None
    shipped_tick: int | None = None


@dataclass
class CartState:
    spec: FlowCart
    node: str | None
    operation: FlowOperation | None = None
