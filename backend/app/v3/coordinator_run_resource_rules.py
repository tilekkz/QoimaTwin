"""Exact named-resource evidence for C receipts, intact HUs, parcels and local packing."""

from urllib.parse import quote

from app.v3.coordinator_models import CoordinatorEvent
from app.v3.coordinator_run_inventory import InventoryJournal
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.whole_flow_models import WholeFlowEvent


def whole_resources(inventory: InventoryJournal, event: FlowEvent) -> tuple[str, ...]:
    if not isinstance(event, WholeFlowEvent) or event.whole_order is None:
        raise ValueError("Whole resource fact lacks admitted native view")
    order, view = inventory.whole[event.order_id], event.whole_order
    if view.actor_id is None or view.buffer_owner_id is None:
        raise ValueError("Whole resource fact has no actual actor/buffer")
    port = inventory.whole_ports[order.port_id]
    return (
        "whole:worker:" + view.actor_id,
        "whole:place:" + view.buffer_owner_id,
        "whole:hu:" + order.hu_id,
        "port:" + port.port_id,
        "whole:shipped:" + quote(port.shipped_owner, safe="") + ":" + quote(order.job_id, safe=""),
    )


def receipt_resources(inventory: InventoryJournal, event: FlowEvent) -> tuple[str, ...]:
    if not isinstance(event, ReceiptFlowEvent) or event.receipt is None:
        raise ValueError("Receipt resource fact lacks admitted native view")
    offer, view = inventory.receipts[event.order_id], event.receipt
    if view.actor_id is None or view.buffer_owner_id is None:
        raise ValueError("Receipt resource fact has no actual actor/buffer")
    return (
        "receipt:worker:" + view.actor_id,
        "receipt:place:" + view.buffer_owner_id,
        "receipt:place:" + offer.slot_owner_id,
        "receipt:hu:" + offer.definition.hu_id,
        "receipt:port:" + offer.port_id,
    )


def packing_resources(inventory: InventoryJournal, event: FlowEvent) -> tuple[str, ...]:
    if not isinstance(event, CoordinatorEvent) or event.packing is None:
        raise ValueError("Packing resource fact lacks actual packing assignment")
    profile, order = inventory.views[event.order_id], inventory.units[event.order_id]
    return (
        "pack:worker:" + event.packing.actor_id,
        "pack:bench:" + quote(profile.station.bench_owner, safe=""),
        "pack:empty:"
        + quote(profile.station.empty_owner, safe="")
        + ":"
        + quote(order.order_id, safe=""),
        "pack:material:" + quote(order.package_id, safe=""),
    )


def expected_resources(
    inventory: InventoryJournal, event: FlowEvent
) -> tuple[bool, tuple[str, ...]]:
    kind, key = event.kind, event.order_id
    stage = event.operation.kind if event.operation is not None else None
    if key in inventory.whole:
        selected = _whole_effect(kind, stage)
        if selected is not None:
            acquire, indices = selected
            values = whole_resources(inventory, event)
            return acquire, tuple(values[i] for i in indices)
    if key in inventory.receipts:
        selected = _receipt_effect(kind, stage)
        if selected is not None:
            acquire, indices = selected
            values = receipt_resources(inventory, event)
            return acquire, tuple(values[i] for i in indices)
    return False, ()


def _whole_effect(kind: str, stage: str | None) -> tuple[bool, tuple[int, ...]] | None:
    values = {
        "whole_admitted": (True, (0, 1, 2)),
        "whole_buffer_picked": (False, (1,)),
        "whole_shipped": (False, (2, 3, 4)),
        "whole_returned": (False, (0,)),
    }
    if kind == "operation_started" and stage == "whole_pick_buffer":
        return True, (3, 4)
    return values.get(kind)


def _receipt_effect(kind: str, stage: str | None) -> tuple[bool, tuple[int, ...]] | None:
    values = {
        "receipt_admitted": (True, (0, 1, 2, 3)),
        "receipt_credited": (False, (4,)),
        "receipt_buffer_picked": (False, (1,)),
        "receipt_putaway": (False, (2, 3)),
        "receipt_returned": (False, (0,)),
    }
    if kind == "operation_started" and stage == "receipt_service":
        return True, (4,)
    return values.get(kind)
