"""Apply public stock/reservation records without depending on the simulation engine."""

from typing import Any


class InventoryReplay:
    def __init__(self, ledger: dict[str, Any]) -> None:
        self.balances = {tuple(row[:-1]): row[-1] for row in ledger["balances"]}
        self.reserved = {tuple(row[:-1]): row[-1] for row in ledger["reservations"]}
        self.claims = {tuple(row[:-1]): row[-1] for row in ledger["claims"]}
        self.accepted = dict(ledger["accepted"])

    def apply(self, event: dict[str, Any]) -> None:
        p, kind = event["payload"], event["kind"]
        if kind == "stock_transferred":
            source, target = p["from"], p["to"]
            prefix = (p["sku_id"], p["lot_id"])
            if source["kind"] != "external":
                _add(self.balances, (*prefix, source["kind"], source["ref"]), -p["quantity"])
            _add(self.balances, (*prefix, target["kind"], target["ref"]), p["quantity"])
        elif kind in {"stock_reserved", "sku_picked"}:
            key = (p["sku_id"], p["lot_id"], "pickface", p["slot_id"])
            amount = p["quantity"] * (1 if kind == "stock_reserved" else -1)
            _add(self.reserved, key, amount)
            _add(self.claims, (p["order_id"], *key), amount)
        elif kind == "receipt_accepted":
            self.accepted[p["sku_id"]] = self.accepted.get(p["sku_id"], 0) + p["quantity"]

    def write(self, state: dict[str, Any]) -> None:
        state["ledger"] = {
            "balances": [[*key, value] for key, value in sorted(self.balances.items())],
            "reservations": [[*key, value] for key, value in sorted(self.reserved.items())],
            "claims": [[*key, value] for key, value in sorted(self.claims.items())],
            "accepted": [[key, value] for key, value in sorted(self.accepted.items())],
        }


def _add(values: dict[tuple[Any, ...], int], key: tuple[Any, ...], amount: int) -> None:
    quantity = values.get(key, 0) + amount
    if quantity < 0:
        raise ValueError(f"replay stock underflow at {key}")
    if quantity:
        values[key] = quantity
    else:
        values.pop(key, None)
