"""Finite common port and terminal promises are journaled without owner-prefix aliases."""

from collections import Counter
from urllib.parse import quote

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorSnapshot
from app.v3.coordinator_run_inventory import InventoryJournal, same
from app.v3.coordinator_run_resource_rules import expected_resources, packing_resources
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent


class ResourceJournal:
    def __init__(self, inventory: InventoryJournal, events: tuple[FlowEvent, ...]) -> None:
        self.inventory = inventory
        self.leases: dict[str, str] = {}
        self._required(events)

    def _required(self, events: tuple[FlowEvent, ...]) -> None:
        expected: Counter[tuple[str, int, str, bool]] = Counter()
        actual: Counter[tuple[str, int, str, bool]] = Counter()
        for event in events:
            acquired, resources = expected_resources(self.inventory, event)
            expected.update((event.order_id, event.tick, r, acquired) for r in resources)
            if event.kind in {
                "receipt_resource_acquired",
                "receipt_resource_released",
                "whole_resource_acquired",
                "whole_resource_released",
            }:
                if not isinstance(event, ReceiptFlowEvent) or event.resource_id is None:
                    raise ValueError("Resource transition lacks its actual named resource")
                actual[
                    event.order_id, event.tick, event.resource_id, event.kind.endswith("_acquired")
                ] += 1
        if actual != expected:
            raise ValueError("Resource facts differ from required physical transitions")
        self._parcel_facts(events)

    def _parcel_facts(self, events: tuple[FlowEvent, ...]) -> None:
        expected: Counter[tuple[str, int, str]] = Counter()
        actual: Counter[tuple[str, int, str]] = Counter()
        for event in events:
            if event.order_id not in self.inventory.units:
                continue
            if (
                event.kind == "operation_started"
                and event.operation is not None
                and event.operation.kind == "shipping_service"
            ):
                expected[event.order_id, event.tick, "parcel_capacity_reserved"] += 1
            if event.kind == "shipped":
                expected[event.order_id, event.tick, "parcel_capacity_committed"] += 1
            if event.kind in {"parcel_capacity_reserved", "parcel_capacity_committed"}:
                actual[event.order_id, event.tick, event.kind] += 1
        if actual != expected:
            raise ValueError("Every parcel service requires its actual common port promise")

    def apply(self, event: FlowEvent) -> None:
        if event.kind in {
            "receipt_resource_acquired",
            "receipt_resource_released",
            "whole_resource_acquired",
            "whole_resource_released",
        }:
            if not isinstance(event, ReceiptFlowEvent) or event.resource_id is None:
                raise ValueError("Resource event has no actual named resource")
            self._change(event.resource_id, event.order_id, event.kind.endswith("_acquired"))
        elif event.kind in {"packing_reserved", "packing_cleared", "packing_actor_released"}:
            self._packing(event)
        elif event.kind in {"parcel_capacity_reserved", "parcel_capacity_committed"}:
            self._parcel(event)
        elif isinstance(event, ReceiptFlowEvent) and event.resource_id is not None:
            raise ValueError("Unexpected named resource payload")

    def _change(self, resource: str, job: str, acquire: bool) -> None:
        if acquire:
            if resource in self.leases:
                raise ValueError("Finite physical resource has simultaneous owners")
            self.leases[resource] = job
        else:
            if self.leases.pop(resource, None) != job:
                raise ValueError("Physical resource release has no matching actual owner")

    def _packing(self, event: FlowEvent) -> None:
        resources = packing_resources(self.inventory, event)
        expected = (
            resources
            if event.kind == "packing_reserved"
            else (resources[1:] if event.kind == "packing_cleared" else resources[:1])
        )
        if not isinstance(event, CoordinatorEvent):
            raise ValueError("Native packing resource fact required")
        same(event.resource_ids, expected, "Packing resource identifiers differ")
        for resource in expected:
            self._change(resource, event.order_id, event.kind == "packing_reserved")

    def _parcel(self, event: FlowEvent) -> None:
        if not isinstance(event, CoordinatorEvent) or event.order_id not in self.inventory.views:
            raise ValueError("Parcel capacity requires its declared multi-port context")
        resource = "port:" + self.inventory.views[event.order_id].port.port_id
        same(event.resource_ids, (resource,), "Parcel capacity promise changed physical port")
        self._change(resource, event.order_id, event.kind == "parcel_capacity_reserved")

    def check_capacity(self) -> None:
        flow = self.inventory.profile.world.receipts.flow
        limits = {
            o.owner_id: o.capacity
            for o in (*flow.stock.owners, *flow.owners)
            if o.kind == "shipped"
        }
        used: dict[str, set[str]] = {key: set() for key in limits}
        for container in self.inventory.ledger.snapshot().containers:
            if container.owner_id in used:
                used[container.owner_id].add(container.container_id)
        for key, whole_order in self.inventory.whole.items():
            port = self.inventory.whole_ports[whole_order.port_id]
            if self.leases.get("port:" + port.port_id) == key:
                used[port.shipped_owner].add(whole_order.hu_id)
        for key, unit_order in self.inventory.units.items():
            view = self.inventory.views[key]
            if self.leases.get("port:" + view.port.port_id) == key:
                used[view.shipped_owner].add(unit_order.package_id)
        if any(len(used[key]) > limit for key, limit in limits.items()):
            raise ValueError("Shared terminal capacity exceeds placed and promised containers")
        self._empty_capacity()

    def _empty_capacity(self) -> None:
        flow = self.inventory.profile.world.receipts.flow
        owners = {view.station.empty_owner for view in self.inventory.views.values()}
        limits = {
            o.owner_id: o.capacity
            for o in (*flow.stock.owners, *flow.owners)
            if o.owner_id in owners
        }
        used = {owner: set[str]() for owner in owners}
        for container in self.inventory.ledger.snapshot().containers:
            if container.owner_id in used:
                used[container.owner_id].add(container.container_id)
        for key, order in self.inventory.units.items():
            owner = self.inventory.views[key].station.empty_owner
            resource = "pack:empty:" + quote(owner, safe="") + ":" + quote(key, safe="")
            if self.leases.get(resource) == key:
                used[owner].add(order.carrier_id)
        if any(len(used[owner]) > limits[owner] for owner in owners):
            raise ValueError("Empty-carrier capacity exceeds placed and promised carriers")

    def check(self, state: CoordinatorSnapshot) -> None:
        prefixes = ("receipt:", "whole:", "pack:", "port:")
        actual = {key: value for key, value in state.leases if key.startswith(prefixes)}
        same(actual, self.leases, "Captured finite resource ownership differs from journal")
        self.check_capacity()
