"""Whole claims and exact finite resources extend, rather than weaken, receipt facts."""

from urllib.parse import quote

from app.v3.interface import Json
from app.v3.receipt_run_facts import ReceiptFacts
from app.v3.receipt_run_journal import InventoryJournal, same


class WholeFacts(ReceiptFacts):
    def __init__(self, catalog: Json, events: list[Json], inventory: InventoryJournal) -> None:
        self.orders = {o["job_id"]: o for o in catalog["whole_process"]["orders"]}
        self.ports = {p["port_id"]: p for p in catalog["whole_process"]["ports"]}
        self.whole_resources: dict[str, str] = {}
        self.whole_views: dict[str, Json] = {}
        self.whole_actors: dict[str, str] = {}
        self.whole_buffers: dict[str, str] = {}
        self.milestones: dict[str, dict[str, int]] = {k: {} for k in self.orders}
        super().__init__(catalog, events, inventory)
        self._required_whole(events)

    def apply(self, event: Json) -> None:
        key, kind, tick = event["order_id"], event["kind"], event["tick"]
        if key not in self.orders:
            self._parcel_resource(event)
            super().apply(event)
            return
        view = event["whole_order"]
        if view is None or view["job_id"] != key or event["receipt"] is not None:
            raise ValueError("Whole job event has lost its exact native view")
        self._actor(event)
        self.whole_views[key] = view
        if kind == "inventory_claim_acquired":
            self._acquire_whole(event)
        elif kind == "inventory_claim_released":
            claim_id = event["released_claim_id"]
            if claim_id != "whole:" + key or self.claims[claim_id]["job_id"] != key:
                raise ValueError("Whole claim release does not own its actual inventory")
            self._trigger(key, "whole_shipped", tick)
            del self.claims[claim_id]
            self.generation += 1
        elif kind in {"whole_resource_acquired", "whole_resource_released"}:
            self._whole_resource(event)
        elif any(
            event[k] is not None for k in ("inventory_claim", "released_claim_id", "resource_id")
        ):
            raise ValueError("Whole fact payload has incorrect event kind")
        self._milestone(event)

    def _actor(self, event: Json) -> None:
        key, view, actor = event["order_id"], event["whole_order"], event["actor_id"]
        if actor != view["actor_id"]:
            raise ValueError("Whole event actor differs from its actual assigned view")
        if view["admitted_tick"] is not None:
            port = self.ports[self.orders[key]["port_id"]]
            if actor not in port["shipper_ids"]:
                raise ValueError("Whole view actor is outside its declared eligible pool")
            buffer = view["buffer_owner_id"]
            if buffer not in port["buffer_ids"]:
                raise ValueError("Whole buffer is not permitted by the selected source port")
            if self.whole_buffers.setdefault(key, buffer) != buffer:
                raise ValueError("Whole admitted buffer assignment changed during physical work")
            assigned = self.whole_actors.setdefault(key, actor)
            if actor != assigned:
                raise ValueError("Whole actor assignment changed during physical work history")
        elif actor is not None or key in self.whole_actors:
            raise ValueError("Whole actor assignment cannot precede admission or disappear")

    def _acquire_whole(self, event: Json) -> None:
        key, claim = event["order_id"], event["inventory_claim"]
        hu = self.orders[key]["hu_id"]
        units = sorted(u for u, loc in self.inventory.locations.items() if loc[0] == hu)
        expected = {
            "claim_id": "whole:" + key,
            "job_id": key,
            "container_id": hu,
            "unit_ids": units,
            "whole_hu": True,
        }
        same(claim, expected, "Whole claim must protect the complete existing physical HU")
        if not units or expected["claim_id"] in self.claims:
            raise ValueError("Whole claim is empty or already active")
        if any(
            set(units).intersection(c["unit_ids"]) or c["container_id"] == hu
            for c in self.claims.values()
        ):
            raise ValueError("Whole claim conflicts with already promised stock")
        self._trigger(key, "whole_admitted", event["tick"])
        self.claims[expected["claim_id"]] = expected
        self.generation += 1

    def _whole_resource(self, event: Json) -> None:
        key, resource, tick = event["order_id"], event["resource_id"], event["tick"]
        view, order = event["whole_order"], self.orders[key]
        port = self.ports[order["port_id"]]
        resources = resource_rules(order, port, view)
        if resource not in resources:
            raise ValueError("Whole event uses an undeclared or aliased resource")
        start, finish = resources[resource]
        if event["kind"] == "whole_resource_acquired":
            if resource in self.whole_resources:
                raise ValueError("Whole/shared port resource has simultaneous owners")
            if start == "reserve":
                self._trigger(key, "operation_started", tick)
                self.milestones[key]["port_reserved_tick"] = tick
            else:
                self._trigger(key, start, tick)
            self.whole_resources[resource] = key
        else:
            if self.whole_resources.get(resource) != key:
                raise ValueError("Whole resource release lacks actual ownership")
            self._trigger(key, finish, tick)
            del self.whole_resources[resource]

    def _required_whole(self, events: list[Json]) -> None:
        self._arrivals(events)
        for event in events:
            key, kind, tick = event["order_id"], event["kind"], event["tick"]
            if key not in self.orders:
                continue
            if kind in {"whole_admitted", "whole_shipped"}:
                trigger = (
                    "inventory_claim_acquired"
                    if kind == "whole_admitted"
                    else "inventory_claim_released"
                )
                self._trigger(key, trigger, tick)
            order, view = self.orders[key], event["whole_order"]
            if view is None:
                raise ValueError("Whole event requires its native view")
            rules = resource_rules(order, self.ports[order["port_id"]], view)
            for resource, (start, end) in rules.items():
                acquiring = kind == start or (
                    start == "reserve"
                    and kind == "operation_started"
                    and event["operation"]["kind"] == "whole_pick_buffer"
                )
                releasing = kind == end
                if acquiring or releasing:
                    required = "whole_resource_acquired" if acquiring else "whole_resource_released"
                    matches = [
                        e
                        for e in events
                        if e["order_id"] == key
                        and e["tick"] == tick
                        and e["kind"] == required
                        and e["resource_id"] == resource
                    ]
                    if len(matches) != 1:
                        raise ValueError("Whole transition lacks its exact finite resource fact")

    def _arrivals(self, events: list[Json]) -> None:
        allowed = {
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
            "inventory_claim_acquired",
            "inventory_claim_released",
            "operation_started",
            "operation_completed",
        }
        for event in events:
            if event["order_id"] in self.orders and event["kind"] not in allowed:
                raise ValueError("Unknown whole event kind")
        end = events[-1]["tick"] if events else 0
        for key, order in self.orders.items():
            arrivals = [e for e in events if e["order_id"] == key and e["kind"] == "whole_arrived"]
            expected = [order["arrival_tick"]] if order["arrival_tick"] <= end else []
            same(
                [e["tick"] for e in arrivals],
                expected,
                "Whole arrival event differs from offered clock",
            )

    def _milestone(self, event: Json) -> None:
        names = {
            "whole_admitted": "admitted_tick",
            "whole_picked": "picked_tick",
            "whole_buffered": "buffered_tick",
            "whole_buffer_picked": "buffer_picked_tick",
            "whole_shipped": "shipped_tick",
            "whole_returned": "returned_tick",
        }
        kind, key = event["kind"], event["order_id"]
        if kind == "operation_started" and event["operation"]["kind"] == "whole_service":
            names[kind] = "service_started_tick"
        if kind in names:
            field = names[kind]
            if field in self.milestones[key]:
                raise ValueError("Whole physical stage completed twice")
            self.milestones[key][field] = event["tick"]

    def _parcel_resource(self, event: Json) -> None:
        port = "port:" + self.catalog["workflow_profile"]["port"]["port_id"]
        if (
            event["kind"] == "operation_started"
            and event["operation"]["kind"] == "shipping_service"
        ):
            if port in self.whole_resources:
                raise ValueError("Parcel and whole HU overlap on the same finite port")
            self.whole_resources[port] = event["order_id"]
        if event["kind"] == "shipped":
            if self.whole_resources.get(port) != event["order_id"]:
                raise ValueError("Parcel shipment lacks actual shared port ownership")
            del self.whole_resources[port]

    def check(self, state: Json, tick: int) -> None:
        super().check(state, tick)
        self.check_shipped_capacity()
        actual = sorted(
            (r, k) for r, k in state["leases"] if r.startswith("whole:") or r.startswith("port:")
        )
        same(
            actual, sorted(self.whole_resources.items()), "Whole captured resource journal differs"
        )
        views = {r["job_id"]: r for r in state["whole_orders"]}
        if len(views) != len(state["whole_orders"]) or views.keys() != self.orders.keys():
            raise ValueError("Whole captured job identities differ")
        for key, row in views.items():
            expected = dict(self.whole_views.get(key, row))
            for field, start, end in (
                ("paid_exposure_ticks", "admitted_tick", "returned_tick"),
                ("port_reservation_ticks", "port_reserved_tick", "shipped_tick"),
                ("port_service_ticks", "service_started_tick", "shipped_tick"),
            ):
                expected[field] = (
                    0
                    if expected[start] is None
                    else min(tick, expected[end] or tick) - expected[start]
                )
            same(row, expected, "Whole captured view differs from its actual transition journal")
            clocks = {k: row[k] for k in row if k.endswith("_tick") and row[k] is not None}
            same(clocks, self.milestones[key], "Whole captured chronology invents a transition")

    def check_shipped_capacity(self) -> None:
        limits = {
            o["owner_id"]: o["capacity"] for o in self.catalog["owners"] if o["kind"] == "shipped"
        }
        usage: dict[str, set[str]] = {owner: set() for owner in limits}
        for container in self.inventory.containers.values():
            if container["owner_id"] in usage:
                usage[container["owner_id"]].add(container["container_id"])
        for key, order in self.orders.items():
            port = self.ports[order["port_id"]]
            if self.whole_resources.get("port:" + port["port_id"]) == key:
                usage[port["shipped_owner"]].add(order["hu_id"])
        self._parcel_terminal_usage(usage)
        if any(len(usage[owner]) > capacity for owner, capacity in limits.items()):
            raise ValueError("Shared terminal capacity exceeds placed and promised containers")

    def _parcel_terminal_usage(self, usage: dict[str, set[str]]) -> None:
        flow = self.catalog["workflow_profile"]
        key = self.whole_resources.get("port:" + flow["port"]["port_id"])
        for order in self.catalog["orders"]:
            if order["order_id"] == key:
                usage[flow["shipped_owner"]].add(order["package_id"])


def resource_rules(order: Json, port: Json, view: Json) -> dict[str, tuple[str, str]]:
    shipped = (
        "whole:shipped:"
        + quote(port["shipped_owner"], safe="")
        + ":"
        + quote(order["job_id"], safe="")
    )
    return {
        "whole:worker:" + str(view["actor_id"]): ("whole_admitted", "whole_returned"),
        "whole:hu:" + order["hu_id"]: ("whole_admitted", "whole_shipped"),
        "whole:place:" + str(view["buffer_owner_id"]): ("whole_admitted", "whole_buffer_picked"),
        "port:" + port["port_id"]: ("reserve", "whole_shipped"),
        shipped: ("reserve", "whole_shipped"),
    }
