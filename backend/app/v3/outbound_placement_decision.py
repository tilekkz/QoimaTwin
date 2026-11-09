"""Planning-only canonical decisions retain the entire authenticated N1 offered stream."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.outbound_placement_decode import decode_choices
from app.v3.outbound_placement_evaluate import evaluate_candidate
from app.v3.outbound_placement_models import (
    SELECTION_POLICY,
    VERSION,
    N1PlacementDecision,
    PlacementChoices,
)
from app.v3.outbound_placement_source import source_bundle
from app.v3.outbound_placement_validation import validate_choices
from app.v3.outbound_placement_wire import decision_record, record
from app.v3.outbound_stock_binding import load_outbound_stock, verify_outbound_stock
from app.v3.outbound_stock_models import BoundOutboundStock
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.staff_registry_values import object_fields


def _prepare(stock: BoundOutboundStock, choices: PlacementChoices) -> N1PlacementDecision:
    validate_choices(choices)
    bundle = source_bundle()
    evaluations = tuple(evaluate_candidate(bundle, stock, choices, c) for c in choices.candidates)
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
        for p in stock.inputs.scenario.initial_placements
    )
    result = N1PlacementDecision(
        stock,
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


def prepare_placement_decision(
    stock: BoundOutboundStock, choices: PlacementChoices
) -> N1PlacementDecision:
    return _prepare(verify_outbound_stock(stock), choices)


def load_placement_decision(raw: bytes) -> N1PlacementDecision:
    require(type(raw) is bytes, "Exact immutable placement bytes required")
    value = object_fields(
        parse_json(raw),
        "schema_version selection_policy stock_inputs "
        "stock_input_hash choices evaluations selected no_op selection_reason placements "
        "operational_admission full_n1_acceptance",
    )
    require(canonical_bytes(value) == raw, "Canonical placement bytes required")
    require(
        value["schema_version"] == VERSION and value["selection_policy"] == SELECTION_POLICY,
        "Unsupported placement version or policy",
    )
    stock = load_outbound_stock(canonical_bytes(value["stock_inputs"]))
    result = _prepare(stock, decode_choices(value["choices"]))
    require(
        result.frozen_bytes == raw, "Placement differs from source, choices or exact evaluation"
    )
    return result


def verify_placement_decision(value: N1PlacementDecision) -> N1PlacementDecision:
    require(type(value) is N1PlacementDecision, "Exact N1PlacementDecision required")
    expected = load_placement_decision(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
