"""Source feasibility and full paid cost retain honest no-op in the forecast namespace."""

from dataclasses import replace

from app.v3.forecast_placement_decision import prepare_forecast_placement_decision
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.outbound_placement_cost import price_candidate
from tests.v3.test_forecast_placement_fixtures import (
    HU,
    candidate,
    choices,
    source_candidate,
    stock,
)
from tests.v3.test_outbound_placement_cost import facts, line_graph

__all__ = ["stock"]


def test_no_candidate_preserves_all_predicted_offers_and_original_placements(
    stock: ForecastBoundStock,
) -> None:
    result = prepare_forecast_placement_decision(stock, choices())
    assert result.no_op is True and result.selected is None and result.evaluations == ()
    assert result.selection_reason == "NO_CANDIDATE"
    assert result.stock.frozen_bytes == stock.frozen_bytes
    assert result.stock.projection.frozen_bytes == stock.projection.frozen_bytes
    assert tuple(row.offer for row in result.stock.allocations) == stock.projection.offers.jobs
    assert len(result.placements) == 530 and result.placements == stock.initial_placements
    assert result.forecast_id == stock.projection.forecast_id
    assert result.projection_id == stock.projection.input_hash
    assert result.stock_input_hash == stock.input_hash
    assert not result.operational_admission and not result.actual_test_stream


def test_actual_source_negative_price_is_retained_once_and_selects_noop(
    stock: ForecastBoundStock,
) -> None:
    result = prepare_forecast_placement_decision(stock, choices(source_candidate(stock)))
    assert len([row for row in stock.allocations if row.hu is not None and row.hu.hu_id == HU]) == 1
    evaluation = result.evaluations[0]
    assert evaluation.status == "evaluated", evaluation.reasons
    assert evaluation.cost is not None
    assert evaluation.cost.relocation_ticks == 196_160_001
    assert evaluation.cost.gross_saving_ticks == 140_799_998
    assert evaluation.cost.net_saving_ticks == -55_360_003
    assert result.selected is None and result.no_op is True
    assert result.selection_reason == "NET_COST_NOT_BETTER"
    assert result.placements == stock.initial_placements
    assert result.stock.allocations == stock.allocations


def test_missing_customer_and_occupied_target_keep_distinct_explanations(
    stock: ForecastBoundStock,
) -> None:
    missing = prepare_forecast_placement_decision(stock, choices(candidate())).evaluations[0]
    assert missing.status == "not_evaluable" and missing.reasons == ("MISSING_CUSTOMER_BINDING",)
    occupied = replace(candidate(), to_slot_id="v3:slot:STANDARD_W:004:L1:B2")
    invalid = prepare_forecast_placement_decision(stock, choices(occupied)).evaluations[0]
    assert invalid.status == "infeasible" and invalid.reasons == ("TARGET_OCCUPIED",)
    assert missing.cost is invalid.cost is None


def test_different_customer_cannot_borrow_the_original_hu_cycle(stock: ForecastBoundStock) -> None:
    selected = source_candidate(stock)
    assert selected.customer is not None
    other = next(
        row.offer for row in stock.allocations if row.offer.job_id != selected.customer.offer_id
    )
    changed = replace(selected, customer=replace(selected.customer, offer_id=other.job_id))
    result = prepare_forecast_placement_decision(stock, choices(changed))
    assert result.no_op and result.evaluations[0].cost is None
    assert result.evaluations[0].reasons == ("CUSTOMER_BINDING_MISMATCH",)


def test_shared_hand_cost_is_twenty_five_to_nine_minus_full_twenty_two() -> None:
    cost = price_candidate(line_graph(), facts())
    assert (cost.baseline_ticks, cost.adapted_ticks, cost.relocation_ticks) == (
        25_000_000,
        9_000_000,
        22_000_000,
    )
    assert cost.net_saving_ticks == -6_000_000
