"""Embedded views cannot invent past milestones, forget observed clocks or falsify exposure."""

from dataclasses import fields
from typing import Any

from app.v3.coordinator_models import CoordinatorEvent
from app.v3.coordinator_run_effects import EventFacts
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.coordinator_run_resource_rules import packing_resources
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.whole_flow_models import WholeFlowEvent

RECEIPT_CLOCKS = {
    "admitted_tick": "receipt_admitted",
    "credited_tick": "receipt_credited",
    "placed_tick": "receipt_putaway",
    "returned_tick": "receipt_returned",
}
WHOLE_CLOCKS = {
    "admitted_tick": "whole_admitted",
    "picked_tick": "whole_picked",
    "buffered_tick": "whole_buffered",
    "buffer_picked_tick": "whole_buffer_picked",
    "shipped_tick": "whole_shipped",
    "returned_tick": "whole_returned",
}
PACK_CLOCKS = {
    "assigned_tick": "packing_reserved",
    "packed_tick": "packed",
    "cleared_tick": "packing_cleared",
    "released_tick": "packing_actor_released",
}


class ViewFacts:
    def __init__(self, inventory: InventoryJournal, events: tuple[FlowEvent, ...]) -> None:
        self.inventory, self.facts = inventory, EventFacts(events)
        self.clocks: dict[tuple[str, str, str], int] = {}

    def apply(self, event: FlowEvent) -> None:
        if isinstance(event, WholeFlowEvent) and event.whole_order is not None:
            view = event.whole_order
            self._clocks(event, "whole", view, WHOLE_CLOCKS)
            for clock, stage in (
                ("port_reserved_tick", "whole_pick_buffer"),
                ("service_started_tick", "whole_service"),
            ):
                tick = getattr(view, clock)
                if tick is not None:
                    self.facts.operation(event.order_id, "operation_started", stage, tick)
                self._remember(event, "whole", clock, tick)
            self._exposure(view, event.tick)
        if isinstance(event, ReceiptFlowEvent) and event.receipt is not None:
            self._clocks(event, "receipt", event.receipt, RECEIPT_CLOCKS)
            self._exposure(event.receipt, event.tick)
        if isinstance(event, CoordinatorEvent) and event.packing is not None:
            self._clocks(event, "packing", event.packing, PACK_CLOCKS)
            self._packing(event)

    def _clocks(self, event: FlowEvent, domain: str, view: Any, mapping: dict[str, str]) -> None:
        for name, kind in mapping.items():
            tick = getattr(view, name)
            if tick is not None:
                self.facts.one(event.order_id, kind, tick)
            self._remember(event, domain, name, tick)
        for field in fields(view):
            value = getattr(view, field.name)
            if (
                field.name.endswith("_tick")
                and value is not None
                and (type(value) is not int or not 0 <= value <= event.tick)
            ):
                raise ValueError("Embedded view invents a future or invalid actual clock")

    def _remember(self, event: FlowEvent, domain: str, field: str, tick: int | None) -> None:
        key = (event.order_id, domain, field)
        if key in self.clocks and self.clocks[key] != tick:
            raise ValueError("Embedded native view forgot or changed an observed actual milestone")
        if tick is not None:
            self.clocks[key] = tick

    @staticmethod
    def _exposure(view: Any, now: int) -> None:
        start, end = view.admitted_tick, view.returned_tick
        expected = 0 if start is None else min(now, end if end is not None else now) - start
        if view.paid_exposure_ticks != expected:
            raise ValueError("Embedded goods exposure differs from actual admitted interval")
        if hasattr(view, "port_reservation_ticks"):
            for field, start_name in (
                ("port_reservation_ticks", "port_reserved_tick"),
                ("port_service_ticks", "service_started_tick"),
            ):
                begin = getattr(view, start_name)
                end = view.shipped_tick
                expected = 0 if begin is None else min(now, end if end is not None else now) - begin
                if getattr(view, field) != expected:
                    raise ValueError(
                        "Embedded port exposure differs from actual reservation/service"
                    )

    def _packing(self, event: CoordinatorEvent) -> None:
        view = event.packing
        if view is None:
            raise ValueError("Missing native packing view")
        if (view.order_id, view.station_id) != (
            event.order_id,
            self.inventory.views[event.order_id].station.station_id,
        ):
            raise ValueError("Embedded packing view changed its declared order/station binding")
        reserved = self.facts.one(event.order_id, "packing_reserved", view.assigned_tick)
        if not isinstance(reserved, CoordinatorEvent) or reserved.packing is None:
            raise ValueError("Native packing view lacks its original assignment")
        original = reserved.packing
        same(
            (view.order_id, view.actor_id, view.station_id, view.role_intent_id),
            (event.order_id, original.actor_id, original.station_id, original.role_intent_id),
            "Embedded packing view changed its physical assignment",
        )
        if view.phase not in {
            "approach",
            "ready",
            "pack",
            "packed",
            "clear",
            "returning",
            "complete",
        }:
            raise ValueError("Unknown native packing phase")
        resources = packing_resources(self.inventory, event)
        held = (
            ()
            if view.phase == "complete"
            else resources[:1]
            if view.phase == "returning"
            else resources
        )
        same(view.held_resources, held, "Embedded packing view changed its actual resource set")
