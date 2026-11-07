"""Pinned C02 and baseline arithmetic, not values learned from ledger output."""

from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.inputs import load_v3_bundle
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container, Placement, StockError, StockOwner, StockSeed
from app.v3.stock_source import source_seed
from tests.v3.test_stock_fixtures import recipe


@pytest.fixture(scope="module")
def initial_seed() -> StockSeed:
    return source_seed(load_v3_bundle(Path("data/v3-proposal")))


@pytest.fixture
def source_ledger(initial_seed: StockSeed) -> StockLedger:
    return StockLedger(
        initial_seed,
        owners=(StockOwner("bench", "workstation", 1),),
        materials=(Container("T1", recipe(), "bench"),),
    )


def test_all_source_units_and_individual_primary_and_hu_tare(source_ledger: StockLedger) -> None:
    state = source_ledger.snapshot()
    balance = source_ledger.balance()
    assert len(state.containers) == 531  # 530 original + one explicitly declared test material
    assert len(state.locations) == 12256
    assert len(balance.units_by_sku) == 200
    assert balance.contents_mass_kg == F("8342.4")
    assert balance.primary_tare_kg == F("443.2")
    assert balance.container_tare_kg == F("618.45")  # original618.25 + test carrier .20
    assert balance.gross_mass_kg == F("9404.05")
    source_ledger.check_invariants()


def test_actual_small_source_pick_retains_one_parent_wrapper(source_ledger: StockLedger) -> None:
    hu = "v3:HU:initial:DEMO_001:01"
    unit_id = f"{hu}:unit:0001"
    result = source_ledger.pick("actual", 0, hu, "T1", (Placement(unit_id, (F(0), F(0), F(0))),))
    assert result.before[0].gross_mass_kg == F(".94")
    assert result.after[0].gross_mass_kg == F(".905")  # 23*.035 + .10
    assert result.after[1].gross_mass_kg == F(".235")
    token = result.after[1].units[0].token
    assert (token.origin_hu, token.sku_id, token.lot_id, token.ordinal) == (
        hu,
        "DEMO_001",
        "v3:lot:initial:DEMO_001",
        1,
    )


def test_standard_source_units_cannot_be_forced_into_generic_carrier(
    source_ledger: StockLedger,
) -> None:
    wrapper = next(
        c
        for c in source_ledger.snapshot().containers
        if c.recipe.allowed_archetypes == ("STANDARD_CARTON",)
    )
    contents = source_ledger.contents(wrapper.container_id)
    unit_id = contents.units[0].token.unit_id
    before = source_ledger.snapshot()
    with pytest.raises(StockError, match="unsupported unit picking class"):
        source_ledger.pick(
            "standard",
            before.revision,
            wrapper.container_id,
            "T1",
            (Placement(unit_id, (F(0), F(0), F(0))),),
        )
    assert source_ledger.snapshot() == before
