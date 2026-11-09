"""Small typed orchestration doubles, not source or numerical forecast acceptance."""

from dataclasses import dataclass, replace
from fractions import Fraction as F
from hashlib import sha256
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import forecast_relocation_binding as bridge
from app.v3.coordinator_profile import CompiledCoordinatorProfile
from app.v3.flow_profile_wire import record
from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.forecast_relocation_models import ForecastRelocationChoices
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.offer_projection_models import (
    OfferProjectionChoices,
    OfferProjectionInputs,
    ProjectionOffers,
)
from app.v3.outbound_placement_models import (
    PlacementActor,
    PlacementCandidate,
    PlacementChoices,
    PlacementCost,
    PlacementCustomer,
    PlacementEvaluation,
    PlacementOperation,
)
from app.v3.outbound_shift_models import BaselinePlacement
from app.v3.outbound_stock_models import StockAllocation, StockHU
from app.v3.relocation_models import BoundRelocation, RelocationChoices, RelocationProfile
from app.v3.relocation_pair_inputs import PreparedRelocationPair
from app.v3.relocation_plan import plan_relocations
from app.v3.workload_models import WorkloadJob, WorkloadPolicy, WorkloadSource
from tests.v3.test_relocation_plan_fixtures import hand_relocation


@dataclass
class BridgeCase:
    common: CompiledCoordinatorProfile
    decision: ForecastPlacementDecision
    relocation: RelocationProfile
    calls: list[RelocationChoices]


def _common() -> tuple[CompiledCoordinatorProfile, RelocationProfile]:
    relocation = hand_relocation()
    flow = replace(
        relocation.coordinator.world.receipts.flow,
        source_revision="hand-source",
        source_hashes=(("hand-source.json", "a" * 64),),
    )
    coordinator = replace(
        relocation.coordinator,
        world=replace(
            relocation.coordinator.world,
            receipts=replace(relocation.coordinator.world.receipts, flow=flow),
        ),
    )
    raw = canonical_bytes(
        {
            "source": {"layout_content_hash": "hand-layout"},
            "choices": {"whole_buffers": [_buffer_row()]},
            "actual_work": ["actual-A", "actual-B2B"],
            "fixture": True,
        }
    )
    common = CompiledCoordinatorProfile(
        coordinator, 1_000_000_000, 1_800_000_000, raw, sha256(raw).hexdigest(), "registry"
    )
    return common, replace(relocation, coordinator=coordinator)


def _buffer_row() -> dict[str, Any]:
    def rational(value: int) -> dict[str, int]:
        return {"numerator": value, "denominator": 1}

    return {
        "owner_id": "whole-buffer",
        "port_id": "OUT_W_RETAIL",
        "zone_id": "ZONE",
        "bounds_xz": [rational(n) for n in (0, 0, 1, 1)],
        "path_xz": [[rational(0), rational(0)], [rational(1), rational(0)]],
        "height_m": rational(1),
        "max_gross_kg": rational(15),
        "clearance_m": rational(0),
    }


def _original_hu(common: CompiledCoordinatorProfile) -> StockHU:
    flow = common.profile.world.receipts.flow
    container, units = flow.stock.containers[0], flow.stock.units
    return StockHU(
        "HU1",
        units[0].sku_id,
        "SMALL_CARTON",
        units[0].lot_id,
        tuple(u.unit_id for u in units),
        len(units),
        container.recipe.max_gross_kg,
        "slot",
        None,
        None,
    )


def _offers(hu: StockHU) -> tuple[WorkloadJob, ...]:
    return tuple(
        WorkloadJob(
            name,
            "outbound",
            hu.sku_id,
            hu.archetype_id,
            "template",
            port,
            hu.quantity_units,
            tick,
            None,
            None,
        )
        for name, port, tick in (
            ("predicted-A", "OUT_W_RETAIL", 10),
            ("predicted-B2B", "OUT_E_B2B", 30),
        )
    )


def _stock(common: CompiledCoordinatorProfile) -> ForecastBoundStock:
    flow = common.profile.world.receipts.flow
    hu = _original_hu(common)
    source = WorkloadSource("hand-source", "hand-layout", flow.source_hashes, (), (), (), ())
    offers = _offers(hu)
    projection = OfferProjectionInputs(
        b'{"test_double":"forecast"}',
        "forecast",
        source,
        (),
        OfferProjectionChoices(
            WorkloadPolicy(common.horizon_tick, 0, 2, "normal"), "source_c10", ()
        ),
        ProjectionOffers((), (), (), offers, "population"),
        b"{}",
        "projection",
    )
    rows = (
        StockAllocation(offers[0], "original_bound", hu, None, None),
        StockAllocation(offers[1], "unallocated", None, "DECLARED_STOCK_EXHAUSTED", None),
    )
    return ForecastBoundStock(
        projection,
        (hu,),
        (),
        (BaselinePlacement("HU1", hu.sku_id, "slot", "M1"),),
        rows,
        "source-stock",
        b"{}",
        "stock",
    )


def _candidate(common: CompiledCoordinatorProfile) -> PlacementCandidate:
    actor = next(a for a in common.profile.world.receipts.flow.actors if a.actor_id == "S01")
    buffer = {
        "place_id": "whole-buffer",
        "port_id": "OUT_W_RETAIL",
        "zone_id": "ZONE",
        "bounds_xz": ["0", "0", "1", "1"],
        "path_xz": [["0", "0"], ["1", "0"]],
        "height_m": "1",
        "max_payload_kg": "15",
    }
    customer = PlacementCustomer(
        "predicted-A", "OUT_W_RETAIL", canonical_bytes(buffer), 1_000_000, 1_000_000, 25_000_000
    )
    return PlacementCandidate(
        "HU1",
        "slot",
        "target",
        PlacementActor("S01", actor.home, actor.speed_m_s, actor.max_gross_kg),
        2_000_000,
        1_000_000,
        customer,
    )


def _placement_choices(
    common: CompiledCoordinatorProfile, relocation: RelocationProfile, candidate: PlacementCandidate
) -> PlacementChoices:
    return PlacementChoices(
        "explicit-hand",
        (candidate,),
        ("S01",),
        relocation.route_policy,
        relocation.min_width_m,
        relocation.min_height_m,
        common.profile.world.receipts.flow.path_clearance_m or F(0),
        (),
    )


def _decision(
    common: CompiledCoordinatorProfile, relocation: RelocationProfile
) -> ForecastPlacementDecision:
    stock = _stock(common)
    candidate = _candidate(common)
    choices = _placement_choices(common, relocation, candidate)
    steps = plan_relocations(relocation)[0].steps
    operations = tuple(
        PlacementOperation(s.kind, F(s.duration, 1_000_000), s.duration, s.route) for s in steps
    )
    # Positive selected branch is only an upstream-loader double, not a source cost claim.
    cost = PlacementCost(operations, (), (), 13_000_000, 20_000_000, 0, 20_000_000, 7_000_000)
    evaluation = PlacementEvaluation(
        candidate,
        stock.original_stock[0],
        stock.allocations[0].offer,
        "evaluated",
        ("NET_COST_IMPROVEMENT",),
        cost,
    )
    raw = canonical_bytes(
        {
            "fixture": "authenticated-loader-double",
            "all_offers": record(stock.allocations),
            "all_placements": record(stock.initial_placements),
        }
    )
    return ForecastPlacementDecision(
        stock,
        "forecast",
        "projection",
        "stock",
        choices,
        (evaluation,),
        candidate,
        False,
        "NET_COST_IMPROVEMENT",
        stock.initial_placements,
        b"{}",
        raw,
        sha256(raw).hexdigest(),
    )


@pytest.fixture
def case(monkeypatch: pytest.MonkeyPatch) -> BridgeCase:
    common, relocation = _common()
    item = BridgeCase(common, _decision(common, relocation), relocation, [])

    def load_decision(raw: bytes) -> ForecastPlacementDecision:
        assert raw == item.decision.frozen_bytes
        return item.decision

    def load_common(raw: bytes) -> CompiledCoordinatorProfile:
        assert raw == item.common.frozen_bytes
        return item.common

    def bind(raw: bytes, choices: RelocationChoices) -> BoundRelocation:
        assert raw == item.common.frozen_bytes
        item.calls.append(choices)
        profile = replace(item.relocation, jobs=choices.jobs)
        frozen = canonical_bytes({"common_inputs": parse_json(raw), "choices": record(choices)})
        return BoundRelocation(
            profile, plan_relocations(profile), choices, raw, frozen, sha256(frozen).hexdigest()
        )

    def pair(
        left: BoundRelocation, right: BoundRelocation, *, scenario: str
    ) -> PreparedRelocationPair:
        assert scenario == "N1" and left.common_inputs == right.common_inputs
        frozen = canonical_bytes(
            {"baseline": parse_json(left.frozen_bytes), "candidate": parse_json(right.frozen_bytes)}
        )
        return PreparedRelocationPair(
            "N1", left, right, common.input_hash, frozen, sha256(frozen).hexdigest()
        )

    monkeypatch.setattr(bridge, "load_forecast_placement_decision", load_decision)
    monkeypatch.setattr(bridge, "load_coordinator_inputs", load_common)
    monkeypatch.setattr(bridge, "bind_relocation_source", bind)
    monkeypatch.setattr(bridge, "prepare_relocation_pair", pair)
    return item


def prepare(case: BridgeCase) -> Any:
    return bridge.prepare_forecast_relocation(
        case.decision.frozen_bytes,
        case.common.frozen_bytes,
        ForecastRelocationChoices("MOVE-ACTUAL", 7),
    )


def test_selected_maps_once_without_rewriting_actual_or_predicted_work(case: BridgeCase) -> None:
    value = prepare(case)
    assert len(case.calls) == 2
    assert case.calls[0].jobs == ()
    job = case.calls[1].jobs[0]
    assert (job.job_id, job.arrival_tick, job.hu_id) == ("MOVE-ACTUAL", 7, "HU1")
    assert (job.take_ticks, job.place_ticks) == (2_000_000, 1_000_000)
    assert value.common_inputs == case.common.frozen_bytes
    assert value.decision.frozen_bytes == case.decision.frozen_bytes
    assert value.decision.stock.allocations[1].offer.port_id == "OUT_E_B2B"
    assert value.decision.stock.allocations[1].status == "unallocated"
    assert value.pair.baseline.common_inputs == value.pair.candidate.common_inputs


def test_negative_raw_candidate_is_not_executed(case: BridgeCase) -> None:
    evaluation = case.decision.evaluations[0]
    assert evaluation.cost is not None
    negative = replace(
        evaluation,
        cost=replace(evaluation.cost, net_saving_ticks=-6_000_000),
        reasons=("NET_COST_NOT_BETTER",),
    )
    case.decision = replace(
        case.decision,
        selected=None,
        no_op=True,
        evaluations=(negative,),
        selection_reason="NET_COST_NOT_BETTER",
    )
    value = prepare(case)
    assert [row.jobs for row in case.calls] == [(), ()]
    assert value.decision.evaluations[0].cost == negative.cost
    assert value.pair.baseline.frozen_bytes == value.pair.candidate.frozen_bytes


def test_no_candidate_is_legitimate(case: BridgeCase) -> None:
    case.decision = replace(
        case.decision,
        selected=None,
        no_op=True,
        evaluations=(),
        choices=replace(case.decision.choices, candidates=()),
    )
    prepare(case)
    assert [row.jobs for row in case.calls] == [(), ()]


def test_equivalent_buffer_decimal_lexemes_keep_exact_geometry(case: BridgeCase) -> None:
    candidate = case.decision.selected
    assert candidate is not None and candidate.customer is not None
    buffer = parse_json(candidate.customer.buffer_choice)
    buffer["height_m"] = "1.00"
    changed = replace(
        candidate, customer=replace(candidate.customer, buffer_choice=canonical_bytes(buffer))
    )
    case.decision = replace(
        case.decision,
        selected=changed,
        evaluations=(replace(case.decision.evaluations[0], candidate=changed),),
    )
    prepare(case)


def test_actual_relocation_route_must_match_priced_plan(case: BridgeCase) -> None:
    evaluation = case.decision.evaluations[0]
    assert evaluation.cost is not None
    operation = evaluation.cost.relocation[0]
    wrong = replace(operation, ticks=operation.ticks + 1)
    cost = replace(evaluation.cost, relocation=(wrong, *evaluation.cost.relocation[1:]))
    case.decision = replace(case.decision, evaluations=(replace(evaluation, cost=cost),))
    with pytest.raises(ValueError):
        prepare(case)


def test_noop_forecasts_have_distinct_outer_identity_and_same_native_pair(case: BridgeCase) -> None:
    case.decision = replace(case.decision, selected=None, no_op=True)
    first = prepare(case)
    raw = canonical_bytes({"fixture": "different-authenticated-forecast-double"})
    case.decision = replace(
        case.decision, forecast_id="second", frozen_bytes=raw, input_hash=sha256(raw).hexdigest()
    )
    second = prepare(case)
    assert first.input_hash != second.input_hash
    assert first.pair.frozen_bytes == second.pair.frozen_bytes


@pytest.mark.parametrize("mismatch", ["horizon", "source"])
def test_noop_still_requires_common_source_and_horizon(case: BridgeCase, mismatch: str) -> None:
    case.decision = replace(case.decision, selected=None, no_op=True)
    if mismatch == "horizon":
        case.common = replace(case.common, horizon_tick=900_000_000)
    else:
        stock = case.decision.stock
        source = replace(stock.projection.source, source_revision="different-source")
        projection = replace(stock.projection, source=source)
        case.decision = replace(case.decision, stock=replace(stock, projection=projection))
    with pytest.raises(ValueError):
        prepare(case)
    assert not case.calls


def test_correlated_valid_noop_arm_substitution_is_rejected(case: BridgeCase) -> None:
    selected = prepare(case)
    case.decision = replace(case.decision, selected=None, no_op=True)
    noop = prepare(case)
    # Both pairs were independently prepared; only the selected pair belongs to this decision.
    case.decision = selected.decision
    wire = parse_json(selected.frozen_bytes)
    wire["pair_inputs"] = parse_json(noop.pair.frozen_bytes)
    wire["pair_input_hash"] = noop.pair.input_hash
    with pytest.raises(ValueError):
        bridge.load_forecast_relocation(canonical_bytes(wire))


@pytest.mark.parametrize(
    "field,value", [("home", "other"), ("speed_m_s", F(2)), ("max_gross_kg", F(99))]
)
def test_actor_drift_rejects(case: BridgeCase, field: str, value: Any) -> None:
    flow = case.common.profile.world.receipts.flow
    actors = tuple(replace(a, **{field: value}) if a.actor_id == "S01" else a for a in flow.actors)
    profile = replace(
        case.common.profile,
        world=replace(
            case.common.profile.world,
            receipts=replace(case.common.profile.world.receipts, flow=replace(flow, actors=actors)),
        ),
    )
    case.common = replace(case.common, profile=profile)
    with pytest.raises(ValueError):
        prepare(case)
    assert not case.calls


def test_horizon_900_cannot_use_forecast_1000(case: BridgeCase) -> None:
    case.common = replace(case.common, horizon_tick=900_000_000)
    with pytest.raises(ValueError, match="horizon"):
        prepare(case)
    assert not case.calls


@pytest.mark.parametrize("field", ["source", "lot", "units", "mass", "owner"])
def test_common_source_and_stock_drift_reject(case: BridgeCase, field: str) -> None:
    flow = case.common.profile.world.receipts.flow
    stock = flow.stock
    if field == "source":
        flow = replace(flow, source_hashes=(("hand-source.json", "b" * 64),))
    elif field in {"lot", "units"}:
        unit = replace(stock.units[0], lot_id="foreign") if field == "lot" else stock.units[0]
        units = (unit, *stock.units[1:]) if field == "lot" else stock.units[:-1]
        flow = replace(flow, stock=replace(stock, units=units))
    else:
        container = stock.containers[0]
        container = (
            replace(container, owner_id="foreign")
            if field == "owner"
            else replace(container, recipe=replace(container.recipe, tare_kg=F(99)))
        )
        flow = replace(flow, stock=replace(stock, containers=(container,)))
    profile = replace(
        case.common.profile,
        world=replace(
            case.common.profile.world,
            receipts=replace(case.common.profile.world.receipts, flow=flow),
        ),
    )
    case.common = replace(case.common, profile=profile)
    with pytest.raises(ValueError):
        prepare(case)
    assert not case.calls


def test_outer_roundtrip_rejects_rehash_and_retained_alias(case: BridgeCase) -> None:
    value = prepare(case)
    assert bridge.load_forecast_relocation(value.frozen_bytes) == value
    wire = parse_json(value.frozen_bytes)
    wire["forecast_id"] = "foreign"
    with pytest.raises(ValueError):
        bridge.load_forecast_relocation(canonical_bytes(wire))
    with pytest.raises(ValueError):
        bridge.verify_forecast_relocation(
            replace(value, choices=ForecastRelocationChoices("MOVE-ACTUAL", True))
        )


@pytest.mark.parametrize("arrival", [True, F(7), -1])
def test_choice_tick_alias_rejects_before_load(case: BridgeCase, arrival: Any) -> None:
    with pytest.raises(ValueError):
        bridge.prepare_forecast_relocation(
            case.decision.frozen_bytes,
            case.common.frozen_bytes,
            ForecastRelocationChoices("MOVE-ACTUAL", arrival),
        )
    assert not case.calls
