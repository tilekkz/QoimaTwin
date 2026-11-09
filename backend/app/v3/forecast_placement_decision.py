"""Reauthenticate forecast stock and source; reuse physical feasibility and complete cost."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.forecast_placement_models import SCOPE, VERSION, ForecastPlacementDecision
from app.v3.forecast_placement_wire import decision_record
from app.v3.forecast_stock_binding import load_forecast_stock, verify_forecast_stock
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.outbound_placement_decode import decode_choices
from app.v3.outbound_placement_evaluate import evaluate_source_candidate
from app.v3.outbound_placement_models import SELECTION_POLICY, PlacementChoices
from app.v3.outbound_placement_source import source_bundle
from app.v3.outbound_placement_validation import validate_choices
from app.v3.outbound_placement_wire import record
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.staff_registry_values import object_fields
from app.v3.workload_source import load_workload_source


def _prepare(stock: ForecastBoundStock, choices: PlacementChoices) -> ForecastPlacementDecision:
    validate_choices(choices)
    bundle = source_bundle()
    source = stock.projection.source
    require_same_authority(source, load_workload_source(bundle))
    evaluations = tuple(
        evaluate_source_candidate(bundle, stock, source, choices, c) for c in choices.candidates
    )
    selected = next(
        (e.candidate for e in evaluations if e.cost is not None and e.cost.net_saving_ticks > 0),
        None,
    )
    reason = "NO_CANDIDATE" if not evaluations else evaluations[0].reasons[0]
    places = tuple(
        replace(
            p,
            slot_id=selected.to_slot_id,
            module_id=next(s.module_id for s in bundle.slots if s.slot_id == selected.to_slot_id),
        )
        if selected is not None and p.hu_id == selected.hu_id
        else p
        for p in stock.initial_placements
    )
    result = ForecastPlacementDecision(
        stock,
        stock.projection.forecast_id,
        stock.projection.input_hash,
        stock.input_hash,
        choices,
        evaluations,
        selected,
        selected is None,
        reason,
        places,
        canonical_bytes(record(choices)),
        b"",
        "",
    )
    raw = canonical_bytes(decision_record(result))
    return replace(result, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def prepare_forecast_placement_decision(
    stock: ForecastBoundStock, choices: PlacementChoices
) -> ForecastPlacementDecision:
    return _prepare(verify_forecast_stock(stock), choices)


def load_forecast_placement_decision(raw: bytes) -> ForecastPlacementDecision:
    require(type(raw) is bytes, "Exact immutable forecast placement bytes required")
    value = object_fields(
        parse_json(raw),
        "schema_version scope selection_policy forecast_id projection_id stock_input_hash "
        "stock_inputs choices evaluations selected no_op selection_reason placements "
        "operational_admission actual_test_stream full_n1_acceptance",
    )
    require(canonical_bytes(value) == raw, "Canonical forecast placement bytes required")
    require(
        (value["schema_version"], value["scope"], value["selection_policy"])
        == (VERSION, SCOPE, SELECTION_POLICY),
        "Unsupported forecast placement version, scope or policy",
    )
    stock = load_forecast_stock(canonical_bytes(value["stock_inputs"]))
    result = _prepare(stock, decode_choices(value["choices"]))
    require(result.frozen_bytes == raw, "Forecast placement differs from reconstructed authority")
    return result


def verify_forecast_placement_decision(
    value: ForecastPlacementDecision,
) -> ForecastPlacementDecision:
    require(type(value) is ForecastPlacementDecision, "Exact ForecastPlacementDecision required")
    expected = load_forecast_placement_decision(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
