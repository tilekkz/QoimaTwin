"""The 2+2+3+1+5 second hand cycle pays the same actual worker exactly once."""

from dataclasses import replace

import pytest

from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_metrics import summary
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


@pytest.mark.parametrize(("horizon", "placed", "units"), [(5, 0, 0), (10, 1, 24)])
def test_relocation_labor_is_a_subset_of_actual_worker_labor_at_both_boundaries(
    horizon: int,
    placed: int,
    units: int,
) -> None:
    profile = relocation_hand()
    outcome = RelocationEngine(profile, receipt_conveyor()).run(horizon * SECOND, 20 * SECOND)
    metrics = summary(profile, outcome)
    at_horizon, at_end = metrics["at_horizon"], metrics["at_end"]
    assert at_horizon["placed_hus"] == placed
    assert at_horizon["placed_units"] == units
    assert at_horizon["paid_ticks"] == horizon * SECOND
    assert at_horizon["pending_placement"] == 1 - placed
    assert at_horizon["pending_return"] == 1
    assert at_end["placed_hus"] == 1 and at_end["placed_units"] == 24
    assert at_end["returned_jobs"] == 1 and at_end["paid_ticks"] == 13 * SECOND
    assert metrics["common"]["at_horizon"]["labor"]["paid_ticks"] == horizon * SECOND
    assert metrics["common"]["at_end"]["labor"]["paid_ticks"] == 13 * SECOND
    assert metrics["paid_ticks_scope"] == "subset_of_common_worker_labor_do_not_add"


def test_empty_plan_has_zero_relocation_cost_and_preserves_common_metrics() -> None:
    profile = replace(relocation_hand(), jobs=())
    outcome = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 2 * SECOND)
    metrics = summary(profile, outcome)
    for window in ("at_horizon", "at_end"):
        assert metrics[window]["offered_jobs"] == 0
        assert metrics[window]["placed_units"] == 0
        assert metrics[window]["paid_ticks"] == 0
