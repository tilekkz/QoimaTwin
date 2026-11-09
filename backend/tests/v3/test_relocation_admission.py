"""Pinned source choices checked independently of scheduling or ledger execution."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.inputs import load_v3_bundle
from app.v3.relocation_admission import source_places
from app.v3.relocation_models import RelocationJob
from app.v3.settings import default_inputs
from tests.v3.test_relocation_plan_fixtures import hand_relocation


def source_job() -> RelocationJob:
    return RelocationJob(
        "MOVE113",
        0,
        "v3:HU:initial:DEMO_113:01",
        "v3:slot:STANDARD_W:004:L1:B1",
        "v3:slot:FLEX_W:003:L1:B1",
        "S01",
        1_000_000,
        1_000_000,
    )


def test_actual_intact_standard_to_free_flex_has_exact_source_capacity() -> None:
    bundle = load_v3_bundle(default_inputs())
    places = source_places(bundle, hand_relocation().coordinator, (source_job(),))
    source, target = (
        {p.owner_id: p for p in places}[source_job().from_slot_id],
        {p.owner_id: p for p in places}[source_job().to_slot_id],
    )
    assert source.dimensions == (F(5, 4), F(21, 20), F(11, 10))
    assert target.dimensions == (F(7, 5), F(3, 5), F(1))
    assert (source.module_max_gross_kg, target.module_max_gross_kg) == (F(1500), F(15))
    assert target.module_max_hus == 1


@pytest.mark.parametrize(
    "target",
    [
        "v3:slot:STANDARD_W:004:L1:B2",
        "v3:slot:STANDARD_W:004:L2:B1",
        "v3:slot:SMALL_W:017:L1:B1",
        "unknown",
    ],
)
def test_occupied_reserve_wrong_class_unknown_destinations_reject(target: str) -> None:
    with pytest.raises(ValueError):
        source_places(
            load_v3_bundle(default_inputs()),
            hand_relocation().coordinator,
            (replace(source_job(), to_slot_id=target),),
        )


def test_hu_source_address_cannot_be_relabelled() -> None:
    job = replace(source_job(), from_slot_id="v3:slot:STANDARD_W:004:L1:B2")
    with pytest.raises(ValueError):
        source_places(load_v3_bundle(default_inputs()), hand_relocation().coordinator, (job,))
