"""Independent directed paid-work probes; no scheduler or source execution."""

from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.input_models import V3Bundle
from app.v3.outbound_placement_cost import price_candidate
from app.v3.outbound_placement_decision import (
    load_placement_decision,
    prepare_placement_decision,
    verify_placement_decision,
)
from app.v3.outbound_placement_feasibility import _capacity
from app.v3.outbound_placement_models import (
    N1PlacementDecision,
    PlacementActor,
    PlacementCandidate,
    PlacementChoices,
    PlacementCostFacts,
)
from app.v3.outbound_shift_inputs import compile_outbound_shift
from app.v3.outbound_stock_binding import bind_outbound_stock
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.whole_profile_geometry import ROUTE_POLICY
from app.v3.workload_models import WorkloadPolicy


def _graph(rows: tuple[tuple[str, str, F], ...]) -> DirectedGraph:
    nodes = tuple(sorted({node for a, b, _ in rows for node in (a, b)}))
    arcs = tuple(
        Arc(
            f"peer-{index}",
            a,
            b,
            length,
            length,
            modes=frozenset({"pedestrian"}),
            cargo_classes=frozenset({"STANDARD_CARTON"}),
            clear_width_m=F(2),
            clear_height_m=F(3),
        )
        for index, (a, b, length) in enumerate(rows)
    )
    return DirectedGraph("independent-directed-hand", nodes, arcs)


def _facts() -> PlacementCostFacts:
    return PlacementCostFacts(
        PlacementActor("S01", "h", F(1), F(10)),
        "s",
        "t",
        "h",
        "h",
        "STANDARD_CARTON",
        (F(".6"), F(".4"), F(".3")),
        1000000,
        1000000,
        1000000,
        1000000,
        2000000,
        F(".7"),
        F("1.8"),
        F(".02"),
    )


def _asymmetric() -> DirectedGraph:
    return _graph(
        (("h", "s", F(6)), ("h", "t", F(1)), ("s", "t", F(7)), ("t", "h", F(2)), ("s", "h", F(9)))
    )


def test_directed_return_is_paid_and_not_inferred_from_outbound_leg() -> None:
    cost = price_candidate(_asymmetric(), _facts())
    assert (cost.baseline_ticks, cost.adapted_ticks) == (20000000, 8000000)
    assert (cost.gross_saving_ticks, cost.relocation_ticks, cost.net_saving_ticks) == (
        12000000,
        17000000,
        -5000000,
    )
    assert cost.relocation[-1].route is not None
    assert cost.relocation[-1].route.node_ids == ("t", "h")
    assert cost.relocation[-1].seconds == F(2)


def test_round_whole_travel_not_each_internal_arc() -> None:
    piece = F(1, 2500000)  # 0.4 microseconds per arc.
    graph = _graph(
        (
            ("h", "x", piece),
            ("x", "s", piece),
            ("s", "t", piece),
            ("t", "h", piece),
            ("h", "t", piece),
        )
    )
    facts = replace(
        _facts(),
        take_ticks=1,
        place_ticks=1,
        pickup_ticks=1,
        customer_place_ticks=1,
        service_ticks=1,
    )
    cost = price_candidate(graph, facts)
    approach = cost.relocation[0]
    assert approach.route is not None and len(approach.route.arc_ids) == 2
    assert approach.seconds == F(1, 1250000) and approach.ticks == 1
    assert (cost.baseline_ticks, cost.adapted_ticks, cost.relocation_ticks) == (6, 6, 5)
    assert cost.net_saving_ticks == -5


def test_loaded_shortcut_must_satisfy_cargo_and_clearance_together() -> None:
    graph = _asymmetric()
    shortcut = Arc(
        "denied-shortcut",
        "s",
        "h",
        F(1),
        F(1),
        modes=frozenset({"pedestrian"}),
        cargo_classes=frozenset({"STANDARD_CARTON"}),
        clear_width_m=F(".63"),
        clear_height_m=F(3),
    )
    cost = price_candidate(
        DirectedGraph(graph.graph_id, graph.node_ids, (*graph.arcs, shortcut)), _facts()
    )
    loaded = next(op for op in cost.baseline if op.kind == "whole_carry_buffer")
    assert loaded.route is not None and "denied-shortcut" not in loaded.route.arc_ids
    assert loaded.seconds == F(9)


@pytest.mark.parametrize(
    "field,value",
    [
        ("take_ticks", F(1000000)),
        ("service_ticks", True),
        ("dimensions", (F(".6"), F(".4"), 0.3)),
        ("min_width_m", 0.7),
    ],
)
def test_cost_facts_do_not_accept_equal_numeric_aliases(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        price_candidate(_asymmetric(), replace(_facts(), **{field: value}))


def test_actor_speed_is_an_exact_fraction_even_when_integer_is_equal() -> None:
    actor = replace(_facts().actor, speed_m_s=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        price_candidate(_asymmetric(), replace(_facts(), actor=actor))


def test_weighted_shortcut_cannot_manufacture_positive_paid_saving() -> None:
    graph = _graph(
        (("h", "s", F(6)), ("h", "t", F(1)), ("s", "t", F(1)), ("t", "h", F(1)), ("s", "h", F(100)))
    )
    costs = {
        ("h", "s"): F(6),
        ("h", "t"): F(100),
        ("s", "t"): F(10),
        ("t", "h"): F(10),
        ("s", "h"): F(1),
    }
    weighted = DirectedGraph(
        graph.graph_id,
        graph.node_ids,
        tuple(replace(a, cost_m=costs[a.source, a.target]) for a in graph.arcs),
    )
    try:
        cost = price_candidate(weighted, _facts())
    except ValueError:
        return
    pytest.fail(
        f"Non-V3 route metric accepted: gross={cost.gross_saving_ticks}, "
        f"transfer={cost.relocation_ticks}, net={cost.net_saving_ticks}"
    )


@pytest.mark.parametrize(
    "limit,reason", [("count", "MODULE_HU_CAPACITY"), ("mass", "MODULE_PAYLOAD")]
)
def test_declared_receipts_cannot_overload_an_unrelated_module(
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    reason: str,
) -> None:
    # This isolates static arithmetic, not source binding or a forged public decision.
    slots = {s: {"module_id": m} for s, m in (("s", "S"), ("t", "T"), ("r1", "R"), ("r2", "R"))}
    modules = [
        {"module_id": m, "max_handling_units": 10, "max_module_payload_kg": 100}
        for m in ("S", "T", "R")
    ]
    if limit == "count":
        modules[-1]["max_handling_units"] = 1
    else:
        modules[-1]["max_module_payload_kg"] = 1
    monkeypatch.setattr(
        "app.v3.outbound_placement_feasibility.document",
        lambda _bundle, _name: {"modules": modules},
    )
    candidate = PlacementCandidate("hand-HU", "s", "t", _facts().actor, 1, 1, None)
    residents: list[tuple[str | None, F]] = [("s", F(1)), ("t", F(1)), ("r1", F(1)), ("r2", F(1))]
    assert _capacity(cast(V3Bundle, None), slots, residents, candidate) == (reason,)


@pytest.fixture(scope="module")
def receipt_decision() -> N1PlacementDecision:
    # Actual pinned input compilation only. It does not create or run an engine.
    root = Path(__file__).resolve().parents[2] / "data"
    inputs = compile_outbound_shift(
        root / "v3-proposal",
        root / "v3-adaptation-proposal",
        WorkloadPolicy(1000000000, 1, 1500, "normal"),
    )
    stock = bind_outbound_stock(inputs)
    candidate = PlacementCandidate(
        "v3:HU:initial:DEMO_113:01",
        "v3:slot:STANDARD_W:004:L1:B1",
        "v3:slot:FLEX_W:003:L1:B1",
        PlacementActor("S01", "v3:service:OUT_S_EXPRESS", F(1), F(10)),
        1000000,
        1000000,
        None,
    )
    choices = PlacementChoices(
        "peer-missing-receipt-destination",
        (candidate,),
        ("S01",),
        ROUTE_POLICY,
        F(".7"),
        F("1.8"),
        F(".02"),
        (),
    )
    before = inputs.workload_bytes, stock.frozen_bytes
    result = prepare_placement_decision(stock, choices)
    assert (inputs.workload_bytes, stock.frozen_bytes) == before
    return result


def test_missing_receipt_destination_preserves_every_offer_and_noop(
    receipt_decision: N1PlacementDecision,
) -> None:
    result = receipt_decision
    evaluation = result.evaluations[0]
    assert evaluation.status == "not_evaluable" and evaluation.cost is None
    assert evaluation.reasons == ("MISSING_RECEIPT_PLACEMENT_BINDING",)
    assert result.no_op and result.selected is None
    assert result.placements == result.stock.inputs.scenario.initial_placements
    jobs = result.stock.inputs.workload.jobs
    assert tuple(row.offer for row in result.stock.allocations) == tuple(
        job for job in jobs if job.direction == "outbound"
    )
    assert {job.port_id for job in jobs if job.direction == "outbound"} == {
        "OUT_W_RETAIL",
        "OUT_S_EXPRESS",
        "OUT_E_B2B",
    }
    candidate_hu = result.choices.candidates[0].hu_id
    assert (
        sum(row.hu is not None and row.hu.hu_id == candidate_hu for row in result.stock.allocations)
        == 1
    )


@pytest.mark.parametrize("tamper", ["arrival", "duplicated_hu", "graph"])
def test_rehashed_stock_changes_cannot_redefine_placement_authority(
    receipt_decision: N1PlacementDecision,
    tamper: str,
) -> None:
    wire = parse_json(receipt_decision.frozen_bytes)
    stock = wire["stock_inputs"]
    if tamper == "arrival":
        stock["allocations"][0]["offer"]["arrival_tick"] += 1
    elif tamper == "duplicated_hu":
        stock["allocations"][1]["hu"] = stock["allocations"][0]["hu"]
    else:
        shift = stock["shift_inputs"]
        scenario = shift["scenario"]
        fake_graph_hash = sha256(canonical_bytes({"graph_id": "walk", "arcs": []})).hexdigest()
        for source in (scenario["baseline"], scenario["postshift"], shift["workload"]["source"]):
            rows = [
                row for row in source["raw_fingerprints"] if row[0].endswith("layout-links-v3.json")
            ]
            assert rows
            for row in rows:
                row[1] = fake_graph_hash
        scenario["scenario_hash"] = sha256(
            canonical_bytes({k: v for k, v in scenario.items() if k != "scenario_hash"})
        ).hexdigest()
        stock["shift_input_hash"] = sha256(canonical_bytes(shift)).hexdigest()
    wire["stock_input_hash"] = sha256(canonical_bytes(stock)).hexdigest()
    raw = canonical_bytes(wire)
    with pytest.raises(ValueError):
        load_placement_decision(raw)
    with pytest.raises(ValueError):
        verify_placement_decision(
            replace(receipt_decision, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())
        )


@pytest.mark.parametrize("alias", [True, 1.0])
def test_rehashed_nested_actor_rational_alias_is_not_one(
    receipt_decision: N1PlacementDecision,
    alias: Any,
) -> None:
    wire = parse_json(receipt_decision.frozen_bytes)
    wire["choices"]["candidates"][0]["actor"]["speed_m_s"] = [alias, 1]
    with pytest.raises(ValueError):
        load_placement_decision(canonical_bytes(wire))
