"""Immutable facts attach actual unit context and packing assignment to native events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_models import CoordinatorEvent
from app.v3.light_flow_state import HumanState
from app.v3.stock_models import StockDelta

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def unit_event(
    engine: CoordinatorEngine,
    kind: str,
    order_id: str,
    *,
    worker: HumanState | None = None,
    delta: StockDelta | None = None,
    resources: tuple[str, ...] = (),
) -> None:
    packing = engine.packing_states.get(order_id)
    engine.events.append(
        CoordinatorEvent(
            len(engine.events),
            engine.tick,
            kind,
            order_id,
            actor_id=worker.spec.actor_id if worker else None,
            operation=worker.operation if worker else None,
            delta=delta,
            work_kind="unit_order",
            unit_context=engine.unit_contexts[order_id],
            packing=packing.view() if packing else None,
            packing_wait_reason=engine.packing_waits.get(order_id),
            resource_ids=resources,
        )
    )
