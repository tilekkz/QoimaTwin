"""Transactional inventory ledger (ADR 0005).

Stock is integer quantities per `Holding = (sku_id, lot_id, location)`. A reservation is a claim on
on-hand stock at a pick face and never adds units. Every public mutation validates first and then
applies, so a rejected call leaves the ledger unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class LedgerError(ValueError):
    """A stock operation violates quantities, reservations or ownership."""


class LocKind(StrEnum):
    PICKFACE = "pickface"
    RESERVE_SLOT = "reserve_slot"
    RECEIVING = "receiving"
    INBOUND_VEHICLE = "inbound_vehicle"
    RESERVE_STAGING = "reserve_staging"
    TOTE = "tote"
    PACK_WIP = "pack_wip"
    PARCEL = "parcel"
    DISPATCHED = "dispatched"


@dataclass(frozen=True, slots=True, order=True)
class Location:
    kind: LocKind
    ref: str


@dataclass(frozen=True, slots=True, order=True)
class Holding:
    sku_id: str
    lot_id: str
    location: Location


@dataclass(frozen=True, slots=True)
class ReservationLine:
    holding: Holding
    quantity: int


def _positive(quantity: int, what: str) -> None:
    if quantity <= 0:
        raise LedgerError(f"{what}: quantity must be positive, got {quantity}")


class Ledger:
    def __init__(self) -> None:
        self._balances: dict[Holding, int] = {}
        self._reserved: dict[Holding, int] = {}
        self._order_claims: dict[str, dict[Holding, int]] = {}
        self._by_location: dict[Location, set[Holding]] = defaultdict(set)
        self._initial: dict[str, int] = defaultdict(int)
        self._accepted: dict[str, int] = defaultdict(int)

    # ----- creation -----
    def add_initial(self, sku_id: str, lot_id: str, location: Location, quantity: int) -> None:
        _positive(quantity, "initial stock")
        self._credit(Holding(sku_id, lot_id, location), quantity)
        self._initial[sku_id] += quantity

    def accept_receipt(self, sku_id: str, lot_id: str, location: Location, quantity: int) -> None:
        _positive(quantity, "receipt")
        self._credit(Holding(sku_id, lot_id, location), quantity)
        self._accepted[sku_id] += quantity

    # ----- queries -----
    def on_hand(self, holding: Holding) -> int:
        return self._balances.get(holding, 0)

    def reserved(self, holding: Holding) -> int:
        return self._reserved.get(holding, 0)

    def available(self, holding: Holding) -> int:
        return self.on_hand(holding) - self.reserved(holding)

    def quantity_at(self, sku_id: str, location: Location) -> int:
        return sum(
            self._balances[h] for h in self._by_location.get(location, ()) if h.sku_id == sku_id
        )

    def contents(self, location: Location) -> dict[str, int]:
        result: dict[str, int] = defaultdict(int)
        for holding in self._by_location.get(location, ()):
            result[holding.sku_id] += self._balances[holding]
        return dict(sorted(result.items()))

    def holdings_at(self, location: Location) -> list[tuple[Holding, int]]:
        return sorted((h, self._balances[h]) for h in self._by_location.get(location, ()))

    def physical_units(self, sku_id: str) -> int:
        return sum(q for h, q in self._balances.items() if h.sku_id == sku_id)

    def buckets(self, sku_id: str) -> dict[LocKind, int]:
        result = dict.fromkeys(LocKind, 0)
        for holding, quantity in self._balances.items():
            if holding.sku_id == sku_id:
                result[holding.location.kind] += quantity
        return result

    def skus(self) -> list[str]:
        return sorted(set(self._initial) | set(self._accepted) | {h.sku_id for h in self._balances})

    def check_conservation(self, skus: Iterable[str] | None = None) -> list[str]:
        """Return violations of `initial + accepted = physical units` and reservation bounds."""
        issues: list[str] = []
        for sku in sorted(skus) if skus is not None else self.skus():
            expected = self._initial.get(sku, 0) + self._accepted.get(sku, 0)
            found = self.physical_units(sku)
            if expected != found:
                issues.append(f"{sku}: expected {expected} units, found {found}")
        for holding, claim in sorted(self._reserved.items()):
            if not 0 <= claim <= self.on_hand(holding):
                issues.append(
                    f"{holding}: reserved {claim} exceeds on hand {self.on_hand(holding)}"
                )
        for holding, quantity in self._balances.items():
            if quantity <= 0:
                issues.append(f"{holding}: non-positive balance {quantity}")
        return issues

    # ----- reservations and picks -----
    def try_reserve(self, order_id: str, lines: Iterable[ReservationLine]) -> bool:
        """Reserve all lines for an order, or nothing. Returns False on any shortage."""
        if order_id in self._order_claims:
            raise LedgerError(f"order {order_id} already holds a reservation")
        wanted: dict[Holding, int] = defaultdict(int)
        for line in lines:
            _positive(line.quantity, f"reservation of {order_id}")
            if line.holding.location.kind is not LocKind.PICKFACE:
                raise LedgerError(f"{order_id}: reservations are only allowed on pick faces")
            wanted[line.holding] += line.quantity
        if any(self.available(h) < q for h, q in wanted.items()):
            return False
        for holding, quantity in wanted.items():
            self._reserved[holding] = self.reserved(holding) + quantity
        self._order_claims[order_id] = dict(wanted)
        return True

    def pick(self, order_id: str, holding: Holding, quantity: int, destination: Location) -> None:
        """Move reserved units from a pick face into `destination` and consume the claim."""
        _positive(quantity, f"pick of {order_id}")
        claims = self._order_claims.get(order_id, {})
        if claims.get(holding, 0) < quantity:
            raise LedgerError(f"{order_id} has no reservation of {quantity} on {holding}")
        self._debit(holding, quantity)
        self._credit(Holding(holding.sku_id, holding.lot_id, destination), quantity)
        claims[holding] -= quantity
        self._reserved[holding] -= quantity
        if self._reserved[holding] == 0:
            del self._reserved[holding]
        if claims[holding] == 0:
            del claims[holding]
        if not claims:
            del self._order_claims[order_id]

    def release_order(self, order_id: str) -> None:
        """Drop an order's unpicked claims (used at run cut-off; never moves stock)."""
        for holding, quantity in self._order_claims.pop(order_id, {}).items():
            self._reserved[holding] -= quantity
            if self._reserved[holding] == 0:
                del self._reserved[holding]

    # ----- movements -----
    def transfer_location(
        self, source: Location, destination: Location
    ) -> list[tuple[Holding, int]]:
        """Move every holding at `source` to `destination`, keeping SKU and lot identity."""
        moved = self.holdings_at(source)
        for holding, _ in moved:
            if self.reserved(holding):
                raise LedgerError(f"{holding} is reserved and cannot move as a whole")
        for holding, quantity in moved:
            self._debit(holding, quantity)
            self._credit(Holding(holding.sku_id, holding.lot_id, destination), quantity)
        return moved

    # ----- internals -----
    def _credit(self, holding: Holding, quantity: int) -> None:
        self._balances[holding] = self._balances.get(holding, 0) + quantity
        self._by_location[holding.location].add(holding)

    def _debit(self, holding: Holding, quantity: int) -> None:
        balance = self._balances.get(holding, 0)
        if balance < quantity:
            raise LedgerError(f"{holding} holds {balance}, cannot remove {quantity}")
        if balance == quantity:
            del self._balances[holding]
            self._by_location[holding.location].discard(holding)
            if not self._by_location[holding.location]:
                del self._by_location[holding.location]
        else:
            self._balances[holding] = balance - quantity
