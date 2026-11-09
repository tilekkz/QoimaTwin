"""Inventory reconstruction from actual atomic deltas, never from future receipt declarations."""

from fractions import Fraction

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_wire import record
from app.v3.flow_run_stock import StockAudit
from app.v3.interface import Json


def same(left: object, right: object, message: str) -> None:
    if canonical_bytes(left) != canonical_bytes(right):
        raise ValueError(message)


class InventoryJournal:
    def __init__(self, catalog: Json) -> None:
        self.catalog = catalog
        self.offers = {r["definition"]["receipt_id"]: r for r in catalog["declared_receipts"]}
        self.units = {u["unit_id"]: u for u in catalog["initial_units"]}
        self.recipes = {c["container_id"]: c["recipe_id"] for c in catalog["initial_containers"]}
        self.containers = {
            c["container_id"]: {
                "container_id": c["container_id"],
                "owner_id": c["initial_owner_id"],
                "sealed_for": c["initial_sealed_for"],
            }
            for c in catalog["initial_containers"]
        }
        self.locations = {k: (u["origin_hu"], None) for k, u in self.units.items()}
        self.registered: set[str] = set()
        self.revision = 0
        self.audit = self._audit()

    def _audit(self) -> StockAudit:
        return StockAudit(
            {
                **self.catalog,
                "units": list(self.units.values()),
                "containers": [
                    {"container_id": key, "recipe_id": value} for key, value in self.recipes.items()
                ],
            }
        )

    def contents(self, identity: str) -> Json:
        units = [
            {"unit_id": key, "position": position}
            for key, (container, position) in sorted(self.locations.items())
            if container == identity
        ]
        gross = self.audit.tares[identity] + sum(
            (sum(self.audit.units[u["unit_id"]][1:], Fraction(0)) for u in units), Fraction(0)
        )
        return {
            "container": self.containers[identity],
            "units": units,
            "gross_mass_kg": record(gross),
        }

    def apply(self, event: Json) -> None:
        delta = event["delta"]
        if delta is None:
            return
        if type(delta["revision"]) is not int or delta["revision"] != self.revision + 1:
            raise ValueError("Receipt inventory revision is not contiguous")
        if delta["delta_type"] == "receipt_creation":
            self._create(event)
        else:
            if delta["receipt"] is not None or delta["created_tokens"]:
                raise ValueError("Ordinary stock delta cannot create receipt tokens")
            for before in delta["before"]:
                same(
                    before,
                    self.contents(before["container"]["container_id"]),
                    "Delta before-state differs from actual inventory",
                )
            if {r["container"]["container_id"] for r in delta["before"]} != {
                r["container"]["container_id"] for r in delta["after"]
            }:
                raise ValueError("Ordinary delta changed physical container identities")
            self.audit.delta(delta)
        locations = self.audit.locations(delta["after"])
        self.locations.update(locations)
        for after in delta["after"]:
            container = after["container"]
            self.containers[container["container_id"]] = container
        self.revision += 1

    def _create(self, event: Json) -> None:
        delta, key = event["delta"], event["order_id"]
        if key in self.registered or key not in self.offers:
            raise ValueError("Unknown or duplicate receipt creation")
        offer = self.offers[key]
        definition, hu = offer["definition"], offer["definition"]["hu_id"]
        if event["kind"] != "receipt_credited" or delta["operation"] != "receive_hu":
            raise ValueError("Receipt creation must be an actual service credit")
        same(delta["receipt"], definition, "Receipt creation definition differs")
        same(delta["created_tokens"], offer["units"], "Created tokens differ from declaration")
        same(
            delta["unit_ids"],
            [u["unit_id"] for u in offer["units"]],
            "Creation unit identities differ",
        )
        if delta["before"] or len(delta["after"]) != 1 or hu in self.containers:
            raise ValueError("Receipt creation requires a new single physical wrapper")
        container = delta["after"][0]["container"]
        if container != {
            "container_id": hu,
            "owner_id": "actor:" + str(event["actor_id"]),
            "sealed_for": None,
        }:
            raise ValueError("Receipt credit is not in actual receiver custody")
        if any(u["unit_id"] in self.units for u in offer["units"]):
            raise ValueError("Receipt unit collides with existing inventory")
        self.units.update((u["unit_id"], u) for u in offer["units"])
        self.recipes[hu] = offer["container_recipe_id"]
        self.registered.add(key)
        self.audit = self._audit()
        actual = self.audit.locations(delta["after"])
        same(
            actual,
            {u["unit_id"]: (hu, None) for u in offer["units"]},
            "New receipt contents differ from complete source recipe",
        )

    def check(self, state: Json) -> None:
        expected = {
            "revision": self.revision,
            "containers": [self.containers[k] for k in sorted(self.containers)],
            "locations": [
                {"unit_id": key, "container_id": owner, "position": position}
                for key, (owner, position) in sorted(self.locations.items())
            ],
        }
        same(state["stock"], expected, "Captured stock differs from actual creation/move journal")
        same(
            state["inventory"]["registered_receipt_ids"],
            sorted(self.registered),
            "Captured registered receipts differ from actual credits",
        )
        self.audit.check(state)
