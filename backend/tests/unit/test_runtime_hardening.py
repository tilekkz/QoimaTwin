"""Runtime regressions from the 2026-11-07 backend task, with hand-derived inputs."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.data.scenario_materializer import materialize
from app.exporter.run import export_run, write_run
from app.simulation.checkpoint import Checkpointer
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.simulation.scheduler import Phase, PhaseScheduler


def test_explicit_rank_precedes_actor_identifier() -> None:
    scheduler = PhaseScheduler()
    seen: list[str] = []
    scheduler.schedule(1, Phase.COMPLETION, lambda: seen.append("age"), key=("a",), rank=1)
    scheduler.schedule(1, Phase.COMPLETION, lambda: seen.append("scan"), key=("z",), rank=0)
    scheduler.run()
    assert seen == ["scan", "age"]


def test_cancelled_unique_slot_can_be_replaced() -> None:
    scheduler = PhaseScheduler()
    seen: list[str] = []
    scheduler.schedule(5, Phase.ARRIVAL, lambda: seen.append("old"), unique="arrival").cancel()
    scheduler.schedule(5, Phase.ARRIVAL, lambda: seen.append("new"), unique="arrival")
    assert scheduler.pending_count() == 1
    assert scheduler.peek_next_tick() == 5
    scheduler.run()
    assert seen == ["new"]
    assert scheduler.pending_count() == 0


@pytest.mark.parametrize("seconds,orders,receipts", [(600, 40, 3), (900, 60, 5)])
def test_shortened_profiles_keep_hourly_intensity(
    bundle: ContractBundle, seconds: int, orders: int, receipts: int
) -> None:
    result = materialize("large-normal", seconds, bundle.config)
    assert len(result.scenario.orders) == orders
    assert len(result.scenario.receipts) == receipts
    assert result.scenario.orders[0].arrival_s == 7.5
    assert result.scenario.orders[-1].arrival_s == seconds - 7.5
    assert "shortened_run=true" in result.scenario.provenance.source_notes


def test_invariants_respect_configured_tote_pool(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    engine = Engine(
        replace(inputs, config=inputs.config.model_copy(update={"totes_total": 2})),
        check_invariants=True,
    )
    engine.run()
    assert sorted(engine.picking.free_totes) == ["T001", "T002"]


def test_unarmed_checkpoint_raises_under_optimized_python() -> None:
    checkpoint = Checkpointer(30, lambda tick: {"tick": tick}, lambda: -1)
    with pytest.raises(RuntimeError, match="begin"):
        checkpoint._emit_before(1)


@pytest.fixture(scope="module")
def projected(bundle: ContractBundle, contracts_dir: Path) -> dict[str, Any]:
    engine = Engine(fixture_inputs(bundle, load_fixture(contracts_dir)), check_invariants=True)
    return export_run(engine, engine.run())


def test_export_refuses_existing_content(projected: dict[str, Any], tmp_path: Path) -> None:
    stale = tmp_path / "stale.json"
    stale.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        write_run(projected, tmp_path)
    assert stale.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "manifest.json").exists()


def test_export_uses_configured_chunk_size(projected: dict[str, Any], tmp_path: Path) -> None:
    manifest = write_run(projected, tmp_path, chunk_duration_s=120, snapshot_interval_s=15)
    assert manifest["chunk_duration_s"] == 120
    assert manifest["snapshot_interval_s"] == 15
    assert [(c["start_s"], c["end_s"]) for c in manifest["chunks"]] == [
        (0, 120),
        (120, 240),
        (240, 360),
        (360, 480),
    ]


def test_export_accepts_exact_fractional_intervals(
    projected: dict[str, Any], tmp_path: Path
) -> None:
    manifest = write_run(projected, tmp_path, chunk_duration_s=120.5, snapshot_interval_s=15.5)
    assert manifest["chunks"][1]["start_s"] == 120.5
    assert manifest["snapshot_interval_s"] == 15.5
