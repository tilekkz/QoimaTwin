"""Receipt recipe authority must retain the original immutable source, not just live stock."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_models import StockError
from tests.v3.test_stock_fixtures import ledger


@pytest.mark.parametrize("authority", ["wrapper", "sku"])
def test_initial_recipe_authority_cannot_change_behind_unchanged_live_stock(
    authority: str,
) -> None:
    state = ledger()
    before = state.snapshot()
    if authority == "wrapper":
        original = state._initial_containers["HU1"]
        altered = replace(original.recipe, outer=(F(".64"), F(".24"), F(".24")))
        state._initial_containers["HU1"] = replace(original, recipe=altered)
    else:
        original_token = state._initial_tokens["U1"]
        state._initial_tokens["U1"] = replace(original_token, sku_id="UNDECLARED")
    assert state.snapshot() == before
    with pytest.raises(StockError):
        state.check_invariants()
