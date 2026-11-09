"""Independent composition clocks, per-SKU shares and namespace boundaries."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.offer_forecast_models import OfferForecast, OfferForecastCPU
from app.v3.offer_projection_inputs import compile_offer_projection
from app.v3.offer_projection_materialize import materialize_projection
from app.v3.offer_projection_models import OfferProjectionChoices, OfferProjectionInputs
from app.v3.outbound_shift_inputs import load_outbound_shift_inputs, verify_outbound_shift_inputs
from app.v3.workload_models import DemandWeight, WorkloadPolicy
from tests.v3.test_offer_projection_inputs import bound, forecast, history
from tests.v3.test_workload_fixtures import hand_source

__all__ = ["bound", "forecast", "history"]
PORTS = {"OUT1": frozenset({"SMALL_CARTON"}), "OUT2": frozenset({"SMALL_CARTON"})}


def _choices(horizon: int = 4_000_000, budget: int = 4) -> OfferProjectionChoices:
    return OfferProjectionChoices(WorkloadPolicy(horizon, 0, budget, "normal"), "source_c10", ())


def test_per_sku_port_normalization_is_not_a_global_intensity_share() -> None:
    source = replace(
        hand_source(),
        outbound_weights=(
            DemandWeight("A", "OUT1", F(3)),
            DemandWeight("A", "OUT2", F(1)),
            DemandWeight("B", "OUT1", F(10)),
            DemandWeight("B", "OUT2", F(30)),
        ),
    )
    result = materialize_projection(
        source, (("A", F(1)), ("B", F(3))), _choices(budget=16), PORTS, "a" * 64
    )
    assert [row.weight for row in result.port_mix] == [F(3, 4), F(1, 4), F(1, 4), F(3, 4)]
    assert [row.count for row in result.quotas] == [3, 1, 3, 9]
    assert len(result.jobs) == 16 and all(job.quantity_units == 24 for job in result.jobs)
    assert all(job.hu_id is None and job.lot_id is None for job in result.jobs)


def test_horizon_changes_arrivals_without_scaling_the_explicit_budget() -> None:
    args = (hand_source(), (("A", F(1)), ("B", F(3))))
    first = materialize_projection(*args, _choices(), PORTS, "a" * 64)
    longer = materialize_projection(*args, _choices(8_000_000), PORTS, "a" * 64)
    assert first.quotas == longer.quotas
    assert [job.arrival_tick for job in first.jobs] == [0, 1_000_000, 2_000_000, 3_000_000]
    assert [job.arrival_tick for job in longer.jobs] == [0, 2_000_000, 4_000_000, 6_000_000]


def test_zero_budget_does_not_clear_or_replace_positive_predicted_signal() -> None:
    result = materialize_projection(
        hand_source(), (("A", F(1)), ("B", F(3))), _choices(budget=0), PORTS, "a" * 64
    )
    assert [row.weight for row in result.weights] == [F(1), F(0), F(0), F(3)]
    assert result.jobs == () and all(
        row.count == row.expected == row.delta == 0 for row in result.quotas
    )


def test_zero_share_cannot_create_an_unpermitted_cargo_port_pair() -> None:
    original = hand_source()
    source = replace(
        original,
        templates=(
            original.templates[0],
            replace(original.templates[1], archetype_id="PALLET_LOAD"),
        ),
    )
    ports = {"OUT1": frozenset({"SMALL_CARTON"}), "OUT2": frozenset({"PALLET_LOAD"})}
    predicted = (("A", F(1)), ("B", F(3)))
    result = materialize_projection(source, predicted, _choices(), ports, "a" * 64)
    assert [(row.sku_id, row.port_id, row.count) for row in result.quotas] == [
        ("A", "OUT1", 1),
        ("B", "OUT2", 3),
    ]
    forged = replace(
        _choices(),
        port_mix_mode="explicit",
        port_mix=(
            DemandWeight("A", "OUT1", F(1)),
            DemandWeight("A", "OUT2", F(0)),
            DemandWeight("B", "OUT2", F(1)),
        ),
    )
    with pytest.raises(ValueError):
        materialize_projection(source, predicted, forged, ports, "a" * 64)


def test_cpu_measurements_cannot_change_public_projection_identity(
    forecast: OfferForecast,
    bound: OfferProjectionInputs,
) -> None:
    other = replace(forecast, measurements=OfferForecastCPU(999.0, 11.0, 22.0))
    projected = compile_offer_projection(other, bound.choices)
    assert projected.frozen_bytes == bound.frozen_bytes
    assert projected.input_hash == bound.input_hash


def test_projection_cannot_be_promoted_through_the_old_c11_public_namespace(
    bound: OfferProjectionInputs,
) -> None:
    with pytest.raises(ValueError):
        load_outbound_shift_inputs(bound.frozen_bytes)
    with pytest.raises(ValueError):
        verify_outbound_shift_inputs(bound)  # type: ignore[arg-type]
