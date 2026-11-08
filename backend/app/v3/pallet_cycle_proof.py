"""A cached recomputation is reusable only after every raw source is revalidated."""

from dataclasses import asdict
from pathlib import Path

from app.storage.canonical_json import canonical_bytes
from app.v3.mesh_proof_fixture import (
    METHOD_VERSION,
    LocalGeometryProof,
    verify_repository_pallet_fixture,
)
from app.v3.mesh_proof_source import load_fixture

_PROVEN: dict[tuple[str, tuple[tuple[str, str], ...]], LocalGeometryProof] = {}


def certified_geometry(proof_root: Path) -> LocalGeometryProof:
    """Recompute once per immutable source set; never trust a caller PASS flag."""
    fixture = load_fixture(proof_root)
    key = METHOD_VERSION, fixture.hashes
    if key not in _PROVEN:
        _PROVEN[key] = verify_repository_pallet_fixture(proof_root)
    return _PROVEN[key]


def validate_proof(proof_root: Path, supplied: LocalGeometryProof) -> LocalGeometryProof:
    if type(supplied) is not LocalGeometryProof or supplied.method_version != METHOD_VERSION:
        raise ValueError("unsupported or stale local geometry proof")
    if supplied.operational_admission is not False or supplied.same_hu is not True:
        raise ValueError("proof scope cannot grant warehouse admission or clone a HU")
    current = certified_geometry(proof_root)
    if canonical_bytes(asdict(supplied)) != canonical_bytes(asdict(current)):
        raise ValueError("proof differs from independently verified source-bound evidence")
    return current
