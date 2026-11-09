"""Actual pinned GLB proof; expectations are source declarations, not engine output."""

from pathlib import Path
from shutil import copytree

import pytest

from app.v3.mesh_proof_fixture import verify_repository_pallet_fixture
from app.v3.mesh_proof_types import MeshProofError

SOURCE = Path(__file__).resolve().parents[2] / "data" / "v3-mesh-proof-proposal"


def test_actual_glb_has_continuous_clearance_and_finite_support() -> None:
    proof = verify_repository_pallet_fixture(SOURCE)
    assert proof.operational_admission is False
    assert proof.scope == "isolated_fixed_yaw_pallet_fixture"
    assert len(proof.segments) == 13  # Fourteen published pose keys, adjacent intervals.
    assert proof.mesh_sha256 == "b172dc6dd245208a49fdddebccd6ff5d64cc3771c4e0259dabdd633adbd2808a"
    assert proof.action_sha256 == "9a37e18d64d9cb63718e504773f99a472783531a8b8a22e07276c847aae4cb59"
    assert all(contact.patch.area_m2 > 0 for contact in proof.contacts)
    assert {"fork_L", "fork_R", "platform"} == {c.support for c in proof.contacts}
    assert proof.same_hu is True


def test_wrong_or_missing_bound_source_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(MeshProofError):
        verify_repository_pallet_fixture(tmp_path)


@pytest.mark.parametrize(
    "relative", ["provenance.json", "frontend/public/models/v3/forklift-pallet-low-fixture.glb"]
)
def test_changed_repository_bytes_cannot_reuse_source_identity(
    tmp_path: Path, relative: str
) -> None:
    root = tmp_path / "proof"
    copytree(SOURCE, root)
    target = root / relative
    payload = bytearray(target.read_bytes())
    payload[-1] ^= 1
    target.write_bytes(payload)
    with pytest.raises(MeshProofError, match=r"changed|mismatch"):
        verify_repository_pallet_fixture(root)
