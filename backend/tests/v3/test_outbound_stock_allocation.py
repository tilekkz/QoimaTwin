"""Each complete HU funds at most one offer; future receipts never become stock."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.outbound_stock_allocation import allocate_offers, declared_receipts
from app.v3.workload_materialize import materialize_workload
from tests.v3.test_outbound_stock_fixtures import initial, workload


def test_original_then_declared_receipts_then_visible_shortage() -> None:
    timed = workload()
    original = initial()
    incoming = declared_receipts(timed)
    rows = allocate_offers(timed, original, incoming)
    assert tuple(r.offer for r in rows) == tuple(j for j in timed.jobs if j.direction == "outbound")
    assert [r.status for r in rows] == [
        "original_bound",
        "original_bound",
        "receipt_dependency",
        "receipt_dependency",
        "unallocated",
        "unallocated",
    ]
    assert [r.reason for r in rows[-2:]] == ["DECLARED_STOCK_EXHAUSTED"] * 2
    selected = [r.hu for r in rows if r.hu is not None]
    assert len({h.hu_id for h in selected}) == len(selected) == 4
    assert sum(h.quantity_units for h in selected) == 96
    assert sum((h.gross_mass_kg for h in selected), F(0)) == F("3.76")
    assert original == initial() and timed == workload()


def test_later_receipt_is_a_dependency_without_rewriting_outbound_arrival() -> None:
    timed = workload(2, 12)
    rows = allocate_offers(timed, initial(), declared_receipts(timed))
    future = [r for r in rows if r.status == "receipt_dependency"]
    assert len(future) == 2
    late = next(r for r in future if r.hu is not None and r.hu.sku_id == "B")
    assert late.hu is not None and late.hu.receipt_arrival_tick == 6
    assert late.offer.arrival_tick < 6 and late.receipt_arrives_after_offer is True
    assert late.hu.initial_owner_id is None
    assert late.hu.receipt_job_id in {j.job_id for j in timed.jobs if j.direction == "inbound"}
    assert all(not r.operational_admission for r in rows)


def test_zero_work_retains_empty_output_and_no_stock_creation() -> None:
    timed = workload(0, 0)
    assert declared_receipts(timed) == ()
    assert allocate_offers(timed, initial(), ()) == ()


def test_shared_receipt_lot_does_not_collapse_distinct_hu_identities() -> None:
    timed = workload(6, 8)
    incoming = declared_receipts(timed)
    assert len(incoming) == 6 and len({h.lot_id for h in incoming}) == 2
    rows = allocate_offers(timed, initial(), incoming)
    assert len({r.hu.hu_id for r in rows if r.hu}) == 8
    assert all(r.hu is not None for r in rows)


@pytest.mark.parametrize(
    "field,value",
    [("quantity_units", True), ("gross_mass_kg", 0.94), ("unit_ids", ("duplicated",) * 24)],
)
def test_invalid_original_identity_is_rejected(field: str, value: Any) -> None:
    timed = workload()
    original = initial()
    bad = replace(original[0], **{field: value})
    with pytest.raises(ValueError):
        allocate_offers(timed, (bad, original[1]), declared_receipts(timed))


def test_duplicate_and_missing_initial_hus_cannot_fund_extra_orders() -> None:
    timed = workload()
    original = initial()
    for bad in ((original[0], original[0]), original[:1], (*original, original[0])):
        with pytest.raises(ValueError):
            allocate_offers(timed, bad, declared_receipts(timed))


def test_receipts_are_exact_offers_not_an_unbounded_stock_pool() -> None:
    timed = workload()
    incoming = declared_receipts(timed)
    bad_cases = (
        (),
        (*incoming, incoming[0]),
        (replace(incoming[0], hu_id="invented"), incoming[1]),
    )
    for bad in bad_cases:
        with pytest.raises(ValueError):
            allocate_offers(timed, initial(), bad)


def test_changed_offer_clock_or_identity_does_not_inherit_workload_hash() -> None:
    timed = workload()
    for bad in (
        replace(timed.jobs[0], arrival_tick=True),
        replace(timed.jobs[0], job_id=timed.jobs[1].job_id),
    ):
        with pytest.raises(ValueError):
            allocate_offers(replace(timed, jobs=(bad, *timed.jobs[1:])), initial(), ())


@pytest.mark.parametrize(
    "field,value", [("hu_id", []), ("hu_id", True), ("sku_id", []), ("initial_owner_id", 1)]
)
def test_malformed_identity_types_fail_with_value_error(field: str, value: Any) -> None:
    timed = workload()
    bad = replace(initial()[0], **{field: value})
    with pytest.raises(ValueError):
        allocate_offers(timed, (bad, initial()[1]), declared_receipts(timed))


def test_original_iteration_order_does_not_change_allocation() -> None:
    timed = workload()
    incoming = declared_receipts(timed)
    assert allocate_offers(timed, initial(), incoming) == allocate_offers(
        timed,
        tuple(reversed(initial())),
        incoming,
    )


def test_pallet_b2b_offers_are_preserved_including_shortage() -> None:
    timed = workload(0, 6)
    source = replace(
        timed.source,
        templates=tuple(replace(t, archetype_id="PALLET") for t in timed.source.templates),
        outbound_weights=tuple(
            replace(w, port_id="OUT_E_B2B") for w in timed.source.outbound_weights
        ),
    )
    timed = materialize_workload(source, timed.policy)
    original = tuple(replace(hu, archetype_id="PALLET") for hu in initial())
    rows = allocate_offers(timed, original, ())
    assert len(rows) == 6 and sum(row.status == "unallocated" for row in rows) == 4
    assert all(row.offer.port_id == "OUT_E_B2B" for row in rows)
    assert all(row.offer.archetype_id == "PALLET" for row in rows)
