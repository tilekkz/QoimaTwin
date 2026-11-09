"""Pinned initial arithmetic and actual ledger observations; no source engine runs."""

from dataclasses import replace
from functools import cache
from typing import cast

import pytest

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_profile import compile_coordinator_profile
from app.v3.coordinator_profile_authority import authoritative_sources
from app.v3.stock_ledger import StockLedger
from app.v3.storage_fullness import coordinator_storage_fullness
from tests.v3.test_coordinator_kpi_fixtures import outcome, point, profile
from tests.v3.test_coordinator_profile_fixtures import coordinator_document


@cache
def source_profile() -> CoordinatorProfile:
    bundle, conveyor = authoritative_sources()
    return compile_coordinator_profile(bundle, conveyor, coordinator_document()).profile


def test_source_baseline_uses_physical_and_active_denominators() -> None:
    value = source_profile()
    at_zero = point(value, 0)
    result = coordinator_storage_fullness(value, outcome(at_zero), at_zero)
    total = result["total"]
    assert (total["physical_slots"], total["occupied_slots"], total["empty_slots"]) == (
        776,
        530,
        246,
    )
    assert (total["active_slots"], total["active_empty_slots"], total["blocked_slots"]) == (
        588,
        58,
        188,
    )
    assert total["unreserved_active_empty_slots"] == 58
    assert total["units"] == 12256
    assert total["gross_mass_kg"] == {"numerator": 188077, "denominator": 20}
    assert total["occupied_fraction"] == {"numerator": 265, "denominator": 388}
    assert total["active_occupied_fraction"] == {"numerator": 265, "denominator": 294}
    assert len(result["slots"]) == 776
    assert result["tick"] == 0
    assert result["operational_admission"] is False


def test_actual_ledger_transfer_changes_current_fullness_without_rewriting_baseline() -> None:
    value = source_profile()
    flow = value.world.receipts.flow
    ledger = StockLedger(flow.stock, owners=flow.owners, materials=flow.materials)
    worker = next(owner.owner_id for owner in flow.owners if owner.kind == "worker")
    ledger.transfer_whole_hu("fullness-test", 0, "v3:HU:initial:DEMO_001:01", worker)
    observed = point(value, 7, ledger)
    result = coordinator_storage_fullness(value, outcome(observed), observed)
    assert result["total"]["occupied_slots"] == 529
    assert result["total"]["units"] == 12232
    assert result["total"]["gross_mass_kg"] == {"numerator": 940291, "denominator": 100}
    assert len(flow.stock.containers) == 530


def test_empty_slot_reservation_is_not_reported_as_unreserved_space() -> None:
    value = source_profile()
    at_zero = point(value, 0)
    reserved = replace(at_zero, leases=(("receipt:place:v3:slot:FLEX_W:003:L1:B1", "receipt-1"),))
    result = coordinator_storage_fullness(value, outcome(reserved), reserved)
    assert result["total"]["empty_slots"] == 246
    assert result["total"]["active_empty_slots"] == 58
    assert result["total"]["reserved_slots"] == 1
    assert result["total"]["unreserved_active_empty_slots"] == 57


def test_analytical_profile_does_not_invent_source_capacity() -> None:
    value = profile()
    observed = point(value, 0)
    result = coordinator_storage_fullness(value, outcome(observed), observed)
    assert result["available"] is False


@pytest.mark.parametrize(
    "kind", ["hash", "unknown_slot", "unknown_lease", "duplicate_lease", "tick"]
)
def test_stale_or_ambiguous_source_observation_is_rejected(kind: str) -> None:
    value = source_profile()
    observed = point(value, 0)
    slot = "v3:slot:FLEX_W:003:L1:B1"
    if kind == "hash":
        receipts = value.world.receipts
        flow = replace(receipts.flow, source_hashes=())
        value = replace(value, world=replace(value.world, receipts=replace(receipts, flow=flow)))
    elif kind == "unknown_slot":
        observed = replace(observed, leases=(("receipt:place:v3:slot:missing", "r"),))
    elif kind == "unknown_lease":
        observed = replace(observed, leases=(("future:place:" + slot, "r"),))
    elif kind == "duplicate_lease":
        observed = replace(
            observed, leases=(("receipt:place:" + slot, "r"), ("relocation:place:" + slot, "j"))
        )
    else:
        observed = replace(observed, tick=cast(int, False))
    with pytest.raises(ValueError):
        coordinator_storage_fullness(value, outcome(observed), observed)
