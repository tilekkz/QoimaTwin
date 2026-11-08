"""Physical inputs must exist before construction, even when execution fails."""

from dataclasses import replace
from pathlib import Path

import pytest

from app.v3.receipt_flow_models import ReceiptFlowOutcome
from app.v3.receipt_run_execute import simulate_receipt
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_receipt_run_fixtures import sample


def test_exact_frozen_inputs_precede_engine_constructor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, outcome = sample()

    class Engine:
        def __init__(self, *args: object) -> None:
            assert (tmp_path / "inputs.json").read_bytes() == inputs.frozen_bytes
            assert not (tmp_path / "manifest.json").exists()

        def run(self, horizon: int, end: int) -> ReceiptFlowOutcome:
            assert (horizon, end) == (300_000_000, 400_000_000)
            return outcome

    monkeypatch.setattr("app.v3.receipt_run_execute.ReceiptFlowEngine", Engine)
    report = simulate_receipt(inputs, receipt_conveyor(), tmp_path)
    assert report["status"] == "complete" and (tmp_path / "manifest.json").exists()
    assert report["receipt_metrics"]["at_end"]["credited_units"] == 24


def test_failure_retains_inputs_and_never_publishes_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, _ = sample()

    def fail(*args: object) -> None:
        assert (tmp_path / "inputs.json").read_bytes() == inputs.frozen_bytes
        raise RuntimeError("actual engine failure")

    monkeypatch.setattr("app.v3.receipt_run_execute.ReceiptFlowEngine", fail)
    with pytest.raises(RuntimeError, match="actual engine failure"):
        simulate_receipt(inputs, receipt_conveyor(), tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["inputs.json"]
    with pytest.raises(ValueError):
        simulate_receipt(inputs, receipt_conveyor(), tmp_path)


def test_mismatched_typed_profile_fails_before_output_creation(tmp_path: Path) -> None:
    inputs, _ = sample()
    changed = replace(inputs, profile=replace(inputs.profile, place_tick=2_000_000))
    out = tmp_path / "absent"
    with pytest.raises(ValueError, match="frozen"):
        simulate_receipt(changed, receipt_conveyor(), out)
    assert not out.exists()
