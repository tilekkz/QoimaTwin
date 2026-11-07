"""Order milestones, backward-compatible counters and windowed order statistics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(slots=True)
class OrderRecord:
    arrival: int
    admitted: int | None = None
    picked: int | None = None
    packed: int | None = None
    dispatched: int | None = None
    rejected: int | None = None


@dataclass(slots=True)
class Metrics:
    orders: dict[str, OrderRecord] = field(default_factory=dict)
    distance_m: dict[str, Fraction] = field(default_factory=lambda: defaultdict(Fraction))

    queue_samples: list[tuple[int, dict[str, int]]] = field(default_factory=list)

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

    def order_summary(self, cutoff: int, tps: int, *, inclusive: bool) -> dict[str, object]:
        def seen(tick: int | None) -> bool:
            return tick is not None and (tick <= cutoff if inclusive else tick < cutoff)

        records = [r for r in self.orders.values() if seen(r.arrival)]
        done = [r for r in records if seen(r.dispatched)]
        backlog = [r for r in records if not seen(r.dispatched)]
        rejected = sum(seen(r.rejected) for r in records)
        cycles = [(r.dispatched - r.arrival) / tps for r in done if r.dispatched is not None]
        ages = [(cutoff - r.arrival) / tps for r in backlog]
        makespan = max((r.dispatched or 0 for r in done), default=0) / tps
        return {
            "arrived_total": len(records),
            "admitted_total": sum(seen(r.admitted) for r in records),
            "admitted_wip": sum(seen(r.admitted) and not seen(r.dispatched) for r in records),
            "picked_total": sum(seen(r.picked) for r in records),
            "packed_total": sum(seen(r.packed) for r in records),
            "dispatched_total": len(done),
            "unfulfilled_inventory_total": rejected,
            "backlog": len(backlog),
            "pending_total": len(backlog) - rejected,
            "completion_rate": len(done) / len(records) if records else None,
            "cycle": distribution(cycles),
            "packed_cycle": distribution(
                [
                    (r.packed - r.arrival) / tps
                    for r in records
                    if r.packed is not None and seen(r.packed)
                ]
            ),
            "backlog_age": distribution(ages),
            "backlog_max_age_s": max(ages, default=None),
            "rejection_reasons": {"unfulfilled_inventory": rejected} if rejected else {},
            "all_orders_makespan_s": makespan if records and not backlog else None,
            "last_dispatch_s": makespan if done else None,
        }


def distribution(values: list[float]) -> dict[str, float | None]:
    """Mean and type-7 (linear) p95; empty populations are undefined."""
    if not values:
        return {"mean_s": None, "p95_s": None}
    ordered = sorted(values)
    rank = (len(ordered) - 1) * 0.95
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return {
        "mean_s": sum(values) / len(values),
        "p95_s": ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower),
    }
