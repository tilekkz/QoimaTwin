"""Closed event domains extend, rather than discard, coordinator boundary authority."""

from app.v3.coordinator_models import CoordinatorEvent
from app.v3.coordinator_run_boundaries import KINDS, _payload
from app.v3.light_flow_models import FlowEvent
from app.v3.relocation_models import RelocationProfile
from app.v3.relocation_observe import RelocationEvent, RelocationOutcome

RELOCATION_KINDS = frozenset(
    {
        "relocation_arrived",
        "relocation_wait_changed",
        "relocation_admitted",
        "inventory_claim_acquired",
        "inventory_claim_released",
        "relocation_resource_acquired",
        "relocation_resource_released",
        "operation_started",
        "operation_completed",
        "relocation_taken",
        "relocation_placed",
        "relocation_state_changed",
        "relocation_returned",
    }
)


def event_boundaries(profile: RelocationProfile, outcome: RelocationOutcome) -> None:
    common, flow = profile.coordinator, profile.coordinator.world.receipts.flow
    jobs = {o.order_id for o in flow.orders} | {o.job_id for o in common.world.orders}
    jobs |= {r.definition.receipt_id for r in common.world.receipts.receipts}
    jobs |= {i.intent_id for i in common.intents}
    jobs |= {"availability:" + a.actor_id for a in flow.actors}
    relocation = {j.job_id for j in profile.jobs}
    previous = 0
    for seq, event in enumerate(outcome.events):
        if event.seq != seq or not previous <= event.tick <= outcome.at_end.tick:
            raise ValueError("N1 event sequence or actual clock is invalid")
        if event.order_id in relocation:
            _relocation_payload(event)
        elif event.order_id in jobs:
            _base_payload(common, event)
        else:
            raise ValueError("N1 event references an undeclared physical job")
        previous = event.tick


def _base_payload(profile: object, event: FlowEvent) -> None:
    from app.v3.coordinator_models import CoordinatorProfile

    assert isinstance(profile, CoordinatorProfile)
    if isinstance(event, RelocationEvent):
        raise ValueError("Relocation payload overwrites another native domain")
    if event.kind not in KINDS and not event.kind.startswith("belt:"):
        raise ValueError("Unknown native coordinator event kind")
    if event.kind.startswith("belt:") and type(event) is not FlowEvent:
        raise ValueError("Conveyor event contains unrelated native payload")
    if isinstance(event, CoordinatorEvent) and event.work_kind not in {
        "unit_order",
        "role_intent",
        "availability",
    }:
        raise ValueError("Unknown coordinator namespace")
    _payload(profile, event)


def _relocation_payload(event: FlowEvent) -> None:
    if type(event) is not RelocationEvent or event.kind not in RELOCATION_KINDS:
        raise ValueError("Exact declared relocation event required")
    if event.relocation is None or event.work_kind != "relocation":
        raise ValueError("Relocation fact lost its actual progress")
    if any(
        (
            event.receipt,
            event.whole_order,
            event.role_view,
            event.unit_context,
            event.packing,
            event.packing_wait_reason,
            event.resource_ids,
            event.belt_event,
        )
    ):
        raise ValueError("Relocation fact contains another physical work payload")
    operation = event.kind in {"operation_started", "operation_completed"}
    if (event.operation is not None) != operation:
        raise ValueError("Relocation operation interval has the wrong event kind")
