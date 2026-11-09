"""Adversarial physical recipes and initial identities cannot silently alter stock."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container, Placement, StockError, StockOwner
from tests.v3.test_stock_fixtures import ledger, placements, recipe, source_seed_fixture


@pytest.mark.parametrize("corruption", ["ordinal", "sku", "quantity", "recipe_id", "source_owner"])
def test_invalid_initial_source_or_recipe_identity_is_rejected(corruption: str) -> None:
    seed = source_seed_fixture()
    materials: tuple[Container, ...] = (Container("C", recipe(), "bench"),)
    if corruption == "ordinal":
        seed = replace(seed, units=(replace(seed.units[0], ordinal=2), *seed.units[1:]))
    elif corruption == "sku":
        seed = replace(seed, units=(replace(seed.units[0], sku_id="OTHER"), *seed.units[1:]))
    elif corruption == "quantity":
        seed = replace(seed, units=seed.units[:-1])
    elif corruption == "recipe_id":
        materials += (Container("C2", replace(recipe(), tare_kg=F(1)), "bench"),)
    else:
        seed = replace(seed, containers=(replace(seed.containers[0], owner_id="bench"),))
    with pytest.raises(StockError):
        StockLedger(seed, owners=(StockOwner("bench", "workstation", 4),), materials=materials)


@pytest.mark.parametrize(
    "changes",
    [
        {"inner": None},
        {"inner": (F(2), F(1), F(1))},
        {"tare_kg": F(-1)},
        {"tare_kg": 0.2},
        {"max_units": True},
        {"kind": "invented"},
        {"provenance": ""},
        {"clearance_m": F(".4")},
        {"allowed_archetypes": ()},
    ],
)
def test_invalid_material_recipe_fails_before_state_exists(changes: dict[str, object]) -> None:
    material = Container("C", replace(recipe(), **changes), "bench")  # type: ignore[arg-type]
    with pytest.raises(StockError):
        StockLedger(
            source_seed_fixture(),
            owners=(StockOwner("bench", "material", 1),),
            materials=(material,),
        )


@pytest.mark.parametrize(
    "position",
    [
        (F(".7400000000000000000001"), F(0), F(0)),  # .8-.06 exact boundary + 1e-22
        (F(0), F(".000001"), F(0)),
        (F(-1), F(0), F(0)),
    ],
)
def test_geometry_rejects_tolerance_overflow_and_unsupported_stack(
    position: tuple[F, F, F],
) -> None:
    state = ledger()
    before = state.snapshot()
    with pytest.raises(StockError):
        state.pick("bad", 0, "HU1", "C1", (Placement("U1", position),))
    assert state.snapshot() == before


def test_exact_touching_floor_units_are_allowed_with_no_duplicate_primary_packaging() -> None:
    state = ledger()
    items = (
        Placement("U1", (F(".68"), F(0), F(".76"))),
        Placement("U2", (F(".74"), F(0), F(".76"))),
    )
    state.pick("touch", 0, "HU1", "C1", items)
    assert state.contents("C1").gross_mass_kg == F(".27")
    assert state.balance().primary_tare_kg == F(".12")


def test_sealed_package_empty_disposal_unknown_owner_and_wrong_class_cannot_bypass_ledger() -> None:
    state = ledger()
    state.pick("p", 0, "HU1", "C1", placements(1))
    state.pack("pack", 1, "C1", "P1", placements(1), order_id="O")
    before = state.snapshot()
    with pytest.raises(StockError):
        state.transfer("unseal", 2, "P1", "C2", placements(1))
    with pytest.raises(StockError):
        state.dispose_empty_wrapper("trash-stock", 2, "HU1", "waste")
    with pytest.raises(StockError):
        state.relocate("unknown", 2, "C1", "unknown")
    with pytest.raises(StockError):
        state.relocate("slot", 2, "C1", "slot")
    assert state.snapshot() == before


def test_forbidden_cargo_kind_rejects_small_unit_even_when_dimensions_fit() -> None:
    material = Container("C", replace(recipe(), allowed_archetypes=("STANDARD_CARTON",)), "bench")
    state = StockLedger(
        source_seed_fixture(), owners=(StockOwner("bench", "material", 1),), materials=(material,)
    )
    before = state.snapshot()
    with pytest.raises(StockError, match="cargo kind forbidden"):
        state.pick("bad", 0, "HU1", "C", placements(1))
    assert state.snapshot() == before
