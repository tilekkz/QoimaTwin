"""Exact scalar stock checks reuse immutable catalog values once per validated run."""

from collections import Counter
from fractions import Fraction
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_wire import record


def exact(value: dict[str, Any]) -> Fraction:
    n, d = value["numerator"], value["denominator"]
    if type(n) is not int or type(d) is not int or d <= 0:
        raise ValueError("Catalog mass requires exact rational integers")
    result = Fraction(n, d)
    if result < 0 or (result.numerator, result.denominator) != (n, d):
        raise ValueError("Catalog mass must be nonnegative and canonically reduced")
    return result


class StockAudit:
    def __init__(self, catalog: dict[str, Any]) -> None:
        self.owners = {o["owner_id"]: (o["kind"], o["capacity"]) for o in catalog["owners"]}
        recipes = {r["recipe_id"]: exact(r["tare_kg"]) for r in catalog["container_recipes"]}
        self.tares = {c["container_id"]: recipes[c["recipe_id"]] for c in catalog["containers"]}
        self.units = {
            u["unit_id"]: (
                u["sku_id"],
                exact(u["recipe"]["contents_mass_kg"]),
                exact(u["recipe"]["primary_tare_kg"]),
            )
            for u in catalog["units"]
        }
        if any(type(capacity) is not int or capacity <= 0 for _, capacity in self.owners.values()):
            raise ValueError("Catalog owner capacity must be a positive integer")

    def check(self, state: dict[str, Any]) -> None:
        stock = state["stock"]
        owners = {c["container_id"]: c["owner_id"] for c in stock["containers"]}
        counts = Counter(owners.values())
        if any(count > self.owners[key][1] for key, count in counts.items()):
            raise ValueError("Captured physical owner capacity exceeded")
        totals: Counter[str] = Counter()
        onsite: Counter[str] = Counter()
        shipped: Counter[str] = Counter()
        masses = {"onsite": Fraction(0), "shipped": Fraction(0), "disposal": Fraction(0)}
        for key, owner in owners.items():
            masses[self.bucket(owner)] += self.tares[key]
        for location in stock["locations"]:
            sku, net, primary = self.units[location["unit_id"]]
            bucket = self.bucket(owners[location["container_id"]])
            if bucket == "disposal":
                raise ValueError("Goods units cannot be disposed with empty packaging")
            totals[sku] += 1
            (shipped if bucket == "shipped" else onsite)[sku] += 1
            masses[bucket] += net + primary
        expected = {
            "units_by_sku": sorted(totals.items()),
            "onsite_units_by_sku": sorted(onsite.items()),
            "shipped_units_by_sku": sorted(shipped.items()),
            "contents_mass_kg": sum((u[1] for u in self.units.values()), Fraction(0)),
            "primary_tare_kg": sum((u[2] for u in self.units.values()), Fraction(0)),
            "container_tare_kg": sum(self.tares.values(), Fraction(0)),
            "onsite_mass_kg": masses["onsite"],
            "shipped_mass_kg": masses["shipped"],
            "disposed_mass_kg": masses["disposal"],
        }
        if record(expected) != state["balance"]:
            raise ValueError("Captured SKU or scalar mass balance differs from physical contents")

    def bucket(self, owner: str) -> str:
        kind = self.owners[owner][0]
        return kind if kind in {"shipped", "disposal"} else "onsite"

    def delta(self, value: dict[str, Any]) -> None:
        ids = value["unit_ids"]
        if len(ids) != len(set(ids)) or any(key not in self.units for key in ids):
            raise ValueError("Delta unit identities must be unique known units")
        before, after = self.locations(value["before"]), self.locations(value["after"])
        if before.keys() != after.keys():
            raise ValueError("Delta before/after unit conservation mismatch")
        moved = {key for key in before if before[key] != after[key]}
        expected = moved if value["operation"] in {"pick", "pack", "transfer"} else set(before)
        if set(ids) != expected:
            raise ValueError("Delta selected units differ from its actual physical mutation")

    def locations(self, rows: list[dict[str, Any]]) -> dict[str, tuple[str, Any]]:
        result: dict[str, tuple[str, Any]] = {}
        containers = set[str]()
        for row in rows:
            key = row["container"]["container_id"]
            if key not in self.tares or key in containers:
                raise ValueError("Delta physical container identity mismatch")
            containers.add(key)
            gross = self.tares[key]
            for unit in row["units"]:
                identity = unit["unit_id"]
                if identity not in self.units or identity in result:
                    raise ValueError("Delta content repeats or invents a unit")
                result[identity] = key, unit["position"]
                gross += self.units[identity][1] + self.units[identity][2]
            if exact(row["gross_mass_kg"]) != gross:
                raise ValueError("Delta container gross mass differs from contents plus tare")
        return result


def check_metric_counts(run: dict[str, Any]) -> None:
    initial = run["checkpoints"][0]["state"]["balance"]["shipped_units_by_sku"]
    baseline = sum(count for _, count in initial)
    for key in ("at_horizon", "at_end"):
        state = run[key]["state"]
        arrived = sum(order["status"] != "unreleased" for order in state["orders"])
        completed = sum(order["shipped_tick"] is not None for order in state["orders"])
        expected = {
            "arrived_orders": arrived,
            "completed_orders": completed,
            "backlog_orders": arrived - completed,
            "completed_units": sum(count for _, count in state["balance"]["shipped_units_by_sku"])
            - baseline,
        }
        actual = {k: run["metrics"][key].get(k) for k in expected}
        if canonical_bytes(actual) != canonical_bytes(expected):
            raise ValueError(
                "Published business counts differ from captured conserved stock/orders"
            )
    if run["metrics"]["backlog_at_horizon"] != run["metrics"]["at_horizon"]["backlog_orders"]:
        raise ValueError("Published horizon backlog differs from its observation")
