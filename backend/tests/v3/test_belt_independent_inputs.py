"""Malformed explicit input never becomes a second physical HU or a clocked job."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.belt_engine import BeltEngine
from tests.v3.test_belt_runtime import job, source_catalog


@pytest.mark.parametrize("field", ["job", "hu", "carrier"])
def test_each_physical_identity_namespace_is_unique(field: str) -> None:
    first = job("A", ("v3:conv:entry-arc",))
    second = job("B", first.route)
    if field == "job":
        second = replace(second, job_id=first.job_id)
    elif field == "hu":
        second = replace(second, hu_id=first.hu_id)
    else:
        second = replace(
            second, payload=replace(second.payload, payload_id=first.payload.payload_id)
        )
    with pytest.raises(ValueError):
        BeltEngine(source_catalog(), (first, second), check_invariants=True)


@pytest.mark.parametrize("invalid", [True, -1, float("nan"), float("inf")])
def test_arrival_requires_an_exact_nonnegative_integer(invalid: object) -> None:
    value = replace(job("A", ("v3:conv:entry-arc",)), arrival_tick=cast(int, invalid))
    with pytest.raises(ValueError):
        BeltEngine(source_catalog(), (value,), check_invariants=True)


@pytest.mark.parametrize("invalid", [True, F(-1), float("nan"), float("inf")])
def test_direct_payload_mass_rejects_invalid_values(invalid: object) -> None:
    value = job("A", ("v3:conv:entry-arc",))
    with pytest.raises(ValueError):
        replace(value.payload, gross_mass_kg=cast(F, invalid))


@pytest.mark.parametrize("horizon,end", [(True, 20), (0, 20), (10, 9), (10, True)])
def test_run_window_rejects_boolean_or_reversed_bounds(horizon: int, end: int) -> None:
    engine = BeltEngine(source_catalog(), (), check_invariants=True)
    with pytest.raises(ValueError):
        engine.run(horizon, end)
