"""Independent finite-offer arithmetic; hand authority is never public C10 authority."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.heavy_inbound_augment import augment_offers
from app.v3.heavy_inbound_models import HeavyInboundReceipt
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import TimedWorkload, WorkloadPolicy
from tests.v3.test_workload_fixtures import hand_source


def baseline() -> TimedWorkload:
    source = hand_source()
    pallet = replace(source.templates[0], archetype_id="PALLET_LOAD", gross_mass_kg=F(455))
    source = replace(source, templates=(pallet, source.templates[1]))
    return materialize_workload(source, WorkloadPolicy(8, 4, 0, "normal"))


def additions() -> tuple[HeavyInboundReceipt, ...]:
    return (
        HeavyInboundReceipt("extra-1", "HU-extra-1", "lot-extra", "A", "IN1", 1),
        HeavyInboundReceipt("extra-2", "HU-extra-2", "lot-extra", "A", "IN1", 3),
    )


def test_two_pallets_become_four_other_two_stay_exact_and_extra_mass_is_910() -> None:
    before = baseline()
    result = augment_offers(before, additions(), {"IN1": frozenset({"PALLET_LOAD"})})
    assert len(before.jobs) == 4 and len(result.postshift_jobs) == 6
    assert sum(j.archetype_id == "PALLET_LOAD" for j in before.jobs) == 2
    assert sum(j.archetype_id == "PALLET_LOAD" for j in result.postshift_jobs) == 4
    retained = {j.job_id: j for j in result.postshift_jobs}
    assert all(retained[j.job_id] == j for j in before.jobs)
    assert [j.arrival_tick for j in result.postshift_jobs] == [0, 1, 2, 3, 4, 6]
    assert len(result.deltas) == 1
    delta = result.deltas[0]
    assert (delta.before_count, delta.added_count, delta.after_count) == (2, 2, 4)
    assert delta.added_mass_kg == F(910)
    assert all(r.offer.quantity_units == 24 for r in result.receipts)
    assert {r.offer.lot_id for r in result.receipts} == {"lot-extra"}


def test_no_increase_and_existing_identity_are_rejected() -> None:
    before = baseline()
    ports = {"IN1": frozenset({"PALLET_LOAD"})}
    with pytest.raises(ValueError, match="INCREASE"):
        augment_offers(before, (), ports)
    for changed in (
        replace(additions()[0], job_id=before.jobs[0].job_id),
        replace(additions()[0], hu_id="initial-HU-A"),
        replace(additions()[0], hu_id=next(j.hu_id for j in before.jobs if j.hu_id)),
    ):
        with pytest.raises(ValueError, match="IDENTITY"):
            augment_offers(before, (changed,), ports)


def test_wrong_class_port_clock_and_conflicting_lot_reject() -> None:
    before = baseline()
    ports = {"IN1": frozenset({"PALLET_LOAD"})}
    for changed in (
        replace(additions()[0], sku_id="B"),
        replace(additions()[0], port_id="OUT1"),
        replace(additions()[0], arrival_tick=8),
        replace(additions()[0], arrival_tick=True),
        replace(additions()[0], lot_id="initial-lot-B"),
    ):
        with pytest.raises(ValueError):
            augment_offers(before, (changed,), ports)


def test_input_order_is_not_a_hidden_change_in_the_postshift_stream() -> None:
    ports = {"IN1": frozenset({"PALLET_LOAD"})}
    first = augment_offers(baseline(), additions(), ports)
    second = augment_offers(baseline(), additions()[::-1], ports)
    assert first == second
