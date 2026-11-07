"""P0 status and KPI windows, with hand-calculated fixture expectations."""

from pathlib import Path
from typing import Any, cast

import pytest

from app.contracts.loader import ContractBundle
from app.exporter.metrics import project_metrics
from app.simulation.engine import Engine, RunStatus, Termination
from app.simulation.metrics_summary import summary
from app.simulation.recorder import RecorderError
from app.simulation.scheduler import Phase
from tests.builders import fixture_order, receipt, run_inputs, scenario

pytestmark = pytest.mark.acceptance


def test_legacy_export_counters_share_the_horizon_window(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = Engine(
        run_inputs(bundle, contracts_dir, scenario([fixture_order()], horizon_s=10)),
        check_invariants=True,
    )
    outcome = engine.run()
    legacy = project_metrics(engine, outcome)
    windows = cast(dict[str, Any], summary(engine, outcome))
    assert legacy["dispatched_total"] == 0
    assert legacy["backlog_at_horizon"] == 1
    assert legacy["mean_cycle_s"] is None
    assert windows["at_horizon"]["dispatched_total"] == 0
    assert windows["at_end"]["dispatched_total"] == 1
    assert windows["at_end"]["cycle"]["mean_s"] == 469.0


def test_deadlock_precedes_deadline_and_stockout(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    rejected = fixture_order()
    rejected["lines"][0]["quantity"] = 1_000_000
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([rejected], [receipt(i) for i in range(2)], 360),
        reserve_staging_capacity=1,
        receiving_queue_capacity=1,
        max_drain_s=0,
    )
    engine = Engine(inputs, check_invariants=True)
    engine.ctx.sched.schedule(engine.ctx.ticks(400), Phase.COMPLETION, lambda: None)
    outcome = engine.run()
    assert outcome.termination is Termination.DEADLOCK
    assert outcome.termination_reasons == (
        Termination.DEADLOCK,
        Termination.MAX_DRAIN,
        Termination.UNFULFILLED_INVENTORY,
    )
    assert outcome.status is RunStatus.PARTIAL
    assert outcome.subsystems["orders"].status == "partial"
    assert outcome.subsystems["receiving"].status == "blocked"
    assert outcome.subsystems["receiving"].blocked_since_tick == engine.ctx.ticks(360)


def test_receiving_block_does_not_hide_completed_orders(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([fixture_order()], [receipt(i) for i in range(3)]),
        reserve_staging_capacity=1,
        receiving_queue_capacity=1,
    )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    assert outcome.status is RunStatus.PARTIAL
    assert outcome.subsystems["orders"].status == "complete"
    assert outcome.subsystems["receiving"].status == "blocked"
    assert engine.receiving.staging_full_since_tick == engine.ctx.ticks(180)
    assert engine.receiving.putaway_blocked_since_tick == engine.ctx.ticks(360)
    assert engine.receiving.external_blocked_since_tick == engine.ctx.ticks(450)


def test_an_unresolved_arrival_without_future_work_is_not_complete(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = Engine(run_inputs(bundle, contracts_dir, scenario([])), check_invariants=True)
    engine.metrics.order_arrived("LOST", 0)
    outcome = engine.run()
    assert outcome.status is RunStatus.PARTIAL
    assert outcome.termination is Termination.DEADLOCK
    assert outcome.subsystems["orders"].pending_total == 1


def test_failure_retains_error_outcome_and_raises_original_exception(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine = Engine(run_inputs(bundle, contracts_dir, scenario([])), check_invariants=True)

    def fail() -> None:
        raise RecorderError("explicit test failure")

    engine.ctx.sched.schedule(1, Phase.COMPLETION, fail)
    with pytest.raises(RecorderError, match="explicit test failure"):
        engine.run()
    assert engine.last_outcome is not None
    assert engine.last_outcome.status is RunStatus.FAILED
    assert engine.last_outcome.termination_reasons[0] is Termination.ERROR
