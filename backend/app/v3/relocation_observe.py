"""Opt-in N1 observations; existing coordinator publication does not support these types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorOutcome, CoordinatorSnapshot
from app.v3.relocation_models import RelocationPlan

if TYPE_CHECKING:
    from app.v3.relocation_engine import RelocationEngine


@dataclass(frozen=True, slots=True)
class RelocationView:
    job_id: str
    hu_id: str
    actor_id: str
    source_owner: str
    destination_owner: str
    status: str
    admitted_tick: int | None
    taken_tick: int | None
    placed_tick: int | None
    returned_tick: int | None
    completed_steps: int
    wait_reason: str | None


@dataclass
class RelocationState:
    plan: RelocationPlan
    status: str = "unreleased"
    admitted_tick: int | None = None
    taken_tick: int | None = None
    placed_tick: int | None = None
    returned_tick: int | None = None
    completed_steps: int = 0
    wait_reason: str | None = None
    paid_before: int = 0

    def view(self) -> RelocationView:
        job = self.plan.job
        return RelocationView(
            job.job_id,
            job.hu_id,
            job.actor_id,
            job.from_slot_id,
            job.to_slot_id,
            self.status,
            self.admitted_tick,
            self.taken_tick,
            self.placed_tick,
            self.returned_tick,
            self.completed_steps,
            self.wait_reason,
        )


@dataclass(frozen=True, slots=True)
class RelocationEvent(CoordinatorEvent):
    work_kind: str = "relocation"
    relocation: RelocationView | None = None


@dataclass(frozen=True, slots=True)
class RelocationSnapshot(CoordinatorSnapshot):
    relocations: tuple[RelocationView, ...] = ()
    derived_sources: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RelocationOutcome(CoordinatorOutcome):
    at_horizon: RelocationSnapshot
    at_end: RelocationSnapshot
    checkpoints: tuple[RelocationSnapshot, ...] = ()


def snapshot(engine: RelocationEngine, base: CoordinatorSnapshot) -> RelocationSnapshot:
    return RelocationSnapshot(
        base.tick,
        base.stock,
        base.balance,
        base.workers,
        base.orders,
        base.leases,
        base.belt,
        base.last_seq,
        base.cart,
        base.inventory,
        base.receipts,
        base.whole_orders,
        base.roles,
        base.actor_roles,
        base.role_bindings,
        base.exposure,
        base.unit_contexts,
        base.packing,
        base.packing_waits,
        base.carts,
        base.cart_releases,
        base.unit_progress,
        tuple(state.view() for state in engine.relocations.values()),
        tuple(sorted(engine.derived_sources.items())),
    )


def native(value: CoordinatorSnapshot) -> RelocationSnapshot:
    if not isinstance(value, RelocationSnapshot):
        raise RuntimeError("RELOCATION_SNAPSHOT_REQUIRED")
    return value


def outcome(base: CoordinatorOutcome) -> RelocationOutcome:
    return RelocationOutcome(
        base.status,
        base.events,
        native(base.at_horizon),
        native(base.at_end),
        tuple(native(s) for s in base.checkpoints),
        base.business_complete_tick,
        base.resource_drained_tick,
        base.observation_end_tick,
        base.staffing_status,
        base.constraint_violations,
    )
