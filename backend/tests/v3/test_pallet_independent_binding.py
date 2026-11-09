"""Fresh pinned bytes and both directed PALLET permissions remain mandatory."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from shutil import copytree
from types import MappingProxyType

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.mesh_proof_source import ACTION_PATH
from app.v3.pallet_cycle_bridge import validate_bridge_source
from app.v3.pallet_cycle_engine import PalletCycleEngine
from app.v3.pallet_cycle_proof import validate_proof
from app.v3.vehicle_package import load_repository_vehicle_adapter
from tests.v3.test_pallet_independent_helpers import (
    ARC,
    PROOF_ROOT,
    ROOT,
    hand_profile,
    physical,
    request,
)
from tests.v3.test_pallet_independent_helpers import (
    independent_proof_fixture as independent_proof_fixture,
)


def test_omitting_a_proved_interval_cannot_authorize_a_shorter_proof(
    independent_proof: LocalGeometryProof,
) -> None:
    shortened = replace(independent_proof, segments=independent_proof.segments[:-1])
    with pytest.raises(ValueError, match="proof"):
        validate_proof(PROOF_ROOT, shortened)


def test_self_consistent_changed_source_manifest_cannot_reuse_cached_proof(
    independent_proof: LocalGeometryProof,
    tmp_path: Path,
) -> None:
    root = tmp_path / "proof"
    copytree(PROOF_ROOT, root)
    assert validate_proof(root, independent_proof) is independent_proof
    path = root / ACTION_PATH
    action = json.loads(path.read_text(encoding="utf-8"))
    action["duration_s"] = 31
    raw = json.dumps(action).encode()
    path.write_bytes(raw)
    manifest_path = root / "provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(row for row in manifest["files"] if row["path"] == ACTION_PATH)
    row.update(
        bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        git_blob_sha1=hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest(),
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        validate_proof(root, independent_proof)


def test_source_approach_rejects_changed_raw_vehicle_document(
    independent_proof: LocalGeometryProof,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vehicle"
    copytree(ROOT / "v3-vehicle-proposal", root)
    graph = root / "docs/v3/contract-proposals/vehicle-graph-v3.json"
    graph.write_bytes(graph.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA256"):
        PalletCycleEngine(
            hand_profile(),
            (request("A"),),
            physical(independent_proof),
            PROOF_ROOT,
            independent_proof,
            source_approach=True,
            base_source_root=ROOT / "v3-proposal",
            vehicle_source_root=root,
        )


@pytest.mark.parametrize("restriction", ["cargo", "profile"])
def test_return_arc_must_itself_permit_pallet_and_nonlong_profile(restriction: str) -> None:
    adapter = load_repository_vehicle_adapter(ROOT / "v3-proposal", ROOT / "v3-vehicle-proposal")
    arcs = dict(adapter.graph.arcs)
    arc = arcs[ARC + "f"]
    arcs[arc.arc_id] = (
        replace(arc, cargo_classes=frozenset({"SMALL_CARTON"}))
        if restriction == "cargo"
        else replace(arc, profiles=frozenset({"long_forklift"}))
    )
    altered = replace(adapter, graph=replace(adapter.graph, arcs=MappingProxyType(arcs)))
    with pytest.raises(ValueError, match="PALLET"):
        validate_bridge_source(altered)
