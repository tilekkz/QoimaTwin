"""Fresh forecast/source composition; the actual future test stream is absent."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_forecast_models import OfferForecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_history_models import OfferHistoryInputs
from app.v3.offer_projection_inputs import (
    compile_offer_projection,
    load_offer_projection,
    verify_offer_projection,
)
from app.v3.offer_projection_models import OfferProjectionChoices, OfferProjectionInputs
from app.v3.workload_models import WorkloadPolicy
from tests.v3.test_offer_history_fixtures import choices as history_choices
from tests.v3.test_offer_history_fixtures import history, history_bytes

__all__ = ["history"]


def choices(budget: int = 4) -> OfferProjectionChoices:
    return OfferProjectionChoices(WorkloadPolicy(4_000_000, 0, budget, "normal"), "source_c10", ())


@pytest.fixture(scope="module")
def forecast(history: OfferHistoryInputs) -> OfferForecast:
    return fit_offer_forecast(history, "mean28")


@pytest.fixture(scope="module")
def bound(forecast: OfferForecast) -> OfferProjectionInputs:
    return compile_offer_projection(forecast, choices())


def test_public_projection_preserves_all_source_stock_and_predicted_namespace(
    bound: OfferProjectionInputs,
    forecast: OfferForecast,
) -> None:
    assert bound.source == forecast.source
    assert len(bound.source.templates) == 200
    assert len(bound.initial_hus) == 530
    assert sum(hu.quantity_units for hu in bound.initial_hus) == 12256
    assert bound.forecast_bytes == forecast.frozen_bytes
    assert bound.forecast_id == forecast.input_hash
    assert [j.arrival_tick for j in bound.offers.jobs] == [0, 1_000_000, 2_000_000, 3_000_000]
    assert len({q.sku_id for q in bound.offers.quotas}) == 200
    assert {q.port_id for q in bound.offers.quotas} == {
        "OUT_W_RETAIL",
        "OUT_S_EXPRESS",
        "OUT_E_B2B",
    }
    assert all(j.hu_id is None and j.lot_id is None for j in bound.offers.jobs)
    assert b'"cpu"' not in bound.frozen_bytes and b'"measurements"' not in bound.frozen_bytes
    assert (
        not bound.operational_admission
        and not bound.actual_test_stream
        and not bound.throughput_claim
    )


def test_fresh_load_verify_and_explicit_mix_reproduce_source_rights(
    bound: OfferProjectionInputs,
) -> None:
    fresh = verify_offer_projection(bound)
    assert fresh == load_offer_projection(bound.frozen_bytes) == bound
    assert fresh is not bound and fresh.source is not bound.source
    forecast = fit_offer_forecast(
        compile_offer_history(history_bytes(), history_choices()), "mean28"
    )
    explicit = replace(bound.choices, port_mix_mode="explicit", port_mix=bound.offers.port_mix)
    other = compile_offer_projection(forecast, explicit)
    assert other.offers == bound.offers
    assert other.input_hash != bound.input_hash


def test_real_all_zero_signal_keeps_catalog_and_rejects_positive_budget() -> None:
    history = compile_offer_history(history_bytes(0, 0), history_choices())
    forecast = fit_offer_forecast(history, "mean28")
    zero = compile_offer_projection(forecast, choices(0))
    assert zero.offers.jobs == () and all(q.count == 0 for q in zero.offers.quotas)
    assert len(zero.source.templates) == 200 and len(zero.initial_hus) == 530
    assert all(row.weight == 0 for row in zero.offers.weights)
    assert zero.source == forecast.source
    with pytest.raises(ValueError, match=r"positive|POSITIVE"):
        compile_offer_projection(forecast, choices(1))


@pytest.mark.parametrize("change", ["arrival", "quantity", "quota", "forecast", "extra", "actual"])
def test_rehashed_projection_changes_are_rejected(
    bound: OfferProjectionInputs, change: str
) -> None:
    value = parse_json(bound.frozen_bytes)
    if change == "arrival":
        value["offers"]["jobs"][0]["arrival_tick"] += 1
    elif change == "quantity":
        value["offers"]["jobs"][0]["quantity_units"] += 1
    elif change == "quota":
        value["offers"]["quotas"][0]["count"] += 1
    elif change == "forecast":
        value["forecast_id"] = "f" * 64
    elif change == "extra":
        value["actual_workload"] = []
    else:
        value["actual_test_stream"] = True
    with pytest.raises(ValueError):
        load_offer_projection(canonical_bytes(value))


def test_retained_equal_aliases_are_not_authority(bound: OfferProjectionInputs) -> None:
    alias: Any = 0
    altered = replace(bound, actual_test_stream=alias)
    with pytest.raises(ValueError):
        verify_offer_projection(altered)
    first = bound.offers.weights[0]
    altered_row = replace(first, weight=int(first.weight))  # type: ignore[arg-type]
    altered = replace(
        bound, offers=replace(bound.offers, weights=(altered_row, *bound.offers.weights[1:]))
    )
    with pytest.raises(ValueError):
        verify_offer_projection(altered)


def test_public_compile_rejects_forged_signal_nonempty_inbound_and_port_grants(
    forecast: OfferForecast,
    bound: OfferProjectionInputs,
) -> None:
    forged = replace(forecast, predictions=(("DEMO_001", F(999)), *forecast.predictions[1:]))
    with pytest.raises(ValueError):
        compile_offer_projection(forged, choices())
    with pytest.raises(ValueError, match="INBOUND"):
        compile_offer_projection(
            forecast, replace(choices(), policy=WorkloadPolicy(4_000_000, 1, 4, "normal"))
        )
    mix = bound.offers.port_mix
    wrong = (replace(mix[0], port_id="IN_W_BULK"), *mix[1:])
    with pytest.raises(ValueError):
        compile_offer_projection(
            forecast, OfferProjectionChoices(choices().policy, "explicit", wrong)
        )


def test_fresh_raw_source_whitespace_change_is_rejected(
    bound: OfferProjectionInputs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = original(path)
        return raw + b" " if path.name == "baseline-assignment-v3.json" else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_offer_projection(bound)


def test_foreign_namespace_and_noncanonical_json_reject(bound: OfferProjectionInputs) -> None:
    value = parse_json(bound.frozen_bytes)
    value["schema_version"] = "qoima-n1-outbound-shift-inputs-0.1.0"
    with pytest.raises(ValueError):
        load_offer_projection(canonical_bytes(value))
    with pytest.raises(ValueError):
        load_offer_projection(bound.frozen_bytes + b"\n")
    with pytest.raises(ValueError):
        verify_offer_projection(bound.offers)  # type: ignore[arg-type]
