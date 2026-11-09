"""Small complete hand bundle exercises the same parser; it is labelled synthetic."""

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.v3 import vehicle_source
from tests.v3.test_vehicle_fixtures import source_documents


def _install_fixture(
    root: Path, monkeypatch: pytest.MonkeyPatch, documents: dict[str, Any]
) -> None:
    folder = root / "docs/v3/contract-proposals"
    folder.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for name, value in documents.items():
        raw = json.dumps(value).encode()
        (folder / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(vehicle_source, "PINNED_SHA256", hashes)
    monkeypatch.setattr(vehicle_source, "SOURCE_REVISION", "synthetic-hand-fixture")
    monkeypatch.setattr(vehicle_source, "LAYOUT_VERSION", "hand")
    monkeypatch.setattr(vehicle_source, "LAYOUT_CONTENT_HASH", "hand-layout")


def test_complete_decoder_preserves_fixed_chassis_rating_and_raw_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixture(tmp_path, monkeypatch, source_documents())
    result = vehicle_source.load_vehicle_adapter(tmp_path)
    assert result.source_revision == "synthetic-hand-fixture"
    load = result.handling.loads[0]
    assert load.travel_arm_m == F(3, 5)
    assert load.extended_arm_m == F(1)
    assert load.hu_mass_kg == F(455)
    assert result.handling.slots[0].support_y_m == F(9, 50)
    assert len(result.raw_documents) == 6
    assert not result.operational_admission


@pytest.mark.parametrize("mutation", ["mass", "arm", "arc", "node", "pair", "layout", "duplicate"])
def test_rehashed_malformed_bundle_cannot_bypass_source_relationships(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    documents = source_documents()
    handling = documents["vehicle-handling-v3.json"]
    if mutation == "mass":
        handling["loads"][0]["attachment_mass_kg"] = 40
    elif mutation == "arm":
        handling["loads"][0]["extended_handling_rating_arm_from_fixed_Z04_m"] = 0.6
    elif mutation == "arc":
        handling["per_cargo_arc_eligibility"][0]["allowed_arc_ids"] = ["imaginary"]
    elif mutation == "node":
        documents["storage-slots-v3.json"]["slots"][0]["access"]["vehicle"] = "imaginary"
    elif mutation == "pair":
        documents["port-resource-policy-v3.json"]["forklift_pairs"][0]["pair_id"] = "imaginary"
    elif mutation == "layout":
        handling["layout_content_hash"] = "another-layout"
    else:
        handling["loads"].append(handling["loads"][0])
    _install_fixture(tmp_path, monkeypatch, documents)
    with pytest.raises(ValueError):
        vehicle_source.load_vehicle_adapter(tmp_path)
