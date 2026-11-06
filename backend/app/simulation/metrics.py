"""Order milestones and basic counters. Full KPI set (queues, utilization) follows in B7."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(slots=True)
class OrderRecord:
    arrival: int
    packed: int | None = None
    dispatched: int | None = None
    rejected: int | None = None


@dataclass(slots=True)
class Metrics:
    orders: dict[str, OrderRecord] = field(default_factory=dict)
    distance_m: dict[str, Fraction] = field(default_factory=lambda: defaultdict(Fraction))

    def order_arrived(self, order_id: str, tick: int) -> None:
        self.orders[order_id] = OrderRecord(arrival=tick)

    def order_rejected(self, order_id: str, tick: int) -> None:
        self.orders[order_id].rejected = tick

    def order_packed(self, order_id: str, tick: int) -> None:
        self.orders[order_id].packed = tick

    def order_dispatched(self, order_id: str, tick: int) -> None:
        self.orders[order_id].dispatched = tick

    def add_distance(self, actor_id: str, metres: Fraction) -> None:
        self.distance_m[actor_id] += metres

    def counts(self) -> dict[str, int]:
        records = self.orders.values()
        return {
            "arrived_total": len(self.orders),
            "packed_total": sum(1 for r in records if r.packed is not None),
            "dispatched_total": sum(1 for r in records if r.dispatched is not None),
            "unfulfilled_inventory_total": sum(1 for r in records if r.rejected is not None),
        }
