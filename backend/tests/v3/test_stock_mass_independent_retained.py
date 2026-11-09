"""Public ledger reads cannot reuse earlier recipe validation or skip geometry scans."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockError
from tests.v3.test_stock_fixtures import ledger, placements, source_seed_fixture


def _integer_recipe_ledger() -> StockLedger:
    seed = source_seed_fixture()
    unit = replace(seed.units[0].recipe, contents_mass_kg=F(1), primary_tare_kg=F(0))
    wrapper = replace(seed.containers[0].recipe, max_gross_kg=F("24.1"))
    return StockLedger(
        replace(
            seed,
            units=tuple(replace(token, recipe=unit) for token in seed.units),
            containers=(replace(seed.containers[0], recipe=wrapper),),
        )
    )


@pytest.mark.parametrize("operation", ["check", "contents", "balance"])
def test_retained_numeric_alias_after_success_is_revalidated_in_every_public_path(
    operation: str,
) -> None:
    state = _integer_recipe_ledger()
    exposed = state.contents("HU1").units[0].token.recipe
    state.check_invariants()
    assert state.balance().gross_mass_kg == F("24.1")
    object.__setattr__(exposed, "contents_mass_kg", True)
    assert exposed.contents_mass_kg == F(1) and state.revision == 0
    with pytest.raises(StockError):
        if operation == "check":
            state.check_invariants()
        elif operation == "contents":
            state.contents("HU1")
        else:
            state.balance()


def test_valid_recipe_geometry_change_without_revision_still_hits_full_placement_scan() -> None:
    state = ledger()
    state.pick("pick", 0, "HU1", "C1", placements(1))
    state.check_invariants()
    exposed = state.contents("C1").units[0].token.recipe
    object.__setattr__(exposed, "dimensions", (F(".9"), F(".04"), F(".04")))
    assert state.revision == 1
    with pytest.raises(StockError, match="usable bounds"):
        state.check_invariants()
