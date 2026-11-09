"""Rehashed metadata is not authority; timings remain outside semantic identity."""

import json
from hashlib import sha256
from pathlib import Path
from shutil import copytree
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.offer_planning_cli_storage import descriptor, request_record
from app.v3.offer_planning_cli_validation import validate_offer_plan
from tests.v3.test_offer_planning_cli import bundle

__all__ = ["bundle"]


def save_manifest(target: Path, value: dict[str, Any]) -> None:
    identity = {"version": value["version"], "semantic": value["semantic"]}
    value["semantic_bundle_id"] = sha256(canonical_bytes(identity)).hexdigest()
    (target / "manifest.json").write_bytes(canonical_bytes(value))


@pytest.mark.parametrize("mutation", ["stage", "request", "semantic_alias"])
def test_rehashed_metadata_cannot_change_authenticated_chain(
    bundle: Path, tmp_path: Path, mutation: str
) -> None:
    target = tmp_path / "copy"
    copytree(bundle, target)
    manifest = json.loads((target / "manifest.json").read_bytes())
    if mutation == "stage":
        path = target / "history.json"
        value = json.loads(path.read_bytes())
        value["choices"]["provenance"]["dataset_id"] = "different-declared-dataset"
        raw = canonical_bytes(value)
        path.write_bytes(raw)
        manifest["semantic"]["artifacts"]["history"] = descriptor("history.json", raw)
    elif mutation == "request":
        path = target / "raw/history-choices.json"
        value = json.loads(path.read_bytes())
        value["provenance"]["dataset_id"] = "different-declared-dataset"
        path.write_bytes(canonical_bytes(value))
        inputs = {p.name: p.read_bytes() for p in (target / "raw").iterdir()}
        raw = canonical_bytes(request_record("mean28", inputs))
        (target / "request.json").write_bytes(raw)
        manifest["semantic"]["request"] = descriptor("request.json", raw)
    else:
        manifest["semantic"]["engine_calls"] = False
    save_manifest(target, manifest)
    with pytest.raises(ValueError):
        validate_offer_plan(target)


def test_cpu_change_keeps_semantic_id_but_changes_manifest_hash(
    bundle: Path, tmp_path: Path
) -> None:
    target = tmp_path / "copy"
    copytree(bundle, target)
    original = (target / "manifest.json").read_bytes()
    manifest = json.loads(original)
    semantic_id = manifest["semantic_bundle_id"]
    path = target / "observations.json"
    observations = json.loads(path.read_bytes())
    observations["planning_elapsed_s"] += 1.0
    observations["forecast_cpu"]["total_s"] += 1.0
    raw = canonical_bytes(observations)
    path.write_bytes(raw)
    manifest["observations"] = descriptor("observations.json", raw)
    save_manifest(target, manifest)
    result = validate_offer_plan(target)
    assert result["semantic_bundle_id"] == semantic_id
    assert result["manifest_sha256"] != sha256(original).hexdigest()
    assert result["planning_status"] == "no-op"


@pytest.mark.parametrize("invalid", [True, -0.5, "0.0"])
def test_rehashed_invalid_cpu_observation_is_rejected(
    bundle: Path, tmp_path: Path, invalid: object
) -> None:
    target = tmp_path / "copy"
    copytree(bundle, target)
    manifest = json.loads((target / "manifest.json").read_bytes())
    path = target / "observations.json"
    observations = json.loads(path.read_bytes())
    observations["forecast_cpu"]["validation_s"] = invalid
    raw = canonical_bytes(observations)
    path.write_bytes(raw)
    manifest["observations"] = descriptor("observations.json", raw)
    save_manifest(target, manifest)
    with pytest.raises(ValueError, match="finite nonnegative floats"):
        validate_offer_plan(target)
