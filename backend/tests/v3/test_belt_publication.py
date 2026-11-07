"""CLI publication uses real source recipes and persists inputs before simulation."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.v3 import cli_belt
from app.v3.belt_engine import BeltEngine
from app.v3.belt_profile import compile_belt_profile
from app.v3.cli import main
from tests.v3.test_belt_runtime import full_route, source_bundle, source_catalog


def proposal() -> dict[str, Any]:
    bundle = source_bundle()
    return {
        "profile_id": "catalog-belt-fixture",
        "source_revision": bundle.source_revision,
        "layout_content_hash": bundle.layout_content_hash,
        "horizon_tick": 100_000_000,
        "end_tick": 200_000_000,
        "jobs": [
            {
                "job_id": "belt-1",
                "hu_id": "v3:HU:initial:DEMO_001:01",
                "payload_id": "carrier-1",
                "arrival_tick": 0,
                "route": list(full_route()),
                "station_id": "PK06",
                "station_dwell_tick": 2_000_000,
            }
        ],
    }


def test_compiled_payload_is_exact_catalogue_hu_without_client_dimensions() -> None:
    inputs = compile_belt_profile(source_bundle(), source_catalog(), proposal())
    job = inputs.jobs[0]
    assert str(job.payload.gross_mass_kg) == "47/50"  # 24*.035 + .1 wrapper
    assert tuple(map(str, job.payload.dimensions_xyz_m)) == ("8/25", "6/25", "6/25")
    assert job.hu_id == job.payload.parent_id == "v3:HU:initial:DEMO_001:01"


@pytest.mark.parametrize(
    "field,value",
    [
        ("horizon_tick", True),
        ("end_tick", 1),
        ("source_revision", "foreign"),
        ("layout_content_hash", "foreign"),
        ("extra", 0),
    ],
)
def test_invalid_profile_is_rejected(field: str, value: object) -> None:
    document = proposal()
    document[field] = value
    with pytest.raises(ValueError):
        compile_belt_profile(source_bundle(), source_catalog(), document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("hu_id", "unknown"),
        ("arrival_tick", 100_000_000),
        ("station_dwell_tick", True),
        ("dimensions_xyz_m", [0.01, 0.01, 0.01]),
        ("route", ["unknown"]),
        ("job_id", ""),
    ],
)
def test_invalid_job_is_rejected(field: str, value: object) -> None:
    document = proposal()
    document["jobs"][0][field] = value
    with pytest.raises(ValueError):
        compile_belt_profile(source_bundle(), source_catalog(), document)


def test_inputs_precede_engine_and_all_published_bytes_are_hashed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, output = tmp_path / "profile.json", tmp_path / "result"
    profile.write_text(json.dumps(proposal()), encoding="utf-8")

    def observed_engine(*args: Any, **kwargs: Any) -> BeltEngine:
        assert (output / "inputs.json").is_file()
        assert not (output / "manifest.json").exists()
        assert kwargs == {"check_invariants": True}
        return BeltEngine(*args, **kwargs)

    monkeypatch.setattr(cli_belt, "BeltEngine", observed_engine)
    result = cli_belt.simulate_conveyor(Path("data/v3-proposal"), profile, output)
    assert result["status"] == "complete" and not result["full_v3_warehouse"]
    manifest = json.loads((output / "manifest.json").read_bytes())
    for entry in manifest["files"]:
        raw = (output / entry["path"]).read_bytes()
        assert len(raw) == entry["bytes"] and sha256(raw).hexdigest() == entry["sha256"]
    trace = json.loads((output / "trace.json").read_bytes())
    assert trace["outcome"]["at_end"]["tick"] == 149_170_000  # source-edge sum in runtime test
    assert trace["outcome"]["at_end"]["completed"] == 1
    assert trace["inventory_integration"] is False and trace["frontend_adapter"] is False
    with pytest.raises(ValueError, match="empty directory"):
        cli_belt.simulate_conveyor(Path("data/v3-proposal"), profile, output)


def test_cli_returns_partial_with_no_invented_completion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = proposal()
    document.update(horizon_tick=1_000_000, end_tick=2_000_000)
    profile, output = tmp_path / "profile.json", tmp_path / "run"
    profile.write_text(json.dumps(document), encoding="utf-8")
    code = main(["simulate-conveyor", "--profile", str(profile), "--out", str(output)])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["status"] == "partial"
    trace = json.loads((output / "trace.json").read_bytes())
    assert trace["outcome"]["at_end"]["completed"] == 0
    assert max(event["tick"] for event in trace["outcome"]["events"]) <= 2_000_000


def test_semantic_identity_preserves_job_order_and_distinguishes_dwell() -> None:
    document = proposal()
    second = dict(document["jobs"][0])
    second.update(job_id="belt-2", payload_id="carrier-2")
    second["hu_id"] = next(
        hu.handling_unit_id
        for hu in source_bundle().handling_units
        if hu.archetype_id == "SMALL_CARTON" and hu.handling_unit_id != second["hu_id"]
    )
    document["jobs"].append(second)
    first = compile_belt_profile(source_bundle(), source_catalog(), document)
    document["jobs"].reverse()
    reordered = compile_belt_profile(source_bundle(), source_catalog(), document)
    assert first.frozen_bytes == reordered.frozen_bytes
    document["jobs"][0]["station_dwell_tick"] += 1
    changed = compile_belt_profile(source_bundle(), source_catalog(), document)
    assert changed.input_hash != first.input_hash


def test_failed_engine_retains_inputs_but_never_publishes_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    profile, output = tmp_path / "profile.json", tmp_path / "failed"
    profile.write_text(json.dumps(proposal()), encoding="utf-8")

    def failed_engine(*args: Any, **kwargs: Any) -> BeltEngine:
        raise RuntimeError("injected component failure")

    monkeypatch.setattr(cli_belt, "BeltEngine", failed_engine)
    code = main(["simulate-conveyor", "--profile", str(profile), "--out", str(output)])
    assert code == 1 and json.loads(capsys.readouterr().out)["status"] == "failed"
    assert (output / "inputs.json").is_file()
    assert not (output / "manifest.json").exists()
