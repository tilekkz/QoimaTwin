"""Strict source reauthentication preserves every offer, including B2B and shortage."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.outbound_placement_decision import (
    load_placement_decision,
    prepare_placement_decision,
    verify_placement_decision,
)
from app.v3.outbound_placement_models import (
    PlacementActor,
    PlacementCandidate,
    PlacementChoices,
    PlacementCustomer,
)
from app.v3.outbound_shift_inputs import compile_outbound_shift
from app.v3.outbound_stock_binding import bind_outbound_stock
from app.v3.outbound_stock_models import BoundOutboundStock
from app.v3.whole_profile_geometry import ROUTE_POLICY
from app.v3.workload_models import WorkloadPolicy

BACKEND = Path(__file__).resolve().parents[2]
HU = "v3:HU:initial:DEMO_113:01"


@pytest.fixture(scope="module")
def stock() -> BoundOutboundStock:
    inputs = compile_outbound_shift(
        BACKEND / "data/v3-proposal",
        BACKEND / "data/v3-adaptation-proposal",
        WorkloadPolicy(1000000000, 0, 1500, "normal"),
    )
    return bind_outbound_stock(inputs)


def choices(candidate: PlacementCandidate | None = None) -> PlacementChoices:
    return PlacementChoices(
        "test-explicit-one-candidate",
        () if candidate is None else (candidate,),
        ("S01",),
        ROUTE_POLICY,
        F(".7"),
        F("1.8"),
        F(".02"),
        (),
    )


def candidate(customer: PlacementCustomer | None = None) -> PlacementCandidate:
    return PlacementCandidate(
        HU,
        "v3:slot:STANDARD_W:004:L1:B1",
        "v3:slot:FLEX_W:003:L1:B1",
        PlacementActor("S01", "v3:service:OUT_S_EXPRESS", F(1), F(10)),
        1000000,
        1000000,
        customer,
    )


def test_empty_candidate_preserves_complete_stream(stock: BoundOutboundStock) -> None:
    result = prepare_placement_decision(stock, choices())
    assert result.no_op is True and result.selected is None and result.evaluations == ()
    assert result.stock.frozen_bytes == stock.frozen_bytes
    assert result.stock.inputs.workload_bytes == stock.inputs.workload_bytes
    assert {r.offer.port_id for r in result.stock.allocations} == {
        "OUT_W_RETAIL",
        "OUT_S_EXPRESS",
        "OUT_E_B2B",
    }
    assert not result.operational_admission and not result.full_n1_acceptance
    restored = load_placement_decision(result.frozen_bytes)
    assert restored == result and restored is not result


def test_missing_customer_binding_is_visible_without_cost(stock: BoundOutboundStock) -> None:
    result = prepare_placement_decision(stock, choices(candidate()))
    evaluation = result.evaluations[0]
    assert evaluation.status == "not_evaluable" and evaluation.cost is None
    assert "MISSING_CUSTOMER_BINDING" in evaluation.reasons
    assert result.no_op and result.placements == stock.inputs.scenario.initial_placements


def test_occupied_target_rejects_before_customer_cost(stock: BoundOutboundStock) -> None:
    moved = replace(candidate(), to_slot_id="v3:slot:STANDARD_W:004:L1:B2")
    result = prepare_placement_decision(stock, choices(moved))
    assert result.evaluations[0].status == "infeasible"
    assert "TARGET_OCCUPIED" in result.evaluations[0].reasons
    assert result.evaluations[0].cost is None


@pytest.mark.parametrize("field,value", [("take_ticks", True), ("actor", None)])
def test_runtime_type_aliases_fail_closed(
    stock: BoundOutboundStock, field: str, value: Any
) -> None:
    with pytest.raises(ValueError):
        prepare_placement_decision(stock, choices(replace(candidate(), **{field: value})))


def test_rehashed_metadata_and_unknown_fields_do_not_grant_authority(
    stock: BoundOutboundStock,
) -> None:
    result = prepare_placement_decision(stock, choices())
    for field, value in (("no_op", 1), ("operational_admission", True), ("invented", 0)):
        wire = parse_json(result.frozen_bytes)
        wire[field] = value
        with pytest.raises(ValueError):
            load_placement_decision(canonical_bytes(wire))
    with pytest.raises(ValueError):
        verify_placement_decision(replace(result, no_op=1))  # type: ignore[arg-type]


def test_mutated_offers_are_not_readopted_from_retained_metadata(stock: BoundOutboundStock) -> None:
    changed = replace(stock, allocations=stock.allocations[:-1])
    with pytest.raises(ValueError):
        prepare_placement_decision(changed, choices())


def test_source_candidate_is_evaluated_once_and_negative_cost_is_retained(
    stock: BoundOutboundStock,
) -> None:
    rows = [r for r in stock.allocations if r.hu is not None and r.hu.hu_id == HU]
    assert len(rows) == 1 and rows[0].offer.port_id == "OUT_S_EXPRESS"
    # Exact source cell08; explicit checked connector, height/payload are proposal choices.
    buffer = canonical_bytes(
        {
            "place_id": "v3:buffer:OUT_S_EXPRESS:08",
            "port_id": "OUT_S_EXPRESS",
            "zone_id": "STAGE_OUT_S_EXPRESS",
            "bounds_xz": ["38.4", "4.4", "39.6", "5.6"],
            "path_xz": [["48", "6"], ["39", "6"], ["39", "5"]],
            "height_m": "1.2",
            "max_payload_kg": "15",
        }
    )
    customer = PlacementCustomer(
        rows[0].offer.job_id, "OUT_S_EXPRESS", buffer, 1000000, 1000000, 30000000
    )
    result = prepare_placement_decision(stock, choices(candidate(customer)))
    evaluation = result.evaluations[0]
    assert evaluation.status == "evaluated", evaluation.reasons
    assert evaluation.affected_offer == rows[0].offer
    assert evaluation.cost is not None and evaluation.cost.relocation_ticks == 196160001
    assert evaluation.cost.net_saving_ticks < 0
    assert result.selected is None and result.no_op is True
    assert result.selection_reason == "NET_COST_NOT_BETTER"
    assert verify_placement_decision(result) == result
