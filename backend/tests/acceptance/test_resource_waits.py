"""One tote and two fixture orders: hand-derived wait ends at the first pack completion."""

import dataclasses
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from app.comparison.compare import _run
from app.contracts.loader import ContractBundle
from app.exporter.identity import fingerprint
from app.simulation.engine import Engine, RunOutcome
from app.simulation.metrics_summary import summary
from app.simulation.resource_waits import derive_resource_waits
from app.storage.canonical_json import sha256_hex
from tests.builders import fixture_order, run_inputs, scenario

pytestmark = pytest.mark.acceptance


@pytest.fixture(scope="module")
def waiting_run(bundle: ContractBundle, contracts_dir: Path) -> tuple[Engine, RunOutcome]:
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([fixture_order(order_id="O1"), fixture_order(order_id="O2")], horizon_s=60),
        totes_total=1,
    )
    engine = Engine(inputs, check_invariants=True)
    return engine, engine.run()


def test_wait_is_one_picker_per_queued_order_and_not_active_labor(
    waiting_run: tuple[Engine, RunOutcome],
) -> None:
    engine, outcome = waiting_run
    result = cast(dict[str, Any], summary(engine, outcome))
    horizon, end = result["at_horizon"], result["at_end"]
    # Fixture P01 is busy until induction33. P02 waits[0,33), then lowest idle P01
    # waits[33,76.1), when packing[52,76.1) returns the only tote. Other pickers stay idle.
    assert horizon["picker_metrics"]["P02"]["wait_resource_s"] == 33
    assert horizon["picker_metrics"]["P01"]["wait_resource_s"] == 27
    assert horizon["labor_by_role"]["picker"]["wait_resource_s"] == 60
    assert horizon["labor_by_role"]["picker"]["active_s"] == pytest.approx(32.8)
    assert end["labor_by_role"]["picker"]["wait_resource_s"] == pytest.approx(76.1)
    roles = horizon["utilization_by_role"]
    assert roles["picker"]["wait_resource"] == pytest.approx(60 / (12 * 60))
    assert all(sum(states.values()) == pytest.approx(1) for states in roles.values())


@pytest.mark.parametrize(
    ("cutoff", "expected"),
    [
        (Fraction(0), [("P02", 0, 0, True)]),
        (Fraction(33), [("P02", 0, 33, False), ("P01", 33, 33, True)]),
        (Fraction(60), [("P02", 0, 33, False), ("P01", 33, 60, True)]),
        (Fraction(761, 10), [("P02", 0, 33, False), ("P01", 33, 76.1, False)]),
    ],
)
def test_wait_clips_are_exact_and_boundary_descriptors_have_no_elapsed_time(
    waiting_run: tuple[Engine, RunOutcome],
    cutoff: Fraction,
    expected: list[tuple[str, float, float, bool]],
) -> None:
    engine, _ = waiting_run
    tps = engine.ctx.grid.ticks_per_second
    waits = derive_resource_waits(engine, engine.ctx.ticks(cutoff))
    assert [
        (w.actor_id, w.start_tick / tps, w.end_tick / tps, w.open_ended) for w in waits
    ] == expected
    assert all(w.reason == "tote_unavailable" for w in waits)


def test_comparison_and_core_share_the_same_wait_totals(
    waiting_run: tuple[Engine, RunOutcome],
) -> None:
    inputs = waiting_run[0].ctx.inputs
    result = _run("baseline", inputs, fingerprint(inputs), None)
    assert result.at_horizon.total_wait_resource_s == 60
    assert result.at_end.total_wait_resource_s == pytest.approx(76.1)
    assert result.at_horizon.by_role["picker"].labor_s == pytest.approx(32.8)
    assert result.side.metrics["at_horizon"]["labor_by_role"]["picker"]["wait_resource_s"] == 60


def test_open_induction_block_is_never_counted_as_idle_tote_wait(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([fixture_order(order_id="O1"), fixture_order(order_id="O2")], horizon_s=32),
        totes_total=1,
        max_drain_s=0.9,
    )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    waits = derive_resource_waits(engine, outcome.end_tick)
    assert [(w.actor_id, w.start_tick, w.end_tick, w.open_ended) for w in waits] == [
        ("P02", 0, engine.ctx.ticks(Fraction(329, 10)), True)
    ]
    end = cast(dict[str, Any], summary(engine, outcome))["at_end"]
    assert end["picker_metrics"]["P01"]["blocked_s"] == pytest.approx(0.1)
    assert end["picker_metrics"]["P01"]["wait_resource_s"] == 0


def test_wait_count_respects_counterfactual_fifo_inventory(
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([fixture_order(order_id=f"O{i}") for i in range(3)], horizon_s=60),
        totes_total=1,
    )
    assignment = inputs.assignment.model_copy(
        update={
            "initial_lots": tuple(
                lot.model_copy(update={"quantity": 2}) for lot in inputs.assignment.initial_lots
            )
        }
    )
    engine = Engine(dataclasses.replace(inputs, assignment=assignment), check_invariants=True)
    engine.run()
    # First order reserves one unit of each SKU; only one of two queued orders can reserve the rest.
    waits = derive_resource_waits(engine, engine.ctx.ticks(Fraction(10)))
    assert [(wait.actor_id, wait.end_tick - wait.start_tick) for wait in waits] == [
        ("P02", engine.ctx.ticks(Fraction(10)))
    ]


def test_derivation_preserves_journals_and_rejects_negative_cutoff(
    waiting_run: tuple[Engine, RunOutcome],
) -> None:
    engine, outcome = waiting_run

    def digest() -> str:
        return sha256_hex(
            {
                "events": [dataclasses.asdict(event) for event in engine.ctx.recorder.events],
                "actions": [dataclasses.asdict(action) for action in engine.ctx.recorder.actions],
            }
        )

    before = digest()
    derive_resource_waits(engine, outcome.horizon_tick)
    derive_resource_waits(engine, outcome.end_tick)
    assert digest() == before
    with pytest.raises(ValueError, match="non-negative"):
        derive_resource_waits(engine, -1)
