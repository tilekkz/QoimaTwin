"""Caller flags and self-consistent edited proof records cannot authorize motion."""

from dataclasses import replace
from pathlib import Path
from shutil import copytree

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_proof import certified_geometry, validate_proof
from tests.v3.test_pallet_cycle_clock import SOURCE


@pytest.fixture(name="proven", scope="session")
def proven_fixture() -> LocalGeometryProof:
    return certified_geometry(SOURCE)


def test_current_complete_source_binding_is_accepted(proven: LocalGeometryProof) -> None:
    assert validate_proof(SOURCE, proven) == proven
    assert proven.operational_admission is False


@pytest.mark.parametrize("field", ["method_version", "mesh_sha256", "action_sha256", "scope"])
def test_stale_or_wrong_proof_is_rejected(proven: LocalGeometryProof, field: str) -> None:
    variants = {
        "method_version": replace(proven, method_version="wrong"),
        "mesh_sha256": replace(proven, mesh_sha256="wrong"),
        "action_sha256": replace(proven, action_sha256="wrong"),
        "scope": replace(proven, scope="wrong"),
    }
    with pytest.raises(ValueError, match="proof"):
        validate_proof(SOURCE, variants[field])


def test_forged_contact_measurement_is_rejected(proven: LocalGeometryProof) -> None:
    first = proven.contacts[0]
    changed = replace(first, patch=replace(first.patch, area_m2=first.patch.area_m2 + 1))
    with pytest.raises(ValueError, match="proof"):
        validate_proof(SOURCE, replace(proven, contacts=(changed, *proven.contacts[1:])))


def test_cache_does_not_hide_changed_source_bytes(
    proven: LocalGeometryProof, tmp_path: Path
) -> None:
    root = tmp_path / "source"
    copytree(SOURCE, root)
    assert validate_proof(root, proven) == proven
    action = root / "frontend/public/data/v3/pallet-pickup-cycle.json"
    action.write_bytes(action.read_bytes() + b" ")
    with pytest.raises(ValueError):
        validate_proof(root, proven)
