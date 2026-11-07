"""Actual pinned V3 source plus explicit four-job proposal traverses the complete wire seam."""

from pathlib import Path

from app.v3.execution import ManualEngine
from app.v3.profile import load_manual_profile
from app.v3.run_export import build_manual_run
from app.v3.run_replay import replay_manual
from app.v3.run_transport import read_manual_run, seek_manual_run, write_manual_run


def test_actual_source_four_jobs_preserve_530_baseline_hus_and_receipt_arithmetic(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    inputs = load_manual_profile(
        root / "data/v3-proposal", root / "data/v3-execution-proposals/manual-whole-hu-demo-v1.json"
    )
    outcome = ManualEngine(inputs.profile, inputs.graph, check_invariants=True).run(
        inputs.horizon_tick, inputs.end_tick
    )
    run = build_manual_run(
        inputs.profile,
        inputs.graph,
        outcome,
        graph_document=inputs.graph_document.decode(),
        end_tick_limit=inputs.end_tick,
    )
    # Pinned baseline12256 + two explicit whole24-unit receipts - two24-unit shipments.
    assert sum(row[1] for row in run["initial_state"]["stock_units"]) == 12256
    assert len(run["initial_state"]["owners"]) == 532
    assert len(inputs.profile.initial_placements) == 530
    assert sum(row[1] for row in run["at_end"]["stock_units"]) == 12256
    assert sum(row[1] for row in run["at_end"]["shipped_units"]) == 48
    assert run["at_end"]["wip_units"] == run["at_end"]["outside_units"] == []
    assert run["at_end"]["status"] == "complete"
    assert run["metrics"]["at_end"]["inbound"]["completed_hus"] == 2
    assert run["metrics"]["at_end"]["outbound"]["completed_hus"] == 2
    manifest = write_manual_run(run, tmp_path / "run")
    assert manifest["graph_document"]["sha256"] == inputs.graph.sha256
    assert read_manual_run(tmp_path / "run") == run
    assert seek_manual_run(tmp_path / "run", 80_000_000) == replay_manual(run, 80_000_000)
