"""Integer observation boundaries, complete native event vocabulary and captured cadence."""

from bisect import bisect_right

from app.v3.coordinator_models import (
    CoordinatorEvent,
    CoordinatorOutcome,
    CoordinatorProfile,
    CoordinatorSnapshot,
)
from app.v3.light_flow_models import FlowEvent

KINDS = frozenset(
    {
        "order_arrived",
        "order_admitted",
        "actor_assigned",
        "operation_started",
        "operation_completed",
        "carrier_attached",
        "carrier_reattached",
        "carrier_detached",
        "source_carrier_detached",
        "picked",
        "intake_handoff",
        "package_prepared",
        "packed",
        "empty_carrier_cleared",
        "parcel_loaded",
        "output_ready",
        "output_collected",
        "shipped",
        "unit_context_bound",
        "packing_reserved",
        "packing_deferred",
        "packing_cleared",
        "packing_actor_released",
        "cart_released",
        "picker_returned",
        "parcel_shipper_returned",
        "parcel_capacity_reserved",
        "parcel_capacity_committed",
        "inventory_claim_acquired",
        "inventory_claim_released",
        "receipt_arrived",
        "receipt_admitted",
        "receipt_wait_changed",
        "receipt_state_changed",
        "receipt_credited",
        "receipt_buffered",
        "receipt_buffer_picked",
        "receipt_putaway",
        "receipt_returned",
        "receipt_resource_acquired",
        "receipt_resource_released",
        "whole_arrived",
        "whole_admitted",
        "whole_wait_changed",
        "whole_state_changed",
        "whole_picked",
        "whole_buffered",
        "whole_buffer_picked",
        "whole_shipped",
        "whole_returned",
        "whole_resource_acquired",
        "whole_resource_released",
        "role_requested",
        "role_transition_assigned",
        "role_activated",
        "role_restored",
        "role_return_waiting",
        "role_rejected",
        "availability_changed",
    }
)


def event_boundaries(profile: CoordinatorProfile, outcome: CoordinatorOutcome) -> None:
    flow = profile.world.receipts.flow
    jobs = {o.order_id for o in flow.orders} | {o.job_id for o in profile.world.orders}
    jobs |= {r.definition.receipt_id for r in profile.world.receipts.receipts}
    jobs |= {i.intent_id for i in profile.intents}
    jobs |= {"availability:" + a.actor_id for a in flow.actors}
    previous = 0
    for seq, event in enumerate(outcome.events):
        if event.seq != seq or not previous <= event.tick <= outcome.at_end.tick:
            raise ValueError("Coordinator events require actual contiguous chronological sequence")
        if event.kind not in KINDS and not event.kind.startswith("belt:"):
            raise ValueError("Unknown native coordinator event kind")
        if event.order_id not in jobs:
            raise ValueError("Coordinator event references an undeclared job or actor")
        if event.kind.startswith("belt:") and type(event) is not FlowEvent:
            raise ValueError("Conveyor event cannot contain unrelated coordinator payload")
        if isinstance(event, CoordinatorEvent) and event.work_kind not in {
            "unit_order",
            "role_intent",
            "availability",
        }:
            raise ValueError("Unknown native coordinator work namespace")
        _payload(profile, event)
        previous = event.tick


def _payload(profile: CoordinatorProfile, event: FlowEvent) -> None:
    if event.operation is not None and event.kind not in {
        "operation_started",
        "operation_completed",
    }:
        raise ValueError("Unexpected operation interval on a non-operation native fact")
    if not isinstance(event, CoordinatorEvent):
        return
    if event.order_id in {i.intent_id for i in profile.intents}:
        expected = "role_intent"
    elif event.order_id.startswith("availability:"):
        expected = "availability"
    elif event.order_id in {o.order_id for o in profile.world.receipts.flow.orders}:
        expected = "unit_order"
    else:
        raise ValueError("Coordinator payload is attached to another native work domain")
    if event.work_kind != expected:
        raise ValueError("Coordinator work namespace does not match its declared identity")
    if expected != "unit_order" and any(
        (
            event.unit_context is not None,
            event.packing is not None,
            event.packing_wait_reason is not None,
            bool(event.resource_ids),
        )
    ):
        raise ValueError("Role/availability event contains unrelated goods payload")
    if event.receipt is not None or event.whole_order is not None:
        raise ValueError("Coordinator role/unit payload cannot overwrite receipt or whole views")
    if expected == "availability" and event.role_view is not None:
        raise ValueError("Availability event cannot create a role assignment")


def captures(
    outcome: CoordinatorOutcome, horizon: int, cap: int
) -> tuple[CoordinatorSnapshot, ...]:
    end = outcome.at_end.tick
    if not 0 < horizon <= end <= cap or outcome.at_horizon.tick != horizon:
        raise ValueError("Coordinator H/end boundaries differ from requested input clocks")
    if outcome.observation_end_tick != end:
        raise ValueError("Coordinator observation end differs from actual final capture")
    expected = sorted({*range(0, end + 1, 30_000_000), end})
    if [s.tick for s in outcome.checkpoints] != expected:
        raise ValueError("Coordinator captures must retain exact cadence and final boundary")
    ticks = [e.tick for e in outcome.events]
    values = (*outcome.checkpoints, outcome.at_horizon, outcome.at_end)
    for state in values:
        if state.last_seq != bisect_right(ticks, state.tick) - 1:
            raise ValueError("Coordinator capture is not settled after every event with tick <= T")
        if state.belt.tick != state.tick:
            raise ValueError("Coordinator belt capture uses another physical clock")
    return tuple(sorted(values, key=lambda state: (state.tick, state.last_seq)))
