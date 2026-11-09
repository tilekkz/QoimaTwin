"""Public source CLI orchestration; fake engine/publication are explicitly test doubles."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.errors import OutputNotEmptyError
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import cli_coordinator, coordinator_cli_evidence
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_profile import CompiledCoordinatorProfile, compile_coordinator_profile
from tests.v3.test_coordinator_profile_fixtures import (
    coordinator_document,
    coordinator_sources,
)

__all__ = ["coordinator_sources"]


@pytest.fixture(scope="module")
def compiled_source(coordinator_sources: Any) -> tuple[CompiledCoordinatorProfile, ConveyorSource]:
    bundle, conveyor = coordinator_sources
    return compile_coordinator_profile(bundle, conveyor, coordinator_document()), conveyor


def test_request_and_exact_inputs_exist_before_engine_construction(
    compiled_source: tuple[CompiledCoordinatorProfile, ConveyorSource],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiled, conveyor = compiled_source
    out = tmp_path / "output"
    observations: list[tuple[int, int]] = []

    class FakeEngine:
        def __init__(self, *args: Any) -> None:
            assert (out / "run/inputs.json").read_bytes() == compiled.frozen_bytes
            request = parse_json((out / "request.json").read_bytes())
            assert request["input_hash"] == compiled.input_hash
            assert request["registry_common_hash"] == compiled.registry_common_hash

        def run(self, horizon: int, end: int) -> object:
            observations.append((horizon, end))
            return object()

    def build(inputs: Any, outcome: Any) -> dict[str, Any]:
        assert inputs is compiled
        return {
            "status": "partial",
            "run_id": "a" * 64,
            "input_hash": compiled.input_hash,
            "registry_common_hash": compiled.registry_common_hash,
            "observed_until_tick": compiled.end_tick,
            "metrics": {"test_double": "only"},
        }

    def write(run: Any, root: Path, *, inputs: bytes) -> dict[str, Any]:
        assert inputs == compiled.frozen_bytes
        raw = canonical_bytes({"run_id": run["run_id"], "test_double": "not native proof"})
        (root / "manifest.json").write_bytes(raw)
        return dict(parse_json(raw))

    monkeypatch.setattr(cli_coordinator, "CoordinatorEngine", FakeEngine)
    monkeypatch.setattr(cli_coordinator, "build_coordinator_run", build)
    monkeypatch.setattr(cli_coordinator, "write_coordinator_run", write)
    report = cli_coordinator.simulate_compiled_coordinator(compiled, conveyor, out)
    assert report["status"] == "partial"
    assert observations == [(compiled.horizon_tick, compiled.end_tick)]
    assert parse_json((out / "result.json").read_bytes()) == report


def test_failed_execution_retains_request_and_input_evidence(
    compiled_source: tuple[CompiledCoordinatorProfile, ConveyorSource],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiled, conveyor = compiled_source
    out = tmp_path / "failure"

    def fail(*args: Any) -> None:
        raise RuntimeError("explicit test double failure")

    monkeypatch.setattr(cli_coordinator, "CoordinatorEngine", fail)
    result = cli_coordinator.simulate_compiled_coordinator(compiled, conveyor, out)
    assert result["status"] == "failed"
    assert (out / "run/inputs.json").read_bytes() == compiled.frozen_bytes
    assert (out / "request.json").is_file()
    assert parse_json((out / "result.json").read_bytes()) == result


def test_public_cli_rejects_forged_retained_input_and_existing_output(
    compiled_source: tuple[CompiledCoordinatorProfile, ConveyorSource],
    tmp_path: Path,
) -> None:
    compiled, conveyor = compiled_source
    target = tmp_path / "forged"
    with pytest.raises(ValueError):
        coordinator_cli_evidence.freeze_request(
            replace(compiled, horizon_tick=compiled.horizon_tick + 1),
            conveyor,
            target,
        )
    assert not target.exists()
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(OutputNotEmptyError):
        coordinator_cli_evidence.freeze_request(compiled, conveyor, target)
    assert (target / "keep.txt").read_text() == "keep"


def test_hand_like_objects_cannot_enter_source_only_cli(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Exact compiled coordinator"):
        coordinator_cli_evidence.freeze_request(object(), object(), tmp_path / "hand")  # type: ignore[arg-type]
