"""Static V3 publication has an executable schema and byte-addressed source documents."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.storage.canonical_json import sha256_hex
from app.v3.export import build_static_export, validate_static_export, write_static_export
from tests.v3.test_interface_sources import small_bundle


def test_published_schema_validates_the_static_export() -> None:
    path = Path(__file__).parents[2] / "docs/proposals/adaptive-v3/static-export.schema.json"
    published = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(published)
    Draft202012Validator(published).validate(build_static_export(small_bundle()))


def test_export_schema_rejects_false_engine_claim_and_invalid_hu_pose() -> None:
    value = build_static_export(small_bundle())
    validate_static_export(value)
    altered = copy.deepcopy(value)
    altered["catalog"]["capabilities"]["actual_engine_run"] = True
    with pytest.raises(ValueError, match="schema"):
        validate_static_export(altered)
    altered = copy.deepcopy(value)
    altered["initial_state"]["handling_units"][0]["pose"]["world_pos"] = [1, 2]
    with pytest.raises(ValueError, match="schema"):
        validate_static_export(altered)


def test_writer_publishes_checked_raw_hashes_without_run_or_history(tmp_path: Path) -> None:
    manifest = write_static_export(small_bundle(), tmp_path / "bundle")
    assert manifest["data_kind"] == "static_geometry_proposal"
    assert "run_id" not in manifest and "event_chunks" not in manifest
    descriptors = [manifest["catalog"], manifest["initial_state"], *manifest["source_documents"]]
    for descriptor in descriptors:
        raw = (tmp_path / "bundle" / descriptor["path"]).read_bytes()
        assert len(raw) == descriptor["bytes"]
        assert hashlib.sha256(raw).hexdigest() == descriptor["sha256"]
        assert isinstance(json.loads(raw), dict)
    with pytest.raises(ValueError, match="empty"):
        write_static_export(small_bundle(), tmp_path / "bundle")


@pytest.mark.parametrize(
    "damage", ["owner", "quantity", "total", "count", "sku", "dimensions", "pose", "yaw"]
)
def test_rehashed_export_still_rejects_incoherent_stock(damage: str) -> None:
    value = build_static_export(small_bundle())
    state, catalog = value["initial_state"], value["catalog"]
    if damage == "owner":
        state["handling_units"][1]["owner"] = copy.deepcopy(state["handling_units"][0]["owner"])
    elif damage == "quantity":
        state["handling_units"][0]["quantity_units"] += 1
    elif damage == "total":
        state["totals"]["gross_mass_kg"] += 1
    elif damage == "count":
        catalog["counts"]["slots"] += 1
    elif damage == "sku":
        state["handling_units"][0]["sku_id"] = "MISSING"
    elif damage == "dimensions":
        state["handling_units"][0]["dimensions_xyz_m"][0] = -1
    elif damage == "pose":
        state["handling_units"][0]["pose"]["world_pos"][1] += 1e-10
    else:
        catalog["storage_modules"][0]["yaw_rad"] = 1.0
        for unit in state["handling_units"]:
            unit["pose"]["yaw_rad"] = 1.0
    for item, key in ((catalog, "catalog_id"), (state, "state_id"), (value, "export_id")):
        item[key] = sha256_hex({name: data for name, data in item.items() if name != key})
    with pytest.raises(ValueError):
        validate_static_export(value)


def test_publication_does_not_overwrite_a_concurrent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.v3.export as exporter

    original = exporter._write

    def competing_write(root: Path, relative: str, raw: bytes) -> dict[str, object]:
        if relative == "catalog.json":
            (root / relative).write_bytes(b'{"foreign":true}')
        return original(root, relative, raw)

    monkeypatch.setattr(exporter, "_write", competing_write)
    with pytest.raises(FileExistsError):
        write_static_export(small_bundle(), tmp_path / "bundle")
    assert (tmp_path / "bundle/catalog.json").read_bytes() == b'{"foreign":true}'
    assert not (tmp_path / "bundle/manifest.json").exists()
