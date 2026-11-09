"""Tiny pinned metadata packets; no real source compilation or geometry execution."""

from dataclasses import dataclass, replace
from hashlib import sha256
from os import link
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import physical_handoff_source as source
from app.v3.physical_handoff_models import HandoffDocument


@dataclass
class Packet:
    root: Path
    bundle: dict[str, Any]
    patch: pytest.MonkeyPatch

    def write_bundle(self, *, repin: bool = False) -> None:
        raw = canonical_bytes(self.bundle)
        (self.root / source.PACKAGE_PATH / "bundle.json").write_bytes(raw)
        if repin:
            self.patch.setattr(source, "BUNDLE_SHA256", sha256(raw).hexdigest())


def _section(name: str) -> dict[str, Any]:
    return {
        "schema_id": "test.physical." + name,
        "source_kind": "visual_fixture",
        "operational_admission": False,
        "engine_operation": False,
        "open_actions": ["CONTINUOUS_NATIVE_PROOF_REQUIRED"],
        "api_refusals": ["TERMINAL_CONNECTOR_NOT_PROVED"],
    }


def _bundle() -> dict[str, Any]:
    return {
        "schema_id": "qoima.n2-n3-physical-handoff.v1",
        "schema_version": "1.0.0",
        "source_kind": "visual_fixture",
        "units": "m_s_kg",
        "coordinate_system": {"handedness": "right", "up_axis": "+Y", "scale_factor": 1},
        "engine_operation": False,
        "operational_workflow_admitted": False,
        "backend_adoption_recorded": False,
        "sections": {},
        "extensions": {},
        "artifacts": {},
        "source_hashes": {},
        "scope": "Tiny metadata double, not an actual geometry certificate.",
    }


def _artifact(packet: Packet, name: str, value: object) -> None:
    raw = canonical_bytes(value)
    path = packet.root / source.PACKAGE_PATH / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    packet.bundle["artifacts"][name] = {"sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


@pytest.fixture
def packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Packet:
    result = Packet(tmp_path / "assets", _bundle(), monkeypatch)
    names = {"sections": ("staging", "retention", "routes"), "extensions": ("relative_pi",)}
    for group, members in names.items():
        for name in members:
            value = _section(name)
            _artifact(result, name + ".json", value)
            result.bundle[group][name] = {
                "path": name + ".json",
                "sha256": result.bundle["artifacts"][name + ".json"]["sha256"],
                "schema_id": value["schema_id"],
            }
    _artifact(result, "bundle.schema.json", {"type": "object", "required": ["scope"]})
    _artifact(result, "historical.json", {"source_hashes": {"source.json": "0" * 64}})
    raw = b'{"payload_kg":455,"operational_admission":false}\n'
    (result.root / "source.json").write_bytes(raw)
    result.bundle["source_hashes"] = {"source.json": sha256(raw).hexdigest()}
    monkeypatch.setattr(source, "ARTIFACT_COUNT", 6)
    monkeypatch.setattr(source, "SOURCE_COUNT", 1)
    result.write_bundle(repin=True)
    return result


def test_fresh_binding_identity_and_detached_section(packet: Packet) -> None:
    bound = source.load_physical_handoff(packet.root)
    fresh = source.verify_physical_handoff(bound)
    assert fresh == bound and fresh is not bound
    assert len(bound.documents) == 7
    report = parse_json(bound.frozen_bytes)
    assert report["validation_scope"] == "reference_only"
    assert report["operational_admission"] is False
    assert report["source_revision"] == "799ff93af8b082b8f1c0a40e4112b9bf8c83df11"
    assert report["counts"] == {"artifacts": 6, "current_sources": 1}
    assert str(packet.root) not in bound.frozen_bytes.decode()
    copy = source.handoff_section(bound, "staging")
    copy["open_actions"].clear()
    assert source.handoff_section(bound, "staging")["open_actions"]


def test_repinning_all_bundle_metadata_does_not_change_public_anchor(packet: Packet) -> None:
    _artifact(packet, "staging.json", {**_section("staging"), "operational_admission": True})
    packet.bundle["sections"]["staging"]["sha256"] = packet.bundle["artifacts"]["staging.json"][
        "sha256"
    ]
    packet.write_bundle()
    with pytest.raises(ValueError, match="anchor"):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize("change", ["missing", "changed", "extra", "extra_directory"])
def test_raw_source_and_closed_package(packet: Packet, change: str) -> None:
    path = packet.root / "source.json"
    if change == "missing":
        path.unlink()
    elif change == "changed":
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "extra":
        (packet.root / source.PACKAGE_PATH / "foreign.json").write_bytes(b"{}")
    else:
        (packet.root / source.PACKAGE_PATH / "unused").mkdir()
    with pytest.raises((ValueError, OSError)):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize(
    "path",
    [
        "../source.json",
        "/source.json",
        "a//b",
        "a/./b",
        "a\\b",
        "C:source",
        "source.json.",
        "NUL",
        "source.json ",
    ],
)
def test_unsafe_relative_source_path(packet: Packet, path: str) -> None:
    packet.bundle["source_hashes"] = {path: next(iter(packet.bundle["source_hashes"].values()))}
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize("alias", [True, 1.0])
def test_artifact_byte_count_alias_is_rejected(packet: Packet, alias: object) -> None:
    packet.bundle["artifacts"]["staging.json"]["bytes"] = alias
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


def test_local_schema_cannot_fetch_network_reference(packet: Packet) -> None:
    _artifact(packet, "bundle.schema.json", {"$ref": "https://example.invalid/schema"})
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError, match="local"):
        source.load_physical_handoff(packet.root)


def test_schema_validates_after_its_hash(packet: Packet) -> None:
    _artifact(packet, "bundle.schema.json", {"type": "object", "required": ["missing"]})
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError, match="schema"):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize(
    "field", ["engine_operation", "operational_workflow_admitted", "backend_adoption_recorded"]
)
def test_false_flags_are_exact_bools(packet: Packet, field: str) -> None:
    packet.bundle[field] = 0
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


def test_source_path_case_aliases_rejected(packet: Packet) -> None:
    packet.bundle["source_hashes"]["SOURCE.json"] = packet.bundle["source_hashes"]["source.json"]
    packet.patch.setattr(source, "SOURCE_COUNT", 2)
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError, match="alias"):
        source.load_physical_handoff(packet.root)


class TextAlias(str):
    pass


@pytest.mark.parametrize("change", ["path_alias", "bytes_alias", "list", "extra", "rehash"])
def test_retained_record_and_descriptor_mutations(packet: Packet, change: str) -> None:
    bound = source.load_physical_handoff(packet.root)
    first = bound.documents[0]
    if change == "path_alias":
        bound = replace(
            bound, documents=(replace(first, path=TextAlias(first.path)), *bound.documents[1:])
        )
    elif change == "bytes_alias":
        bound = replace(bound, bundle_raw=bytearray(bound.bundle_raw))  # type: ignore[arg-type]
    elif change == "list":
        bound = replace(bound, documents=list(bound.documents))  # type: ignore[arg-type]
    elif change == "extra":
        extra = HandoffDocument("foreign", b"x", sha256(b"x").hexdigest())
        bound = replace(bound, documents=(*bound.documents, extra))
    else:
        record = parse_json(bound.frozen_bytes)
        record["operational_admission"] = 0
        raw = canonical_bytes(record)
        bound = replace(bound, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        source.verify_physical_handoff(bound)


def test_retained_raw_source_change_rejected(packet: Packet) -> None:
    bound = source.load_physical_handoff(packet.root)
    documents = tuple(
        replace(row, raw=b"{}", sha256=sha256(b"{}").hexdigest())
        if row.path == "source.json"
        else row
        for row in bound.documents
    )
    with pytest.raises(ValueError):
        source.verify_physical_handoff(replace(bound, documents=documents))


def test_unknown_section_refused(packet: Packet) -> None:
    with pytest.raises(ValueError):
        source.handoff_section(source.load_physical_handoff(packet.root), "not-a-section")


def test_hardlinked_source_is_rejected(packet: Packet, tmp_path: Path) -> None:
    link(packet.root / "source.json", tmp_path / "alias.json")
    with pytest.raises(ValueError, match="unshared"):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize("method", ["is_symlink", "is_junction"])
def test_ancestor_link_guard(packet: Packet, monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    original = getattr(Path, method)
    monkeypatch.setattr(Path, method, lambda path: path == packet.root or original(path))
    with pytest.raises(ValueError, match="links"):
        source.load_physical_handoff(packet.root)


def test_corrupt_schema_is_not_evaluated(packet: Packet, monkeypatch: pytest.MonkeyPatch) -> None:
    (packet.root / source.PACKAGE_PATH / "bundle.schema.json").write_bytes(b"not JSON")
    monkeypatch.setattr(
        source, "Draft202012Validator", lambda value: pytest.fail("schema evaluated")
    )
    with pytest.raises(ValueError, match="raw bytes"):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_strict_json_anchor_parser(packet: Packet, raw: bytes) -> None:
    (packet.root / source.PACKAGE_PATH / "bundle.json").write_bytes(raw)
    packet.patch.setattr(source, "BUNDLE_SHA256", sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("schema_id", "foreign.schema")])
def test_section_reference_mismatch(packet: Packet, field: str, value: str) -> None:
    packet.bundle["sections"]["staging"][field] = value
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


def test_retained_verification_uses_bytes_not_stale_root(packet: Packet) -> None:
    bound = source.load_physical_handoff(packet.root)
    (packet.root / "source.json").write_bytes(b"changed later")
    assert source.verify_physical_handoff(bound) == bound
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


def _share_artifact_source(packet: Packet, *, digest: str | None = None) -> str:
    name = source.PACKAGE_PATH + "/staging.json"
    packet.bundle["source_hashes"][name] = (
        packet.bundle["artifacts"]["staging.json"]["sha256"] if digest is None else digest
    )
    packet.patch.setattr(source, "SOURCE_COUNT", 2)
    packet.write_bundle(repin=True)
    return name


def test_identical_path_may_prove_both_artifact_and_current_source(packet: Packet) -> None:
    name = _share_artifact_source(packet)
    bound = source.load_physical_handoff(packet.root)
    assert len(bound.documents) == 7
    assert sum(document.path == name for document in bound.documents) == 1
    report = parse_json(bound.frozen_bytes)
    assert report["counts"] == {"artifacts": 6, "current_sources": 2}
    row = next(row for row in report["documents"] if row["path"] == name)
    assert row["roles"] == ["artifact", "current_source"]
    assert source.verify_physical_handoff(bound) == bound


def test_shared_path_cannot_hide_conflicting_source_hash(packet: Packet) -> None:
    _share_artifact_source(packet, digest="0" * 64)
    with pytest.raises(ValueError):
        source.load_physical_handoff(packet.root)


def test_shared_path_preserves_artifact_byte_length_requirement(packet: Packet) -> None:
    _share_artifact_source(packet)
    packet.bundle["artifacts"]["staging.json"]["bytes"] += 1
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError, match="raw bytes"):
        source.load_physical_handoff(packet.root)


def test_cross_role_case_alias_still_rejected(packet: Packet) -> None:
    name = _share_artifact_source(packet)
    packet.bundle["source_hashes"][name.upper()] = packet.bundle["source_hashes"].pop(name)
    packet.write_bundle(repin=True)
    with pytest.raises(ValueError, match="alias"):
        source.load_physical_handoff(packet.root)
