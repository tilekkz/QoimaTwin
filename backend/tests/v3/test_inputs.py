from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from app.v3.input_catalogs import validate_catalogs, validate_layout, validate_source_links
from app.v3.input_json import parse_json
from app.v3.input_models import V3InputError
from app.v3.input_stock import validate_assignments, validate_skus
from app.v3.inputs import V3Bundle, load_v3_bundle

from .input_helpers import PACKAGE, PREFIX, catalog_context


@pytest.fixture(scope="session")
def pinned_bundle() -> V3Bundle:
    return load_v3_bundle(PACKAGE)


@pytest.fixture
def documents(pinned_bundle: V3Bundle) -> dict[str, Any]:
    return {name: doc.decode() for name, doc in pinned_bundle.documents.items()}


def test_pinned_baseline_is_derived_from_records(pinned_bundle: V3Bundle) -> None:
    bundle = pinned_bundle
    assert len(bundle.handling_units) == 530
    assert len(bundle.skus) == 200
    assert bundle.baseline.quantity_units == 12256
    assert bundle.baseline.gross_mass_kg == 9403.85
    assert bundle.baseline.occupied_slots == 530
    assert bundle.baseline.active_slots == 588
    assert bundle.baseline.blocked_reserve_slots == 188
    assert bundle.baseline.free_active_slots == 58
    assert bundle.baseline.free_initial_flex_slots == 8
    assert len(bundle.slots) == 776
    assert len(bundle.cargo_archetypes) == 8
    assert len(bundle.ports) == 6
    assert bundle.data_kind == "static_geometry_proposal"
    assert bundle.operational_admission is False
    assert bundle.source_revision == "22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec"


def test_documents_and_nested_models_are_immutable(pinned_bundle: V3Bundle) -> None:
    with pytest.raises(FrozenInstanceError):
        mutate_frozen(pinned_bundle, "source_revision", "changed")
    with pytest.raises(FrozenInstanceError):
        mutate_frozen(pinned_bundle.handling_units[0], "quantity_units", 1)
    mapping: Any = pinned_bundle.documents
    with pytest.raises(TypeError):
        mapping["extra"] = "changed"
    doc = pinned_bundle.documents[PREFIX + "baseline-input-v3.json"]
    mutable = doc.decode()
    mutable["skus"][0]["quantity_units"] = -1
    assert doc.decode()["skus"][0]["quantity_units"] == 96
    assert isinstance(doc.canonical_bytes, bytes)
    assert isinstance(pinned_bundle.skus[0].handling_unit_ids, tuple)


@pytest.mark.parametrize(
    "raw,reason",
    [
        (b'{"x":1,"x":2}', "duplicate JSON key: x"),
        (b'{"nested":{"x":1,"x":2}}', "duplicate JSON key: x"),
        (b'{"x":NaN}', "nonfinite"),
        (b'{"x":Infinity}', "nonfinite"),
        (b'{"x":-Infinity}', "nonfinite"),
        (b'{"x":1e999}', "nonfinite"),
        (b"\xff", "utf-8"),
    ],
)
def test_strict_json_rejects_invalid_numbers_and_keys(raw: bytes, reason: str) -> None:
    with pytest.raises(V3InputError, match=reason) as error:
        parse_json(raw, "input.json")
    assert "input.json" in str(error.value)


@pytest.mark.parametrize("mode", ["changed", "missing", "inventory"])
def test_package_integrity_fails_closed(tmp_path: Path, mode: str) -> None:
    import shutil

    target = tmp_path / "proposal"
    shutil.copytree(PACKAGE, target)
    path = target / PREFIX / "baseline-input-v3.json"
    if mode == "changed":
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)
    elif mode == "missing":
        path.unlink()
    else:
        (target / "provenance.json").write_bytes(b"{}")
    with pytest.raises(V3InputError, match=r"required source unreadable|pinned .*mismatch"):
        load_v3_bundle(target)


@pytest.mark.parametrize("kind", ["cargo", "storage"])
def test_raw_upstream_schema_violations(documents: dict[str, Any], kind: str) -> None:
    if kind == "cargo":
        documents[PREFIX + "cargo-catalog-v3.json"]["records"][0]["handling_unit"][
            "units_per_handling_unit"
        ] = 0
    else:
        documents[PREFIX + "storage-slots-v3.json"]["slots"][0]["max_payload_kg"] = "15"
    with pytest.raises(V3InputError, match="schema violation") as error:
        validate_catalogs(documents)
    assert ("records/0" if kind == "cargo" else "slots/0") in str(error.value)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("sku_id", "missing", "unknown SKU"),
        ("slot_id", "missing", "unknown slot"),
        ("quantity_units", 25, "HU quantity mismatch"),
        ("quantity_units", True, "expected positive integer"),
        ("module_id", "missing", "module mismatch"),
        ("lot_id", "missing", "lot mismatch"),
    ],
)
def test_assignment_integrity(
    documents: dict[str, Any], field: str, value: Any, reason: str
) -> None:
    documents[PREFIX + "baseline-assignment-v3.json"]["assignments"][0][field] = value
    cargo, skus, slots, ports = catalog_context(documents)
    with pytest.raises(V3InputError, match=reason) as error:
        validate_assignments(documents, cargo, skus, slots, ports)
    assert "baseline-assignment-v3.json/assignments/0" in str(error.value)


@pytest.mark.parametrize("field", ["handling_unit_id", "slot_id"])
def test_duplicate_assignment_identities(documents: dict[str, Any], field: str) -> None:
    assignments = documents[PREFIX + "baseline-assignment-v3.json"]["assignments"]
    assignments[1][field] = assignments[0][field]
    cargo, skus, slots, ports = catalog_context(documents)
    with pytest.raises(V3InputError, match="duplicate identity"):
        validate_assignments(documents, cargo, skus, slots, ports)


@pytest.mark.parametrize("kind", ["mass", "units", "module_mass"])
def test_record_derived_arithmetic_rejects_false_summary(
    documents: dict[str, Any], kind: str
) -> None:
    data = documents[PREFIX + "baseline-assignment-v3.json"]
    if kind == "module_mass":
        key = next(iter(data["module_mass_kg"]))
        data["module_mass_kg"][key] += 1
    else:
        data["summary"]["gross_mass_kg" if kind == "mass" else "quantity_units"] += 1
    cargo, skus, slots, ports = catalog_context(documents)
    with pytest.raises(V3InputError, match=r"arithmetic mismatch|record-derived count mismatch"):
        validate_assignments(documents, cargo, skus, slots, ports)


def test_sku_quantity_conservation(documents: dict[str, Any]) -> None:
    documents[PREFIX + "baseline-input-v3.json"]["skus"][0]["quantity_units"] += 1
    cargo, _, _, ports = catalog_context(documents)
    with pytest.raises(V3InputError, match="quantity conservation mismatch"):
        validate_skus(documents, cargo, ports)


def test_duplicate_sku_identity(documents: dict[str, Any]) -> None:
    skus = documents[PREFIX + "sku-catalog-v3.json"]["skus"]
    skus[1]["sku_id"] = skus[0]["sku_id"]
    cargo, _, _, ports = catalog_context(documents)
    with pytest.raises(V3InputError, match="duplicate identity"):
        validate_skus(documents, cargo, ports)


def test_unsupported_layout(documents: dict[str, Any]) -> None:
    documents[PREFIX + "layout-manifest-v3.json"]["layout_version"] = "qoima-72x48-v2"
    with pytest.raises(V3InputError, match="unsupported layout"):
        validate_layout(documents)


def test_in_scope_source_link_hash(documents: dict[str, Any], pinned_bundle: V3Bundle) -> None:
    documents[PREFIX + "baseline-assignment-v3.json"]["baseline_input"]["sha256"] = "0" * 64
    with pytest.raises(V3InputError, match="source hash mismatch"):
        validate_source_links(
            documents, {e.path: e.raw_sha256 for e in pinned_bundle.source_inventory}
        )


def mutate_frozen(value: object, field: str, replacement: object) -> None:
    setattr(value, field, replacement)


def test_cargo_mass_is_recomputed(documents: dict[str, Any]) -> None:
    from app.v3.input_catalogs import validate_cargo_arithmetic

    record = documents[PREFIX + "cargo-catalog-v3.json"]["records"][0]
    record["handling_unit"]["gross_mass_kg"] += 1
    with pytest.raises(V3InputError, match="arithmetic mismatch"):
        validate_cargo_arithmetic(record, "cargo-catalog-v3.json/records/0")


def test_duplicate_cargo_archetype(documents: dict[str, Any]) -> None:
    records = documents[PREFIX + "cargo-catalog-v3.json"]["records"]
    records[1] = records[0]
    with pytest.raises(V3InputError, match="duplicate identity"):
        validate_catalogs(documents)


def test_duplicate_storage_identity(documents: dict[str, Any]) -> None:
    from app.v3.input_stock import validate_slots

    storage = documents[PREFIX + "storage-slots-v3.json"]
    storage["slots"][1]["slot_id"] = storage["slots"][0]["slot_id"]
    cargo, _, _, _ = catalog_context(documents)
    with pytest.raises(V3InputError, match="duplicate identity"):
        validate_slots(documents, cargo, {})


def test_assignment_cannot_use_blocked_reserve(documents: dict[str, Any]) -> None:
    cargo, skus, slots, ports = catalog_context(documents)
    blocked = next(s for s in slots.values() if s["retrieval_blocked"])
    assignment = documents[PREFIX + "baseline-assignment-v3.json"]["assignments"][0]
    assignment["slot_id"] = blocked["slot_id"]
    assignment["module_id"] = blocked["module_id"]
    with pytest.raises(V3InputError, match="blocked or inactive slot"):
        validate_assignments(documents, cargo, skus, slots, ports)


def test_external_schema_reference_is_rejected() -> None:
    from app.v3.input_checks import schema_check

    with pytest.raises(V3InputError, match="external schema reference forbidden"):
        schema_check({}, {"$ref": "https://example.invalid/schema.json"}, "schema.json")


def test_missing_document_fails_with_source_path(documents: dict[str, Any]) -> None:
    del documents[PREFIX + "cargo-catalog-v3.json"]
    with pytest.raises(V3InputError, match=r"cargo-catalog-v3\.json: required document missing"):
        validate_catalogs(documents)


def test_static_slot_geometry_is_checked(documents: dict[str, Any]) -> None:
    cargo, skus, slots, ports = catalog_context(documents)
    first = documents[PREFIX + "baseline-assignment-v3.json"]["assignments"][0]
    slots[first["slot_id"]]["usable_dimensions_xyz_m"][0] = 0.01
    with pytest.raises(V3InputError, match="HU dimensions and clearance"):
        validate_assignments(documents, cargo, skus, slots, ports)


def test_sku_template_pointer_is_bound(documents: dict[str, Any]) -> None:
    documents[PREFIX + "sku-catalog-v3.json"]["skus"][0]["cargo_template_pointer"] = "/records/1"
    cargo, _, _, ports = catalog_context(documents)
    with pytest.raises(V3InputError, match="cargo template pointer mismatch"):
        validate_skus(documents, cargo, ports)
