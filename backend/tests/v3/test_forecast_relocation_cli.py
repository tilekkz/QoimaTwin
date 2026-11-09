"""File orchestration controls with an explicit executor double; no runtime is started."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import forecast_relocation_cli as cli
from app.v3.forecast_relocation_models import ForecastRelocationChoices
from tests.v3.test_forecast_relocation_binding import BridgeCase, prepare
from tests.v3.test_forecast_relocation_binding import case as case


def test_prepare_freezes_outer_and_unchanged_native_arms(
    case: BridgeCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Prepare must never enter the executor")

    monkeypatch.setattr(cli, "execute_relocation_pair", forbidden)
    decision, common = tmp_path / "decision.json", tmp_path / "common.json"
    decision.write_bytes(case.decision.frozen_bytes)
    common.write_bytes(case.common.frozen_bytes)
    out = tmp_path / "prepared"
    result = cli.prepare_files(decision, common, ForecastRelocationChoices("MOVE-ACTUAL", 7), out)
    value = prepare(case)
    assert result["status"] == "prepared"
    assert (out / "inputs.json").read_bytes() == value.frozen_bytes
    assert (out / "baseline.json").read_bytes() == value.pair.baseline.frozen_bytes
    assert (out / "candidate.json").read_bytes() == value.pair.candidate.frozen_bytes
    assert parse_json((out / "manifest.json").read_bytes()) == result


def test_partial_compare_freezes_before_one_executor_and_keeps_status(
    case: BridgeCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value, calls = prepare(case), []

    def execute(pair: Any, root: Path) -> dict[str, Any]:
        calls.append(pair)
        assert (root.parent / "inputs.json").read_bytes() == value.frozen_bytes
        root.mkdir()
        report = {
            "status": "partial",
            "pair_input_hash": pair.input_hash,
            "comparison_id": "hand-observed-partial",
            "no_op": False,
        }
        (root / "comparison.json").write_bytes(canonical_bytes(report))
        return report

    monkeypatch.setattr(cli, "execute_relocation_pair", execute)
    out = tmp_path / "comparison"
    result = cli.compare_forecast_relocation(value, out)
    assert len(calls) == 1
    assert result["status"] == "partial"
    assert result["input_hash"] == value.input_hash
    assert result["pair_input_hash"] == value.pair.input_hash
    assert result["full_n1_acceptance"] is False
    assert parse_json((out / "manifest.json").read_bytes()) == result


def test_executor_error_preserves_outer_and_partial_pair(
    case: BridgeCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = prepare(case)

    def failed(pair: Any, root: Path) -> Any:
        root.mkdir()
        (root / "partial.txt").write_bytes(b"observed-before-error")
        raise ValueError("injected executor error")

    monkeypatch.setattr(cli, "execute_relocation_pair", failed)
    out = tmp_path / "failed"
    with pytest.raises(ValueError, match="injected"):
        cli.compare_forecast_relocation(value, out)
    assert (out / "inputs.json").read_bytes() == value.frozen_bytes
    assert (out / "pair" / "partial.txt").read_bytes() == b"observed-before-error"
    assert parse_json((out / "failure.json").read_bytes())["status"] == "error"
    assert not (out / "manifest.json").exists()


def test_retained_mutation_refused_before_claim_or_execution(
    case: BridgeCase, tmp_path: Path
) -> None:
    value = prepare(case)
    corrupt = replace(value, pair=replace(value.pair, common_input_hash="foreign"))
    with pytest.raises(ValueError):
        cli.compare_forecast_relocation(corrupt, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_existing_empty_output_is_not_claimed(case: BridgeCase, tmp_path: Path) -> None:
    out = tmp_path / "claimed"
    out.mkdir()
    with pytest.raises(FileExistsError):
        cli.compare_forecast_relocation(prepare(case), out)
    assert list(out.iterdir()) == []


def test_cli_partial_exit_is_zero(
    case: BridgeCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "inputs.json"
    source.write_bytes(prepare(case).frozen_bytes)

    def partial(raw: bytes, out: Path) -> dict[str, Any]:
        assert raw == source.read_bytes()
        return {"status": "partial"}

    monkeypatch.setattr(cli, "compare_forecast_relocation", partial)
    assert cli.main(["compare", "--inputs", str(source), "--out", str(tmp_path / "out")]) == 0
    assert parse_json(capsys.readouterr().out)["status"] == "partial"
