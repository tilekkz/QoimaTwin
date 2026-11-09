"""Repository-contained C02 authority; stock registration grants no physical execution."""

from fractions import Fraction as F
from pathlib import Path

from app.v3.inputs import load_v3_bundle
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockOwner
from app.v3.stock_receipts import ReceiptDefinition
from app.v3.stock_source import source_seed


def test_pinned_source_receipt_preserves_all_530_initial_hus_and_exact_recipe() -> None:
    bundle = load_v3_bundle(Path("data/v3-proposal"))
    seed = source_seed(bundle)
    state = StockLedger(
        seed, owners=(StockOwner("worker:R01", "worker", 1), StockOwner("shipped", "shipped", 1))
    )
    initial = {container.container_id: container for container in seed.containers}
    new = ReceiptDefinition("R1", "received:SMALL:1", "DEMO_001", "received:lot:1", 24)
    delta = state.receive_hu("receive", 0, new, "worker:R01")
    assert len(state.snapshot().locations) == 12280
    assert state.balance().gross_mass_kg == F("9404.79")
    assert state.contents(new.hu_id).container.recipe is initial["v3:HU:initial:DEMO_001:01"].recipe
    assert len(delta.created_tokens) == 24
    state.ship_whole_hu("ship", 1, new.hu_id, "shipped")
    assert state.balance().onsite_mass_kg == F("9403.85")
    assert state.balance().shipped_mass_kg == F(".94")
    assert sum(q for _, q in state.balance().onsite_units_by_sku) == 12256
    current = {container.container_id: container for container in state.snapshot().containers}
    assert len(initial) == 530 and len(current) == 531
    assert all(current[key] is value for key, value in initial.items())
    state.check_invariants()
