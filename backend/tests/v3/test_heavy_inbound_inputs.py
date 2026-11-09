"""Explicit source-heavy additions preserve every original C10 offered row."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.heavy_inbound_binding import compile_heavy_inbound_inputs
from app.v3.heavy_inbound_models import HeavyInboundInputs, HeavyInboundReceipt
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_wire import workload_dict


def policy() -> WorkloadPolicy:
    return WorkloadPolicy(60000000, 40, 60, "normal")


def additions() -> tuple[HeavyInboundReceipt, ...]:
    return (
        HeavyInboundReceipt("n2-job-1", "n2-HU-1", "n2-lot", "DEMO_172", "IN_W_BULK", 1),
        HeavyInboundReceipt("n2-job-2", "n2-HU-2", "n2-lot", "DEMO_172", "IN_W_BULK", 30000000),
    )


@pytest.fixture(scope="module")
def bound() -> HeavyInboundInputs:
    return compile_heavy_inbound_inputs(policy(), additions())


def test_actual_source_stock_offers_and_quantity_mass_are_preserved(
    bound: HeavyInboundInputs,
) -> None:
    assert len(bound.authority.initial_hus) == 530
    assert sum(h.quantity_units for h in bound.authority.initial_hus) == 12256
    before = bound.authority.baseline
    assert len(before.jobs) == 100 and len(bound.postshift_jobs) == 102
    rows = {j.job_id: j for j in bound.postshift_jobs}
    assert all(rows[j.job_id] == j for j in before.jobs)
    assert bound.authority.baseline_bytes == canonical_bytes(workload_dict(before))
    assert {j.port_id for j in before.jobs if j.direction == "outbound"} == {
        "OUT_W_RETAIL",
        "OUT_S_EXPRESS",
        "OUT_E_B2B",
    }
    assert len(bound.receipts) == 2
    assert all(r.template.gross_mass_kg == F(455) for r in bound.receipts)
    assert all(
        r.offer.quantity_units == 24 and r.offer.archetype_id == "PALLET_LOAD"
        for r in bound.receipts
    )
    assert sum(d.added_mass_kg for d in bound.deltas) == F(910)
    assert bound.accepted_receipt_count == 0
    assert bound.operational_admission is False and bound.full_n2_acceptance is False


@pytest.mark.parametrize(
    "field,value",
    [("port_id", "IN_E_PARCEL"), ("sku_id", "DEMO_001"), ("arrival_tick", 60000000)],
)
def test_public_source_restrictions_are_not_inferred_or_expanded(field: str, value: Any) -> None:
    changed = replace(additions()[0], **{field: value})
    with pytest.raises(ValueError):
        compile_heavy_inbound_inputs(policy(), (changed,))


def test_existing_source_hu_and_baseline_job_ids_cannot_be_declared_again(
    bound: HeavyInboundInputs,
) -> None:
    for changed in (
        replace(additions()[0], hu_id="v3:HU:initial:DEMO_172:01"),
        replace(additions()[0], job_id=bound.authority.baseline.jobs[0].job_id),
    ):
        with pytest.raises(ValueError, match="IDENTITY"):
            compile_heavy_inbound_inputs(policy(), (changed,))


def test_zero_additions_and_foreign_policy_types_fail_closed() -> None:
    with pytest.raises(ValueError, match="INCREASE"):
        compile_heavy_inbound_inputs(policy(), ())
    with pytest.raises(ValueError):
        compile_heavy_inbound_inputs(replace(policy(), inbound_hus=True), additions())
