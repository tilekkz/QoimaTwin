"""Authoritative state checks reject forged ancestry, material identity and location state."""

from dataclasses import replace

import pytest

from app.v3.stock_models import StockError
from tests.v3.test_stock_fixtures import ledger


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_unit",
        "replaced_token",
        "missing_material",
        "wrong_recipe",
        "source_owner",
        "changed_container_id",
        "sealed_carrier",
        "changed_owner_capacity",
        "equal_recipe_rating",
    ],
)
def test_invariant_checker_rejects_forged_state(corruption: str) -> None:
    state = ledger()
    if corruption == "missing_unit":
        del state._locations["U1"]
    elif corruption == "replaced_token":
        state._tokens["U1"] = replace(state._tokens["U1"], sku_id="invented")
    elif corruption == "missing_material":
        del state._containers["C2"]
    elif corruption == "wrong_recipe":
        item = state._containers["C2"]
        state._containers["C2"] = replace(item, recipe=replace(item.recipe, max_units=25))
    elif corruption == "source_owner":
        state._containers["HU1"] = replace(state._containers["HU1"], owner_id="bench")
    elif corruption == "changed_container_id":
        state._containers["C2"] = replace(state._containers["C2"], container_id="C1")
    elif corruption == "sealed_carrier":
        state._containers["C2"] = replace(state._containers["C2"], sealed_for="ORDER")
    elif corruption == "equal_recipe_rating":
        item = state._containers["C2"]
        changed_recipe = replace(item.recipe, max_gross_kg=10)  # type: ignore[arg-type]
        state._containers["C2"] = replace(item, recipe=changed_recipe)
    else:
        state._owners["bench"] = replace(state._owners["bench"], capacity=400)
    with pytest.raises(StockError):
        state.check_invariants()
