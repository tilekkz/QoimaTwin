"""Independent mixed-demand and derived-cost authority controls; no engine execution."""

from collections import Counter
from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import forecast_placement_decision
from app.v3.forecast_placement_decision import (
    load_forecast_placement_decision,
    prepare_forecast_placement_decision,
    verify_forecast_placement_decision,
)
from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.forecast_stock_binding import bind_forecast_stock
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.input_models import V3Bundle
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_projection_inputs import compile_offer_projection
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.outbound_placement_source import source_bundle
from app.v3.workload_models import WorkloadPolicy
from tests.v3.test_forecast_placement_fixtures import choices, source_candidate
from tests.v3.test_offer_history_fixtures import choices as history_choices
from tests.v3.test_offer_history_fixtures import history_bytes


def _mixed_history() -> bytes:
    lines = history_bytes(0, 0).decode().splitlines()
    rows = [lines[0]]
    for line in lines[1:]:
        day, sku, _ = line.split(",")
        count = int(sku in {"DEMO_001", "DEMO_113", "DEMO_172"})
        rows.append(f"{day},{sku},{count}")
    return ("\n".join(rows) + "\n").encode()


@pytest.fixture(scope="module")
def mixed_stock() -> ForecastBoundStock:
    history = compile_offer_history(_mixed_history(), history_choices())
    forecast = fit_offer_forecast(history, "mean28")
    policy = WorkloadPolicy(12_000_000, 0, 12, "normal")
    initial = compile_offer_projection(forecast, OfferProjectionChoices(policy, "source_c10", ()))
    mix = tuple(
        replace(row, weight=F(int(row.port_id == "OUT_S_EXPRESS")))
        if row.sku_id == "DEMO_113"
        else row
        for row in initial.offers.port_mix
    )
    projection = compile_offer_projection(forecast, OfferProjectionChoices(policy, "explicit", mix))
    return bind_forecast_stock(projection)


@pytest.fixture(scope="module")
def evaluated(mixed_stock: ForecastBoundStock) -> ForecastPlacementDecision:
    return prepare_forecast_placement_decision(mixed_stock, choices(source_candidate(mixed_stock)))


def test_mixed_skus_b2b_and_shortages_survive_evaluated_noop(
    mixed_stock: ForecastBoundStock, evaluated: ForecastPlacementDecision
) -> None:
    offers = mixed_stock.projection.offers.jobs
    assert Counter(j.sku_id for j in offers) == {"DEMO_001": 4, "DEMO_113": 4, "DEMO_172": 4}
    assert [j.arrival_tick for j in offers] == [i * 1_000_000 for i in range(12)]
    assert any(j.port_id == "OUT_E_B2B" for j in offers)
    assert any(r.status == "unallocated" for r in mixed_stock.allocations)
    assert evaluated.stock.frozen_bytes == mixed_stock.frozen_bytes
    assert tuple(r.offer for r in evaluated.stock.allocations) == offers
    assert evaluated.stock.declared_receipts == ()
    assert len(evaluated.placements) == 530
    assert evaluated.placements == mixed_stock.initial_placements
    assert evaluated.no_op is True and evaluated.selected is None
    cost = evaluated.evaluations[0].cost
    assert evaluated.evaluations[0].status == "evaluated" and cost is not None
    assert cost.relocation_ticks == 196_160_001
    assert cost.gross_saving_ticks == 140_799_998
    assert cost.net_saving_ticks == -55_360_003
    assert evaluated.actual_test_stream is evaluated.operational_admission is False


def _forge_cost(wire: dict[str, Any], mutation: str) -> None:
    evaluation = wire["evaluations"][0]
    cost = evaluation["cost"]
    if mutation == "route":
        cost["relocation"][0]["route"]["arc_ids"][0] = "invented-source-arc"
    elif mutation == "return":
        returned = cost["relocation"].pop()
        assert returned["kind"] == "relocation_return"
        cost["relocation_ticks"] -= returned["ticks"]
        cost["net_saving_ticks"] += returned["ticks"]
    elif mutation == "net":
        cost["net_saving_ticks"] = 1
        wire["selected"] = wire["choices"]["candidates"][0]
        wire["no_op"] = False
        wire["selection_reason"] = "NET_COST_IMPROVEMENT"
    else:
        original = evaluation["affected_offer"]
        other = next(
            row["offer"]
            for row in wire["stock_inputs"]["allocations"]
            if row["offer"]["sku_id"] == original["sku_id"]
            and row["offer"]["job_id"] != original["job_id"]
        )
        for candidate in (wire["choices"]["candidates"][0], evaluation["candidate"]):
            candidate["customer"]["offer_id"] = other["job_id"]
        evaluation["affected_offer"] = other


@pytest.mark.parametrize("mutation", ["route", "return", "net", "customer"])
def test_rehashed_evaluated_cost_cannot_replace_recomputed_authority(
    evaluated: ForecastPlacementDecision, mutation: str
) -> None:
    wire = parse_json(evaluated.frozen_bytes)
    _forge_cost(wire, mutation)
    raw = canonical_bytes(wire)
    forged = replace(evaluated, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        verify_forecast_placement_decision(forged)


@pytest.mark.parametrize("field", ["operation_seconds", "aggregate_ticks"])
def test_equal_retained_cost_scalar_aliases_reject(
    evaluated: ForecastPlacementDecision, field: str
) -> None:
    evaluation = evaluated.evaluations[0]
    cost = evaluation.cost
    assert cost is not None
    if field == "operation_seconds":
        operation = cost.relocation[1]
        assert operation.kind == "relocation_take" and operation.seconds == F(1)
        alias: Any = 1
        rows = (cost.relocation[0], replace(operation, seconds=alias), *cost.relocation[2:])
        changed = replace(cost, relocation=rows)
    else:
        changed = replace(cost, relocation_ticks=F(cost.relocation_ticks))  # type: ignore[arg-type]
    forged = replace(evaluated, evaluations=(replace(evaluation, cost=changed),))
    assert forged == evaluated
    with pytest.raises(ValueError):
        verify_forecast_placement_decision(forged)


def test_caller_graph_is_not_a_choice(evaluated: ForecastPlacementDecision) -> None:
    wire = parse_json(evaluated.frozen_bytes)
    wire["choices"]["graph"] = {"nodes": [], "arcs": []}
    with pytest.raises(ValueError):
        load_forecast_placement_decision(canonical_bytes(wire))


def test_retained_caller_template_cannot_supply_cost_dimensions(
    evaluated: ForecastPlacementDecision,
) -> None:
    stock = evaluated.stock
    source = stock.projection.source
    templates = tuple(
        replace(t, dimensions_xyz_m=(F(1), F(1), F(1))) if t.sku_id == "DEMO_113" else t
        for t in source.templates
    )
    forged = replace(
        stock, projection=replace(stock.projection, source=replace(source, templates=templates))
    )
    with pytest.raises(ValueError):
        prepare_forecast_placement_decision(forged, evaluated.choices)


def test_physical_graph_source_reopens_after_stock_verification(
    evaluated: ForecastPlacementDecision, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_read = Path.read_bytes
    observed: list[Path] = []

    def changed(path: Path) -> bytes:
        raw = original_read(path)
        if path.name == "layout-links-v3.json":
            observed.append(path)
            return raw + b" "
        return raw

    def changed_only_at_physical_stage() -> V3Bundle:
        with monkeypatch.context() as local:
            local.setattr(Path, "read_bytes", changed)
            return source_bundle()

    monkeypatch.setattr(
        forecast_placement_decision, "source_bundle", changed_only_at_physical_stage
    )
    with pytest.raises(ValueError, match="pinned bytes/SHA256 mismatch"):
        prepare_forecast_placement_decision(evaluated.stock, evaluated.choices)
    assert observed
