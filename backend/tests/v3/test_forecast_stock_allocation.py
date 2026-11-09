"""Handwritten finite-stock arithmetic for the shared, already-validated loop."""

from fractions import Fraction as F

from app.v3.outbound_stock_allocation import _allocate_verified_offers
from app.v3.outbound_stock_models import StockHU
from app.v3.workload_models import WorkloadJob


def test_three_originals_four_offers_retains_shortage_without_cloning() -> None:
    stock = tuple(
        StockHU(hu, "A", "PALLET", "lot-A", (hu + ":unit:0001",), 1, F(2), hu + "-slot", None, None)
        for hu in ("HU3", "HU1", "HU2")
    )
    offers = tuple(
        WorkloadJob(
            f"offer-{n}", "outbound", "A", "PALLET", "T-A", "OUT_E_B2B", 1, n * 7, None, None
        )
        for n in range(4)
    )
    rows = _allocate_verified_offers(offers, stock, ())
    assert tuple(row.offer for row in rows) == offers
    assert [row.hu.hu_id if row.hu else None for row in rows] == ["HU1", "HU2", "HU3", None]
    assert [row.status for row in rows] == ["original_bound"] * 3 + ["unallocated"]
    assert rows[-1].reason == "DECLARED_STOCK_EXHAUSTED"
    assert all(row.receipt_arrives_after_offer is None for row in rows)
    assert all(not row.operational_admission for row in rows)
    assert tuple(hu.hu_id for hu in stock) == ("HU3", "HU1", "HU2")
    assert _allocate_verified_offers(offers, stock, ()) == rows


def test_empty_offers_preserve_stock_without_allocations() -> None:
    assert _allocate_verified_offers((), (), ()) == ()
