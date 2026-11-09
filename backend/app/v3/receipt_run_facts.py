"""Claims and receipt resource facts must match native inventory and captured watermarks."""

from app.v3.interface import Json
from app.v3.receipt_run_journal import InventoryJournal, same


class ReceiptFacts:
    def __init__(self, catalog: Json, events: list[Json], inventory: InventoryJournal) -> None:
        self.catalog, self.inventory = catalog, inventory
        self.claims: dict[str, Json] = {}
        self.resources: dict[str, str] = {}
        self.generation = 0
        self.observed = {(e["order_id"], e["kind"], e["tick"]) for e in events}
        self._required_facts(events)
        self._service_resources(events)
        self.views = {
            key: {
                "receipt_id": key,
                "status": "unreleased",
                "actor_id": None,
                "buffer_owner_id": None,
                "admitted_tick": None,
                "credited_tick": None,
                "placed_tick": None,
                "returned_tick": None,
                "wait_reason": None,
                "paid_exposure_ticks": 0,
            }
            for key in inventory.offers
        }

    def apply(self, event: Json) -> None:
        key, kind, tick = event["order_id"], event["kind"], event["tick"]
        required = {
            "inventory_claim_acquired": "inventory_claim",
            "inventory_claim_released": "released_claim_id",
            "receipt_resource_acquired": "resource_id",
            "receipt_resource_released": "resource_id",
        }
        if kind in required and event[required[kind]] is None:
            raise ValueError("Actual claim/resource event has lost its required payload")
        view = event["receipt"]
        if view is not None:
            if key not in self.views or view["receipt_id"] != key:
                raise ValueError("Event references an unknown receipt view")
            self.views[key] = view
        if event["inventory_claim"] is not None:
            if kind != "inventory_claim_acquired":
                raise ValueError("Claim payload requires acquisition event")
            self._acquire(event)
        if event["released_claim_id"] is not None:
            claim_id = event["released_claim_id"]
            claim = self.claims[claim_id]
            trigger = "receipt_putaway" if claim["whole_hu"] else "picked"
            if kind != "inventory_claim_released" or claim["job_id"] != key:
                raise ValueError("Claim release has incorrect owner or kind")
            self._trigger(key, trigger, tick)
            del self.claims[claim_id]
            self.generation += 1
        if event["resource_id"] is not None:
            self._resource(event)

    def _trigger(self, key: str, kind: str, tick: int) -> None:
        if (key, kind, tick) not in self.observed:
            raise ValueError("Receipt fact lacks its actual same-tick operational event")

    def _required_facts(self, events: list[Json]) -> None:
        for event in events:
            key, kind, tick = event["order_id"], event["kind"], event["tick"]
            if kind in {"receipt_credited", "order_admitted"}:
                self._trigger(key, "inventory_claim_acquired", tick)
            if kind in {"receipt_putaway", "picked"}:
                self._trigger(key, "inventory_claim_released", tick)
            if kind != "receipt_admitted":
                continue
            view = event["receipt"]
            offer = self.inventory.offers[key]
            required = {
                "receipt:hu:" + offer["definition"]["hu_id"],
                "receipt:place:" + offer["slot_owner_id"],
                "receipt:place:" + view["buffer_owner_id"],
                "receipt:worker:" + view["actor_id"],
            }
            actual = {
                e["resource_id"]
                for e in events
                if e["order_id"] == key
                and e["tick"] == tick
                and e["kind"] == "receipt_resource_acquired"
            }
            if not required <= actual:
                raise ValueError("Receipt admission lacks actual finite resource acquisition")

    def _acquire(self, event: Json) -> None:
        claim, job = event["inventory_claim"], event["order_id"]
        key, ids = claim["claim_id"], claim["unit_ids"]
        if key in self.claims or claim["job_id"] != job or not ids or len(ids) != len(set(ids)):
            raise ValueError("Claim identity or selected units conflict")
        container = claim["container_id"]
        if any(self.inventory.locations[u][0] != container for u in ids):
            raise ValueError("Claim units are absent from their actual container")
        if claim["whole_hu"]:
            self._trigger(job, "receipt_credited", event["tick"])
            offer = self.inventory.offers[job]
            same(sorted(ids), sorted(u["unit_id"] for u in offer["units"]), "Incomplete HU claim")
            if key != "receipt:" + job or container != offer["definition"]["hu_id"]:
                raise ValueError("Receipt claim definition differs")
        else:
            self._trigger(job, "order_admitted", event["tick"])
            order = next(o for o in self.catalog["orders"] if o["order_id"] == job)
            same(
                sorted(ids),
                sorted(p["unit_id"] for p in order["carrier_placements"]),
                "Pick claim differs from exact requested units",
            )
            if key != "pick:" + job or container != order["source_hu"]:
                raise ValueError("Pick claim references the wrong physical source")
        for other in self.claims.values():
            if set(ids).intersection(other["unit_ids"]) or (
                container == other["container_id"] and (claim["whole_hu"] or other["whole_hu"])
            ):
                raise ValueError("Two claims promise the same inventory")
        self.claims[key] = claim
        self.generation += 1

    def _service_resources(self, events: list[Json]) -> None:
        expected = set[tuple[str, int, str]]()
        for event in events:
            operation = event["operation"]
            if (
                event["kind"] != "operation_started"
                or operation is None
                or operation["kind"] != "receipt_service"
            ):
                continue
            key = event["order_id"]
            port_id = self.inventory.offers[key]["port_id"]
            port = next(
                p for p in self.catalog["receipt_process"]["ports"] if p["port_id"] == port_id
            )
            if event["actor_id"] not in port["receiver_ids"]:
                raise ValueError("Receipt service starts with an ineligible receiver")
            expected.add((key, event["tick"], "receipt:port:" + port_id))
        actual = {
            (e["order_id"], e["tick"], e["resource_id"])
            for e in events
            if e["kind"] == "receipt_resource_acquired"
            and (e["resource_id"] or "").startswith("receipt:port:")
        }
        same(
            sorted(actual),
            sorted(expected),
            "Actual receipt service and finite port acquisition differ",
        )

    def _resource(self, event: Json) -> None:
        key, resource, kind = event["order_id"], event["resource_id"], event["kind"]
        offer = self.inventory.offers[key]
        port = next(
            p for p in self.catalog["receipt_process"]["ports"] if p["port_id"] == offer["port_id"]
        )
        allowed = {
            "receipt:hu:" + offer["definition"]["hu_id"],
            "receipt:port:" + port["port_id"],
            "receipt:place:" + offer["slot_owner_id"],
            *("receipt:place:" + b for b in port["buffer_ids"]),
            *("receipt:worker:" + a for a in port["receiver_ids"]),
        }
        if resource not in allowed:
            raise ValueError("Receipt event references an undeclared finite resource")
        if kind == "receipt_resource_acquired":
            if resource in self.resources:
                raise ValueError("Receipt resource acquired twice")
            if not resource.startswith("receipt:port:"):
                self._trigger(key, "receipt_admitted", event["tick"])
            self.resources[resource] = key
        elif kind == "receipt_resource_released":
            if self.resources.get(resource) != key:
                raise ValueError("Receipt resource released without actual ownership")
            trigger = "receipt_putaway"
            if resource.startswith("receipt:worker:"):
                trigger = "receipt_returned"
            elif resource.startswith("receipt:port:"):
                trigger = "receipt_credited"
            elif resource.removeprefix("receipt:place:") in port["buffer_ids"]:
                trigger = "receipt_buffer_picked"
            self._trigger(key, trigger, event["tick"])
            del self.resources[resource]
        else:
            raise ValueError("Resource payload requires an actual resource event")

    def check(self, state: Json, tick: int) -> None:
        same(
            state["inventory"]["claims"],
            [self.claims[k] for k in sorted(self.claims)],
            "Captured claims differ from the actual claim journal",
        )
        same(state["inventory"]["claim_generation"], self.generation, "Claim generation differs")
        resources = sorted((r, owner) for r, owner in state["leases"] if r.startswith("receipt:"))
        same(
            resources, sorted(self.resources.items()), "Captured receipt resource ownership differs"
        )
        self.check_claims()
        views = {r["receipt_id"]: r for r in state["receipts"]}
        if len(views) != len(state["receipts"]) or views.keys() != self.views.keys():
            raise ValueError("Captured receipt identities differ")
        for key, expected in self.views.items():
            paid = (
                0
                if expected["admitted_tick"] is None
                else (min(tick, expected["returned_tick"] or tick) - expected["admitted_tick"])
            )
            same(
                views[key],
                {**expected, "paid_exposure_ticks": paid},
                "Captured receipt state differs from actual transitions",
            )

    def check_claims(self) -> None:
        for claim in self.claims.values():
            if any(
                self.inventory.locations[u][0] != claim["container_id"] for u in claim["unit_ids"]
            ):
                raise ValueError("Claimed physical units moved before authorized release")
