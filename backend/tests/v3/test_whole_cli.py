"""The command freezes evidence before execution and reports real partial/failure status."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.errors import OutputNotEmptyError
from app.storage.canonical_json import canonical_bytes
from app.v3 import cli, whole_cli, whole_cli_evidence
from app.v3.whole_profile_io import CompiledWholeProfile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_run_fixtures import sample


def setup_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, partial: bool = False
) -> tuple[Path, CompiledWholeProfile, Any]:
    inputs, outcome = sample(horizon=46 * SECOND, end=47 * SECOND) if partial else sample()
    raw = canonical_bytes({"test_fixture": "explicit hand input, not source approval"})
    compiled = CompiledWholeProfile(inputs, raw, sha256(raw).hexdigest())
    profile = tmp_path / "offered.json"
    profile.write_bytes(raw)
    monkeypatch.setattr(whole_cli, "load_v3_bundle", lambda _: None)
    monkeypatch.setattr(whole_cli, "load_conveyor_source", lambda _: receipt_conveyor())
    monkeypatch.setattr(whole_cli, "compile_whole_profile", lambda *args: compiled)
    # These orchestration tests inject hand inputs; actual source binding has separate tests.
    monkeypatch.setattr(whole_cli_evidence, "verify_compiled", lambda _: None)
    return profile, compiled, outcome


def test_input_evidence_exists_before_engine_and_manifest_is_explicit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile, compiled, outcome = setup_command(monkeypatch, tmp_path)
    out = tmp_path / "result"

    def engine(*args: Any) -> Any:
        request = json.loads((out / "request.json").read_bytes())
        assert request["choices_sha256"] == compiled.choices_sha256
        assert request["input_hash"] == compiled.run_inputs.input_hash
        assert request["physical_input_hash"] == compiled.run_inputs.physical_input_hash
        assert (out / "run/inputs.json").read_bytes() == compiled.run_inputs.frozen_bytes
        return type("Finished", (), {"run": lambda *args: outcome})()

    monkeypatch.setattr(whole_cli, "WholeFlowEngine", engine)
    result = whole_cli.simulate_whole_file(tmp_path, profile, out)
    assert result["status"] == "complete"
    assert result["manifest"] == str(out / "run/manifest.json")
    assert result["request_sha256"] == sha256((out / "request.json").read_bytes()).hexdigest()
    assert json.loads((out / "result.json").read_bytes()) == result


def test_runtime_failure_preserves_inputs_and_structured_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile, compiled, _ = setup_command(monkeypatch, tmp_path)

    def fail(*args: Any) -> Any:
        raise RuntimeError("injected bounded failure")

    monkeypatch.setattr(whole_cli, "WholeFlowEngine", fail)
    out = tmp_path / "failed"
    result = whole_cli.simulate_whole_file(tmp_path, profile, out)
    assert result["status"] == "failed"
    assert result["error"]["code"] == "execution_error"
    assert (out / "run/inputs.json").read_bytes() == compiled.run_inputs.frozen_bytes
    assert (out / "request.json").exists()
    assert not (out / "run/manifest.json").exists()


def test_nonempty_output_is_preserved_before_loading_profile(tmp_path: Path) -> None:
    marker = tmp_path / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(OutputNotEmptyError):
        whole_cli.simulate_whole_file(tmp_path, tmp_path / "missing", tmp_path)
    assert marker.read_text() == "keep"


def test_output_that_changes_during_compilation_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile, compiled, _ = setup_command(monkeypatch, tmp_path)
    out = tmp_path / "changed"

    def compile_changed(*args: Any) -> CompiledWholeProfile:
        out.mkdir()
        (out / "foreign.txt").write_text("keep")
        return compiled

    monkeypatch.setattr(whole_cli, "compile_whole_profile", compile_changed)
    with pytest.raises(OutputNotEmptyError):
        whole_cli.simulate_whole_file(tmp_path, profile, out)
    assert sorted(p.name for p in out.iterdir()) == ["foreign.txt"]


def test_partial_cli_returns_nonzero_and_keeps_real_paid_return(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile, _, outcome = setup_command(monkeypatch, tmp_path, partial=True)
    monkeypatch.setattr(
        whole_cli,
        "WholeFlowEngine",
        lambda *args: type("Finished", (), {"run": lambda *a: outcome})(),
    )
    code = cli.main(["simulate-whole", "--profile", str(profile), "--out", str(tmp_path / "out")])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["status"] == "partial"
    assert report["operational_admission"] is False
    assert Path(report["manifest"]).is_file()


def test_existing_receipt_dispatch_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: list[tuple[Any, ...]] = []

    def receipt(*args: Any) -> dict[str, str]:
        called.append(args)
        return {"status": "complete"}

    monkeypatch.setattr(cli, "simulate_receipt_file", receipt)
    assert cli.main(["simulate-receipt", "--profile", "existing.json", "--out", str(tmp_path)]) == 0
    assert called[0][1] == Path("existing.json")
