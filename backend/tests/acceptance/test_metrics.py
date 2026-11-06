from dataclasses import replace
from pathlib import Path

import pytest

from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.simulation.metrics import Metrics, distribution
from app.simulation.metrics_summary import summary

pytestmark = pytest.mark.acceptance


def test_T5_linear_percentile() -> None:
    assert distribution([10.0, 20.0, 40.0]) == {"mean_s": 70 / 3, "p95_s": 38.0}


def test_T1_undefined_distribution() -> None:
    assert distribution([]) == {"mean_s": None, "p95_s": None}


def test_T2_T3_backlog_includes_rejections() -> None:
    metrics = Metrics()
    metrics.order_arrived("a", 0)
    metrics.order_arrived("b", 2)
    metrics.order_rejected("b", 2)
    metrics.order_dispatched("a", 10)
    at_h = metrics.order_summary(10, 1, inclusive=False)
    assert at_h["backlog"] == 2
    assert at_h["dispatched_total"] == 0
    at_end = metrics.order_summary(10, 1, inclusive=True)
    assert at_end["backlog"] == 1
    assert at_end["completion_rate"] == 0.5
    assert at_end["all_orders_makespan_s"] is None
    assert at_end["rejection_reasons"] == {"unfulfilled_inventory": 1}


def fixture_engine(bundle: ContractBundle, contracts_dir: Path, horizon: int) -> Engine:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    return Engine(
        replace(inputs, scenario=inputs.scenario.model_copy(update={"horizon_s": horizon})),
        check_invariants=True,
    )


def test_K5_K6_T2_fixture_cutoff(bundle: ContractBundle, contracts_dir: Path) -> None:
    engine = fixture_engine(bundle, contracts_dir, 10)
    outcome = engine.run()
    result = summary(engine, outcome)
    shift = engine.metrics.order_summary(outcome.horizon_tick, 3_000_000, inclusive=False)
    assert shift["backlog"] == 1
    assert shift["dispatched_total"] == 0
    assert result["backlog_at_horizon"] == 1
    # P01 works throughout [0,10); the other 11 roster pickers are idle.
    from app.simulation.metrics_summary import utilization

    assert utilization(engine, outcome.horizon_tick)["picker"]["active"] == 1 / 12
    end = engine.metrics.order_summary(outcome.end_tick, 3_000_000, inclusive=True)
    assert end["cycle"] == {"mean_s": 469.0, "p95_s": 469.0}
    assert end["all_orders_makespan_s"] == 469.0


def test_T1_empty_run(bundle: ContractBundle, contracts_dir: Path) -> None:
    engine = fixture_engine(bundle, contracts_dir, 10)
    inputs = engine.ctx.inputs
    engine = Engine(
        replace(inputs, scenario=inputs.scenario.model_copy(update={"orders": (), "receipts": ()})),
        check_invariants=True,
    )
    result = summary(engine, engine.run())
    assert result["backlog_at_horizon"] == 0
    assert engine.metrics.order_summary(10, 1, inclusive=False)["completion_rate"] is None
    from app.simulation.metrics_summary import queue_means

    assert all(value == 0 for value in queue_means(engine, 10).values())


def test_queues_observed_after_dispatch(bundle: ContractBundle, contracts_dir: Path) -> None:
    engine = fixture_engine(bundle, contracts_dir, 100)
    engine.run()
    # One picker and one packer start immediately: no waiting queue at either stage.
    assert all(
        sizes["orders"] == 0 and sizes["pack:PK01"] == 0
        for _, sizes in engine.metrics.queue_samples
    )


def test_T4_cutoff_planned_service(bundle: ContractBundle, contracts_dir: Path) -> None:
    engine = fixture_engine(bundle, contracts_dir, 10)
    inputs = replace(
        engine.ctx.inputs, config=engine.ctx.config.model_copy(update={"max_drain_s": 0})
    )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    assert outcome.termination.value == "max_drain"
    assert outcome.end_tick == outcome.horizon_tick
    from app.simulation.metrics_summary import utilization

    assert utilization(engine, outcome.end_tick)["picker"]["active"] == 1 / 12
    assert engine.metrics.counts()["dispatched_total"] == 0


def test_T6_offered_load_preserved() -> None:
    metrics = Metrics()
    for index in range(600):
        metrics.order_arrived(str(index), index * 6)
    for index in range(100):
        metrics.order_dispatched(str(index), 1000 + index * 6)
    result = metrics.order_summary(3600, 1, inclusive=False)
    assert result["arrived_total"] == 600
    assert result["dispatched_total"] == 100
    assert result["backlog"] == 500
    assert result["completion_rate"] == 1 / 6
    assert result["backlog_max_age_s"] == 3000.0


def test_time_weighted_queue_hand_oracle(bundle: ContractBundle, contracts_dir: Path) -> None:
    from app.simulation.metrics_summary import queue_means

    engine = fixture_engine(bundle, contracts_dir, 10)
    engine.metrics.queue_samples = [(0, {"orders": 2}), (3, {"orders": 1}), (7, {"orders": 0})]
    assert queue_means(engine, 10)["orders"] == 1.0  # (2*3 + 1*4)/10
    assert queue_means(engine, 5)["orders"] == 1.6


def test_T4_open_pack_block_excludes_active(bundle: ContractBundle, contracts_dir: Path) -> None:
    from app.simulation.metrics_summary import utilization

    engine = fixture_engine(bundle, contracts_dir, 10)
    station = engine.packing.stations["PK01"]
    station.blocked_parcel = "parcel"
    station.blocked_since = engine.ctx.ticks(4)
    result = utilization(engine, engine.ctx.ticks(10))["packer"]
    assert result["active"] == 0
    assert result["blocked"] == 0.1  # 6 seconds / (6 roster packers * 10 seconds)


def test_T4_open_induction_block_at_deadline(bundle: ContractBundle, contracts_dir: Path) -> None:
    from app.simulation.metrics_summary import utilization

    inputs = fixture_engine(bundle, contracts_dir, 10).ctx.inputs
    inputs = replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": 32.9}),
        config=inputs.config.model_copy(update={"max_drain_s": 0}),
    )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    assert outcome.termination.value == "max_drain"
    result = utilization(engine, outcome.end_tick)["picker"]
    assert result["blocked"] == pytest.approx(0.1 / (12 * 32.9))
    assert result["active"] == pytest.approx(32.8 / (12 * 32.9))


def test_T3_rejected_run_is_partial(bundle: ContractBundle, contracts_dir: Path) -> None:
    inputs = fixture_engine(bundle, contracts_dir, 10).ctx.inputs
    order = inputs.scenario.orders[0]
    lines = tuple(line.model_copy(update={"quantity": 1000000}) for line in order.lines)
    order = order.model_copy(update={"lines": lines})
    inputs = replace(inputs, scenario=inputs.scenario.model_copy(update={"orders": (order,)}))
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    assert outcome.status.value == "partial"
    assert outcome.termination.value == "unfulfilled_inventory"
    result = engine.metrics.order_summary(outcome.end_tick, 3_000_000, inclusive=True)
    assert result["backlog"] == 1
    assert result["all_orders_makespan_s"] is None
    assert result["completion_rate"] == 0.0
