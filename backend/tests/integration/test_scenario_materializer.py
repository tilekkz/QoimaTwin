"""Schema-valid materialization and byte-identical, atomically published artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from app.cli import main
from app.contracts.config import SimulationConfig
from app.contracts.scenario import Scenario
from app.data.catalog import SKU_IDS
from app.data.scenario_materializer import (
    MaterializedScenario,
    Profile,
    materialize,
    write_materialized,
)
from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex


@pytest.mark.parametrize(
    ("profile", "horizon", "count", "receipt_count"),
    [
        ("large-normal", 3600, 240, 20),
        ("large-peak", 3600, 600, 20),
        ("large-normal", 28800, 1920, 160),
        ("large-peak", 28800, 4800, 160),
    ],
)
def test_counts_and_schema(
    config: SimulationConfig,
    contracts_dir: Path,
    profile: Profile,
    horizon: int,
    count: int,
    receipt_count: int,
) -> None:
    scenario = materialize(profile, horizon, config).scenario
    assert len(scenario.orders) == count
    assert len(scenario.receipts) == receipt_count
    assert scenario.orders[-1].arrival_s < horizon
    assert scenario.provenance.kind == "synthetic"
    assert scenario.scenario_id == f"{profile}-{horizon}s-{scenario.provenance.orders_sha256[:12]}"
    data = scenario.model_dump(mode="json")
    assert scenario.provenance.orders_sha256 == sha256_hex(data["orders"])
    assert scenario.provenance.receipts_sha256 == sha256_hex(data["receipts"])
    jsonschema.validate(data, json.loads((contracts_dir / "scenario.schema.json").read_bytes()))
    for order in scenario.orders:
        skus = [line.sku_id for line in order.lines]
        assert 2 <= len(skus) <= 4
        assert len(set(skus)) == len(skus)
        assert skus == sorted(skus)
        assert all(sku in SKU_IDS for sku in skus)
        assert all(1 <= line.quantity <= 4 for line in order.lines)


def test_promotion_increases_visits(config: SimulationConfig) -> None:
    normal = materialize("large-normal", 28800, config)
    promotion = materialize("promotion", 28800, config)
    assert len(normal.scenario.orders) == len(promotion.scenario.orders)
    assert normal.scenario.receipts == promotion.scenario.receipts
    visits = [
        sum(line.sku_id == "DEMO_173" for order in result.scenario.orders for line in order.lines)
        for result in (normal, promotion)
    ]
    assert visits[1] > visits[0]
    w = normal.normalized_weights[172]
    assert promotion.normalized_weights[172] == pytest.approx(5 * w / (1 - w + 5 * w))


@pytest.mark.usefixtures("cached_materialization_history")
def test_artifacts_are_reproducible(
    config: SimulationConfig, tmp_path: Path, normal_materialization: MaterializedScenario
) -> None:
    first = normal_materialization
    second = materialize("large-normal", 3600, config)
    assert first == second
    for name, result in (("a", first), ("b", second)):
        write_materialized(result, tmp_path / name)
    for name in ("scenario.json", "history_daily.csv", "manifest.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    output = tmp_path / "a"
    assert Scenario.from_json_text((output / "scenario.json").read_bytes()) == first.scenario
    manifest = parse_json((output / "manifest.json").read_bytes())
    for name in ("scenario.json", "history_daily.csv"):
        assert manifest["hashes"][name] == hashlib.sha256((output / name).read_bytes()).hexdigest()
    for name in ("catalog", "weights"):
        assert manifest["hashes"][name] == sha256_hex(manifest[name])
    assert (output / "scenario.json").read_bytes() == canonical_bytes(
        first.scenario.model_dump(mode="json")
    )
    assert len(list(output.iterdir())) == 3


def test_config_rates_are_used(config: SimulationConfig) -> None:
    data = config.model_dump(mode="json", by_alias=True)
    data["profiles"]["large-normal"]["orders_per_hour"] = 17
    data["profiles"]["large-peak"]["orders_per_hour"] = 23
    changed = SimulationConfig.from_data(data)
    assert len(materialize("large-normal", 3600, changed).scenario.orders) == 17
    assert len(materialize("promotion", 3600, changed).scenario.orders) == 17
    assert len(materialize("large-peak", 3600, changed).scenario.orders) == 23


@pytest.mark.usefixtures("cached_materialization_history")
def test_materialize_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = [
        "materialize",
        "--profile",
        "large-normal",
        "--horizon-s",
        "3600",
        "--out",
        str(tmp_path),
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
    assert len(Scenario.from_json_text((tmp_path / "scenario.json").read_bytes()).orders) == 240
    args[4] = "3599"
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_failed_replace_preserves_target_and_cleans_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.data.scenario_materializer import _atomic_write

    target = tmp_path / "scenario.json"
    target.write_bytes(b"previous")

    def fail_replace(source: Path, destination: Path) -> None:
        assert source.read_bytes() == b"replacement"
        assert destination == target
        raise OSError("injected replacement failure")

    monkeypatch.setattr("app.data.scenario_materializer.os.replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        _atomic_write(target, b"replacement")
    assert target.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [target]
