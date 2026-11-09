"""Repeated full checks recompute recipe mass once per pass while preserving state."""

from fractions import Fraction

import pytest

from app.v3.stock_models import UnitRecipe
from tests.v3.test_stock_fixtures import ledger


@pytest.mark.parametrize("operation", ["check", "contents", "balance"])
def test_each_complete_scan_computes_shared_recipe_gross_once(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    state = ledger()
    before = state.inventory_snapshot()
    calls: list[UnitRecipe] = []

    def gross(recipe: UnitRecipe) -> Fraction:
        calls.append(recipe)
        return recipe.contents_mass_kg + recipe.primary_tare_kg

    monkeypatch.setattr(UnitRecipe, "gross_mass_kg", property(gross))
    for _ in range(2):
        calls.clear()
        if operation == "check":
            state.check_invariants()
        elif operation == "contents":
            assert state.contents("HU1").gross_mass_kg == Fraction(".94")
        else:
            totals = state.balance()
            assert totals.contents_mass_kg == Fraction(".72")
            assert totals.primary_tare_kg == Fraction(".12")
            assert totals.gross_mass_kg == Fraction("1.39")
        assert len(calls) == 1  # Twenty-four units share one declared recipe.
        assert state.inventory_snapshot() == before
