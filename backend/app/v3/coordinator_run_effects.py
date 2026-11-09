"""Every stock handover is caused by one actual completed paid stage, in both directions."""

from collections import defaultdict

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.light_flow_models import FlowEvent

EFFECTS = {
    "attach": ("carrier_attached",),
    "source_attach": ("carrier_reattached",),
    "detach": ("carrier_detached",),
    "source_detach": ("source_carrier_detached",),
    "pick": ("picked",),
    "deposit": ("intake_handoff",),
    "pack": ("packed",),
    "clear": ("empty_carrier_cleared", "parcel_loaded"),
    "pickup_package": ("output_collected",),
    "shipping_service": ("shipped",),
    "receipt_service": ("receipt_credited",),
    "receipt_place_buffer": ("receipt_buffered",),
    "receipt_pick_buffer": ("receipt_buffer_picked",),
    "receipt_place_slot": ("receipt_putaway",),
    "whole_pick_slot": ("whole_picked",),
    "whole_place_buffer": ("whole_buffered",),
    "whole_pick_buffer": ("whole_buffer_picked",),
    "whole_service": ("whole_shipped",),
}


class EventFacts:
    def __init__(self, events: tuple[FlowEvent, ...]) -> None:
        self.rows: dict[tuple[str, str, int], list[FlowEvent]] = defaultdict(list)
        self.operations: dict[tuple[str, str, str, int], list[FlowEvent]] = defaultdict(list)
        for event in events:
            self.rows[event.order_id, event.kind, event.tick].append(event)
            if event.kind in {"operation_started", "operation_completed"}:
                if event.operation is None:
                    raise ValueError("Actual operation fact is missing its native interval")
                self.operations[
                    event.order_id, event.kind, event.operation.kind, event.tick
                ].append(event)

    def one(self, key: str, kind: str, tick: int) -> FlowEvent:
        rows = self.rows.get((key, kind, tick), [])
        if len(rows) != 1:
            raise ValueError("Physical transition requires one actual " + kind + " fact")
        return rows[0]

    def operation(self, key: str, kind: str, stage: str, tick: int) -> FlowEvent:
        rows = self.operations.get((key, kind, stage, tick), [])
        if len(rows) != 1:
            raise ValueError("Physical handover requires one actual declared operation")
        return rows[0]


def validate_effects(
    profile: CoordinatorProfile, events: tuple[FlowEvent, ...], horizon: int, observed: int
) -> None:
    facts = EventFacts(events)
    inverse = {effect: stage for stage, values in EFFECTS.items() for effect in values}
    for event in events:
        if event.kind in {*inverse, "package_prepared"} and event.delta is None:
            raise ValueError("Physical handover fact lacks its actual stock delta")
        if event.delta is not None:
            stage = inverse.get(event.kind)
            if event.kind == "package_prepared":
                facts.operation(event.order_id, "operation_started", "pack", event.tick)
            elif stage is None:
                raise ValueError("Stock delta has no declared physical handover kind")
            else:
                actual = facts.operation(event.order_id, "operation_completed", stage, event.tick)
                if event.actor_id is not None and event.actor_id != actual.actor_id:
                    raise ValueError("Handover actor differs from its actual completed operation")
        if event.kind == "operation_completed" and event.operation is not None:
            for effect in EFFECTS.get(event.operation.kind, ()):
                if facts.one(event.order_id, effect, event.tick).delta is None:
                    raise ValueError("Completed physical handover lacks its stock delta")
        if (
            event.kind == "operation_started"
            and event.operation is not None
            and event.operation.kind == "pack"
        ):
            facts.one(event.order_id, "package_prepared", event.tick)
    _arrivals(profile, facts, events, horizon, observed)


def _arrivals(
    profile: CoordinatorProfile,
    facts: EventFacts,
    events: tuple[FlowEvent, ...],
    horizon: int,
    observed: int,
) -> None:
    flows = {
        o.order_id: (o.arrival_tick, "order_arrived", "order_admitted")
        for o in profile.world.receipts.flow.orders
    }
    flows.update(
        (o.job_id, (o.arrival_tick, "whole_arrived", "whole_admitted"))
        for o in profile.world.orders
    )
    flows.update(
        (o.definition.receipt_id, (o.arrival_tick, "receipt_arrived", "receipt_admitted"))
        for o in profile.world.receipts.receipts
    )
    for key, (arrival, arrived, _) in flows.items():
        if arrival <= observed:
            facts.one(key, arrived, arrival)
    for event in events:
        if event.order_id not in flows:
            continue
        arrival, arrived, admitted = flows[event.order_id]
        if event.kind == arrived and event.tick != arrival:
            raise ValueError("Arrival fact differs from the explicit offered clock")
        if event.kind == admitted:
            if not arrival <= event.tick < horizon:
                raise ValueError("Admission violates the common half-open horizon")
            facts.one(event.order_id, arrived, arrival)
        if event.kind in {"order_admitted", "whole_admitted", "receipt_credited"}:
            facts.one(event.order_id, "inventory_claim_acquired", event.tick)
        if arrived == "receipt_arrived" and event.kind == "receipt_putaway":
            facts.one(event.order_id, "inventory_claim_released", event.tick)
        if event.kind == "inventory_claim_acquired":
            trigger = "receipt_credited" if arrived == "receipt_arrived" else admitted
            facts.one(event.order_id, trigger, event.tick)
        if arrived == "receipt_arrived" and event.kind == "inventory_claim_released":
            facts.one(event.order_id, "receipt_putaway", event.tick)
