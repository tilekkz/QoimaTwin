"""PDF p8 / ADR0005: failed reservations/picks are atomic, stock never appears or disappears."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.inventory.ledger import Holding, Ledger, LedgerError, Location, LocKind, ReservationLine

pytestmark = pytest.mark.property
FACES = tuple(Holding(f"SKU{i}", f"LOT{i}", Location(LocKind.PICKFACE, f"S{i}")) for i in range(3))
type Command = tuple[str, int, list[tuple[int, int]]]
COMMANDS = st.lists(
    st.tuples(
        st.sampled_from(("reserve", "pick", "release")),
        st.integers(0, 3),
        st.lists(st.tuples(st.integers(0, 2), st.integers(0, 5)), min_size=1, max_size=4),
    ),
    min_size=1,
    max_size=60,
)


@dataclass
class StockModel:
    stock: list[int]
    claims: dict[int, Counter[int]] = field(default_factory=dict)
    picked: dict[int, Counter[int]] = field(default_factory=dict)

    def reserve(self, ledger: Ledger, order: int, lines: list[tuple[int, int]]) -> None:
        request = [ReservationLine(FACES[index], quantity) for index, quantity in lines]
        if order in self.claims or any(quantity <= 0 for _, quantity in lines):
            with pytest.raises(LedgerError):
                ledger.try_reserve(str(order), request)
            return
        wanted: Counter[int] = Counter()
        for index, quantity in lines:
            wanted[index] += quantity
        available = [self.stock[i] - sum(c[i] for c in self.claims.values()) for i in range(3)]
        enough = all(quantity <= available[i] for i, quantity in wanted.items())
        assert ledger.try_reserve(str(order), request) is enough
        if enough:
            self.claims[order] = wanted

    def pick(self, ledger: Ledger, order: int, index: int, quantity: int) -> None:
        tote = Location(LocKind.TOTE, f"T{order}")
        if quantity <= 0 or self.claims.get(order, Counter())[index] < quantity:
            with pytest.raises(LedgerError):
                ledger.pick(str(order), FACES[index], quantity, tote)
            return
        ledger.pick(str(order), FACES[index], quantity, tote)
        self.stock[index] -= quantity
        self.claims[order][index] -= quantity
        self.picked.setdefault(order, Counter())[index] += quantity
        if not any(self.claims[order].values()):
            del self.claims[order]

    def verify(self, ledger: Ledger, initial: list[int]) -> None:
        assert ledger.check_conservation() == []
        for i, holding in enumerate(FACES):
            reserved = sum(claim[i] for claim in self.claims.values())
            assert ledger.on_hand(holding) == self.stock[i]
            assert ledger.reserved(holding) == reserved
            assert ledger.available(holding) == self.stock[i] - reserved >= 0
            assert ledger.physical_units(holding.sku_id) == initial[i]
            for order in range(4):
                tote = Location(LocKind.TOTE, f"T{order}")
                assert (
                    ledger.quantity_at(holding.sku_id, tote) == self.picked.get(order, Counter())[i]
                )


@settings(max_examples=100, deadline=None)
@given(initial=st.lists(st.integers(1, 8), min_size=3, max_size=3), commands=COMMANDS)
def test_random_reserve_pick_release_matches_independent_model(
    initial: list[int], commands: list[Command]
) -> None:
    ledger = Ledger()
    for holding, quantity in zip(FACES, initial, strict=True):
        ledger.add_initial(holding.sku_id, holding.lot_id, holding.location, quantity)
    model = StockModel(initial.copy())
    for operation, order, lines in commands:
        if operation == "reserve":
            model.reserve(ledger, order, lines)
        elif operation == "pick":
            model.pick(ledger, order, *lines[0])
        else:
            ledger.release_order(str(order))
            model.claims.pop(order, None)
        model.verify(ledger, initial)
