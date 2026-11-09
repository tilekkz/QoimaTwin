"""Independent actual-run pair oracles count two engines and charge relocation once."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import parse_json
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_pair_execute import execute_relocation_pair
from app.v3.relocation_pair_inputs import PreparedRelocationPair, prepare_relocation_pair
from app.v3.relocation_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def hand_pair(
    *, noop: bool = False, horizon: int = 10 * SECOND, end: int = 20 * SECOND
) -> PreparedRelocationPair:
    profile, conveyor = relocation_hand(), receipt_conveyor()
    baseline = freeze_hand_inputs(replace(profile, jobs=()), conveyor, horizon, end)
    candidate = freeze_hand_inputs(
        replace(profile, jobs=()) if noop else profile, conveyor, horizon, end
    )
    return prepare_relocation_pair(baseline, candidate, scenario="N1")


def actual_calls(
    monkeypatch: pytest.MonkeyPatch, root: Path, pair: PreparedRelocationPair
) -> list[RelocationEngine]:
    calls: list[RelocationEngine] = []
    original = RelocationEngine.run

    def counted(engine: RelocationEngine, horizon: int, end: int) -> CoordinatorOutcome:
        assert (root / "inputs.json").read_bytes() == pair.frozen_bytes
        assert (root / "baseline/inputs.json").read_bytes() == pair.baseline.frozen_bytes
        assert (root / "candidate/inputs.json").read_bytes() == pair.candidate.frozen_bytes
        calls.append(engine)
        return original(engine, horizon, end)

    monkeypatch.setattr(RelocationEngine, "run", counted)
    return calls


def test_actual_candidate_cost_is_subtracted_once_at_both_observed_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = hand_pair()
    calls = actual_calls(monkeypatch, tmp_path, pair)
    report = execute_relocation_pair(pair, tmp_path)
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert len(calls[0].relocations) == 0 and len(calls[1].relocations) == 1
    assert report["status"] == "complete" and report["no_op"] is False
    horizon, end = report["windows"]["at_horizon"], report["windows"]["at_end"]
    assert horizon["baseline_paid_ticks"] == 0 and horizon["candidate_paid_ticks"] == 10 * SECOND
    assert horizon["net_paid_ticks"] == -10 * SECOND
    assert end["baseline_paid_ticks"] == 0 and end["candidate_paid_ticks"] == 13 * SECOND
    assert end["net_paid_ticks"] == -13 * SECOND
    assert end["candidate_relocation_paid_ticks"] == 13 * SECOND
    assert (end["baseline_tick"], end["candidate_tick"]) == (10 * SECOND, 13 * SECOND)
    assert end["customer_work"]["unit"]["completed_orders_delta"] == 0
    assert end["customer_work"]["whole"]["completed_orders_delta"] == 0
    assert parse_json((tmp_path / "comparison.json").read_bytes()) == report
    assert (tmp_path / "baseline/manifest.json").is_file()
    assert (tmp_path / "candidate/manifest.json").is_file()


def test_noop_still_executes_two_real_instances_with_equal_observed_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = hand_pair(noop=True, horizon=SECOND, end=2 * SECOND)
    calls = actual_calls(monkeypatch, tmp_path, pair)
    report = execute_relocation_pair(pair, tmp_path)
    assert len(calls) == 2 and calls[0] is not calls[1]
    assert report["executions"] == 2 and report["no_op"] is True
    assert report["baseline"]["event_sha256"] == report["candidate"]["event_sha256"]
    assert report["baseline"]["observation_sha256"] == report["candidate"]["observation_sha256"]
    assert report["windows"]["at_end"]["net_paid_ticks"] == 0


def test_partial_cap_retains_actual_carried_stock_and_negative_paid_difference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = hand_pair(horizon=5 * SECOND, end=6 * SECOND)
    calls = actual_calls(monkeypatch, tmp_path, pair)
    report = execute_relocation_pair(pair, tmp_path)
    assert len(calls) == 2 and report["status"] == "partial"
    assert report["baseline"]["status"] == "complete"
    assert report["candidate"]["status"] == "partial"
    assert report["windows"]["at_end"]["net_paid_ticks"] == -6 * SECOND
    assert calls[1].ledger.contents("HU1").container.owner_id == "actor:S01"
    assert len(calls[1].ledger.claims) == 1


def test_changed_common_clock_is_rejected_before_any_execution_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = hand_pair()
    changed = freeze_hand_inputs(relocation_hand(), receipt_conveyor(), 10 * SECOND, 21 * SECOND)
    forged = replace(pair, candidate=changed)
    output = tmp_path / "rejected"
    calls = actual_calls(monkeypatch, output, forged)
    with pytest.raises(ValueError):
        execute_relocation_pair(forged, output)
    assert calls == [] and not output.exists()


def test_publication_failure_retains_complete_frozen_input_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = hand_pair()
    calls = actual_calls(monkeypatch, tmp_path, pair)

    def fail_write(*args: Any, **kwargs: Any) -> None:
        raise OSError("independent publication failure")

    monkeypatch.setattr("app.v3.relocation_pair_execute.write_relocation_run", fail_write)
    with pytest.raises(OSError, match="publication failure"):
        execute_relocation_pair(pair, tmp_path)
    assert len(calls) == 2
    assert (tmp_path / "inputs.json").read_bytes() == pair.frozen_bytes
    assert (tmp_path / "baseline/inputs.json").read_bytes() == pair.baseline.frozen_bytes
    assert (tmp_path / "candidate/inputs.json").read_bytes() == pair.candidate.frozen_bytes
    assert not (tmp_path / "comparison.json").exists()


def test_nonempty_output_is_rejected_without_clobbering_or_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = hand_pair()
    original = b"preexisting evidence"
    (tmp_path / "keep.txt").write_bytes(original)
    calls = actual_calls(monkeypatch, tmp_path, pair)
    with pytest.raises(ValueError):
        execute_relocation_pair(pair, tmp_path)
    assert calls == [] and (tmp_path / "keep.txt").read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt"]
