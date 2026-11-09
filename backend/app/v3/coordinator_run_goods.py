"""Observed goods milestones and receipt/whole views share one integer event clock."""

from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.receipt_flow_state import ReceiptState
from app.v3.whole_flow_models import WholeFlowEvent
from app.v3.whole_flow_state import WholeState


class GoodsJournal:
    def __init__(self, inventory: InventoryJournal) -> None:
        self.inventory = inventory
        self.receipts = {key: ReceiptState(value) for key, value in inventory.receipts.items()}
        self.whole = {key: WholeState(value) for key, value in inventory.whole.items()}

    def apply(self, event: FlowEvent) -> None:
        key = event.order_id
        if key in self.receipts:
            self._receipt(event, self.receipts[key])
        elif key in self.whole:
            self._whole(event, self.whole[key])

    def _receipt(self, event: FlowEvent, state: ReceiptState) -> None:
        if not isinstance(event, ReceiptFlowEvent) or event.receipt is None:
            raise ValueError("Receipt event lost its actual native view")
        if event.actor_id != event.receipt.actor_id:
            raise ValueError("Receipt event actor differs from admitted physical custody")
        kind, stage = event.kind, event.operation.kind if event.operation else None
        milestones = {
            "receipt_admitted": ("admitted_tick", "approaching"),
            "receipt_credited": ("credited_tick", "carrying"),
            "receipt_putaway": ("placed_tick", "returning"),
            "receipt_returned": ("returned_tick", "complete"),
        }
        if kind in milestones:
            clock, status = milestones[kind]
            self._mark(state, clock, event.tick)
            state.status = status
        if kind == "receipt_admitted":
            state.actor_id, state.buffer_owner_id = (
                event.receipt.actor_id,
                event.receipt.buffer_owner_id,
            )
            state.wait_reason = None
        elif kind == "receipt_arrived":
            state.status = "waiting"
        elif kind == "operation_completed" and stage == "receipt_approach":
            state.status = "awaiting_service"
        elif kind == "operation_started" and stage == "receipt_service":
            state.status = "service"
        elif kind == "receipt_buffered":
            state.status = "buffered"
        elif kind == "receipt_buffer_picked":
            state.status = "carrying"
        if kind == "receipt_wait_changed":
            state.wait_reason = event.receipt.wait_reason
        if kind == "receipt_returned":
            state.wait_reason = None

    def _whole(self, event: FlowEvent, state: WholeState) -> None:
        if not isinstance(event, WholeFlowEvent) or event.whole_order is None:
            raise ValueError("Whole event lost its actual native view")
        if event.actor_id != event.whole_order.actor_id:
            raise ValueError("Whole event actor differs from admitted physical custody")
        kind, stage = event.kind, event.operation.kind if event.operation else None
        milestones = {
            "whole_admitted": ("admitted_tick", "approaching"),
            "whole_picked": ("picked_tick", "carrying"),
            "whole_buffered": ("buffered_tick", "buffered"),
            "whole_buffer_picked": ("buffer_picked_tick", "carrying"),
            "whole_shipped": ("shipped_tick", "returning"),
            "whole_returned": ("returned_tick", "complete"),
        }
        if kind in milestones:
            clock, status = milestones[kind]
            self._mark(state, clock, event.tick)
            state.status = status
        if kind == "whole_admitted":
            state.actor_id, state.buffer_owner_id = (
                event.whole_order.actor_id,
                event.whole_order.buffer_owner_id,
            )
            state.wait_reason = None
        elif kind == "whole_arrived":
            state.status = "waiting"
        elif kind == "operation_started" and stage == "whole_pick_buffer":
            self._mark(state, "port_reserved_tick", event.tick)
        elif kind == "operation_started" and stage == "whole_service":
            self._mark(state, "service_started_tick", event.tick)
            state.status = "service"
        if kind == "whole_wait_changed":
            state.wait_reason = event.whole_order.wait_reason
        if kind == "whole_returned":
            state.wait_reason = None

    @staticmethod
    def _mark(state: ReceiptState | WholeState, field: str, tick: int) -> None:
        if getattr(state, field) is not None:
            raise ValueError("Goods milestone occurred more than once")
        setattr(state, field, tick)

    def check(self, state: CoordinatorSnapshot) -> None:
        receipts = tuple(value.view(state.tick) for _, value in sorted(self.receipts.items()))
        whole = tuple(value.view(state.tick) for _, value in sorted(self.whole.items()))
        same(
            state.receipts, receipts, "Captured receipt state differs from actual goods milestones"
        )
        same(state.whole_orders, whole, "Captured whole state differs from actual goods milestones")
