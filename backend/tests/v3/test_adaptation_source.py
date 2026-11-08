"""C11 planning pin: exact identity of six Tilek documents, kept apart from the 14-file baseline.

Expected hashes are the audited Tilek blobs (`v3-tilek-be9b4da-audit/report.json`, unchanged at
c661a726), not adapter output.
"""

import json
import shutil
from pathlib import Path

import pytest

from app.v3.adaptation_source import AdaptationSourceError, load_adaptation_package
from app.v3.inputs import load_v3_bundle

BACKEND = Path(__file__).parents[2]
PACKAGE = BACKEND / "data/v3-adaptation-proposal"
BASE = BACKEND / "data/v3-proposal"
PREFIX = "docs/v3/contract-proposals/"
AUDITED = {
    "adaptation-input-v3.json": (
        "5b9f294e4ac3f36bd196dcde5853432f394a7276f9fc4256e4d59a1a9aed8e23",
        "d598d98ddf7f7614625fee2e7f79b0072585e5e2",
    ),
    "adaptation-evaluation-v3.json": (
        "9237c019b9995e318c473688f8dbe54278eb1394d3a310fda1347bb9d931a3c5",
        "ea0786ba398c7330da4a7b48c43ed3b3792d4c62",
    ),
    "adapted-assignment-v3.json": (
        "57c6cde798b08c6d45da7acb311d13f81a31cd127e6352ddc7089ea818179b04",
        "6efb772d6966bcffa47760f66d66b9831ef27489",
    ),
    "adapted-assignment-horizon2-v3.json": (
        "be67f3dbd8c1e9e65be82f2b0791000251259ae938486abfce43e2bf5f179ee3",
        "ab59eea5ffb5fcabffd74b6141f693a38c189bfc",
    ),
    "adapted-assignment-horizon4-v3.json": (
        "e4a663f975acabfd333df56f7f4451fd88d503635c77a74ab772e4b5a2ea02b1",
        "f2916f0904793ddb89aaf3b77b049e4a9ef17210",
    ),
    "adapted-assignment-horizon8-v3.json": (
        "e1fe62e7fc9dd86f07b6a40f41774ab4055ebe67c06653f1f43e31895df885ea",
        "007566b2c53396fd25ebd26dc42091ec9545d0e7",
    ),
}


def test_six_documents_are_pinned_with_audited_raw_and_blob_ids() -> None:
    package = load_adaptation_package(PACKAGE, BASE)
    assert package.source_revision == "be9b4da9b93b2c99aacfd048b8cd3846c91efc82"
    assert {e.path: (e.raw_sha256, e.git_blob_sha1) for e in package.entries} == {
        PREFIX + name: ids for name, ids in AUDITED.items()
    }
    assert package.comparison_inputs_sha256_verified is False
    assert package.baseline_assignment_sha256 == (
        "576785a5893594517b4af5b8e888c7c20fe01c16c8ab901fd6191872a65c7939"
    )


def test_existing_baseline_package_and_loader_are_unchanged() -> None:
    bundle = load_v3_bundle(BASE)
    assert len(bundle.source_inventory) == 14
    assert bundle.source_revision == "22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec"
    assert not any("adapt" in entry.path for entry in bundle.source_inventory)


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "package"
    shutil.copytree(PACKAGE, target)
    return target


def test_changed_document_byte_is_rejected(tmp_path: Path) -> None:
    target = _copy(tmp_path)
    path = target / PREFIX / "adapted-assignment-horizon2-v3.json"
    raw = bytearray(path.read_bytes())
    raw[-2:-1] = b" "
    path.write_bytes(bytes(raw))
    with pytest.raises(AdaptationSourceError, match="mismatch"):
        load_adaptation_package(target, BASE)


def test_rehashed_manifest_is_rejected_by_the_provenance_pin(tmp_path: Path) -> None:
    target = _copy(tmp_path)
    manifest = json.loads((target / "provenance.json").read_bytes())
    manifest["comparison_inputs_sha256_method_established"] = True
    (target / "provenance.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AdaptationSourceError, match="provenance"):
        load_adaptation_package(target, BASE)


def test_swapped_horizon_documents_are_rejected(tmp_path: Path) -> None:
    target = _copy(tmp_path)
    h2, h4 = (target / PREFIX / f"adapted-assignment-horizon{h}-v3.json" for h in (2, 4))
    first, second = h2.read_bytes(), h4.read_bytes()
    h2.write_bytes(second)
    h4.write_bytes(first)
    with pytest.raises(AdaptationSourceError, match="mismatch"):
        load_adaptation_package(target, BASE)
