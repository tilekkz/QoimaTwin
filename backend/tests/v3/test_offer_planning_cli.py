"""Normal CLI entry runs one real mean28 source chain with no engine access."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.cli import main
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_offer_planning_cli_fixtures import arguments


@pytest.fixture(scope="session")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("offer-cli")
    with pytest.MonkeyPatch.context() as monkeypatch:

        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("Planning CLI called an engine")

        for cls in (CoordinatorEngine, WholeFlowEngine, ReceiptFlowEngine, LightFlowEngine):
            monkeypatch.setattr(cls, "__init__", forbidden)
            monkeypatch.setattr(cls, "run", forbidden)
        assert main(arguments(root / "caller", root / "bundle")) == 0
    return root / "bundle"


def test_normal_cli_keeps_finite_shortages_negative_cost_and_noop(bundle: Path) -> None:
    decision = json.loads((bundle / "decision.json").read_bytes())
    assert decision["no_op"] is True and decision["selected"] is None
    assert decision["evaluations"][0]["cost"]["net_saving_ticks"] == -55_360_003
    assert (
        sum(row["status"] == "unallocated" for row in decision["stock_inputs"]["allocations"]) == 3
    )
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    assert manifest["semantic"]["status"] == "no-op"
    assert manifest["semantic"]["engine_calls"] == 0
    assert manifest["semantic"]["operational_admission"] is False


def test_data_only_validate_command_reconstructs_saved_chain(bundle: Path) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:

        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("Bundle validation called an engine")

        for cls in (CoordinatorEngine, WholeFlowEngine, ReceiptFlowEngine, LightFlowEngine):
            monkeypatch.setattr(cls, "__init__", forbidden)
            monkeypatch.setattr(cls, "run", forbidden)
        assert main(["v3", "validate-offer-plan", "--bundle", str(bundle)]) == 0


@pytest.mark.parametrize("mutation", ["unknown", "clock_bool", "missing", "history", "fraction"])
def test_malformed_choices_freeze_raw_failure_without_a_manifest(
    tmp_path: Path,
    mutation: str,
) -> None:
    output = tmp_path / "out"
    args = arguments(tmp_path / "caller", output)
    path = tmp_path / "caller/history_choices.json"
    value: Any = json.loads(path.read_bytes())
    if mutation == "unknown":
        value["actual_test_stream"] = []
    elif mutation == "clock_bool":
        value["window_start_second"] = False
    elif mutation == "missing":
        del value["timezone_name"]
    elif mutation == "history":
        (path.parent / "history.csv").write_bytes(b"date,sku_id,visits\n")
    else:
        path = path.parent / "placement_choices.json"
        value = json.loads(path.read_bytes())
        value["min_width_m"] = [True, 1]
    path.write_text(json.dumps(value), encoding="utf-8")
    assert main(args) == 1
    assert (output / "request.json").is_file()
    assert (output / "failure.json").is_file()
    assert not (output / "manifest.json").exists()
    assert (output / "raw/history.csv").read_bytes() == (path.parent / "history.csv").read_bytes()


def test_nonempty_output_is_not_changed(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    marker = output / "existing.bin"
    marker.write_bytes(b"keep-exact")
    assert main(arguments(tmp_path / "caller", output)) == 1
    assert list(output.iterdir()) == [marker] and marker.read_bytes() == b"keep-exact"
