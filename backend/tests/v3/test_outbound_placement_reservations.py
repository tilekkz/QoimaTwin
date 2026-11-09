"""Storage reservations require static compatibility without claiming receipt handling."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.outbound_placement_feasibility import receipt_slot_reasons
from app.v3.outbound_placement_source import source_bundle
from app.v3.outbound_stock_models import StockHU


def test_receipt_overweight_slot_is_not_only_a_module_question() -> None:
    bundle = source_bundle()
    hu = StockHU("future", "DEMO_113", "STANDARD_CARTON", "lot", (), 24, F(16), None, "receipt", 0)
    assert "RECEIPT_SLOT_PAYLOAD" in receipt_slot_reasons(bundle, hu, "v3:slot:FLEX_W:003:L1:B1")


def test_receipt_shape_and_storage_family_remain_source_bound() -> None:
    bundle = source_bundle()
    hu = StockHU(
        "future", "DEMO_113", "STANDARD_CARTON", "lot", (), 24, F("6.35"), None, "receipt", 0
    )
    assert receipt_slot_reasons(bundle, hu, "v3:slot:FLEX_W:003:L1:B1") == ()
    bulky = replace(hu, archetype_id="PALLET_LOAD", gross_mass_kg=F(455))
    assert receipt_slot_reasons(bundle, bulky, "v3:slot:FLEX_W:003:L1:B1")
