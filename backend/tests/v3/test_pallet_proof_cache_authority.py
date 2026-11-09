"""Caller mutations must not turn a cached geometry result into its own authority."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from app.v3 import pallet_cycle_proof
from app.v3.mesh_proof_fixture import METHOD_VERSION, LocalGeometryProof
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture


@pytest.fixture
def isolated_cache(proven: LocalGeometryProof, monkeypatch: pytest.MonkeyPatch) -> None:
    # The source proof is verified by the existing session fixture. Isolate deliberate
    # corruption from other tests; this fixture does not replace raw source validation.
    monkeypatch.setattr(
        pallet_cycle_proof,
        "_PROVEN",
        {
            (METHOD_VERSION, proven.bindings): deepcopy(proven),
        },
    )


def test_mutated_returned_mesh_hash_cannot_poison_future_certification(
    isolated_cache: None,
    proven: LocalGeometryProof,
) -> None:
    supplied = pallet_cycle_proof.certified_geometry(SOURCE)
    object.__setattr__(supplied, "mesh_sha256", "0" * 64)
    current = pallet_cycle_proof.certified_geometry(SOURCE)
    assert current.mesh_sha256 == proven.mesh_sha256
    with pytest.raises(ValueError, match="proof"):
        pallet_cycle_proof.validate_proof(SOURCE, supplied)


def test_nested_contact_mutation_cannot_change_the_cached_reference(
    isolated_cache: None,
    proven: LocalGeometryProof,
) -> None:
    supplied = pallet_cycle_proof.certified_geometry(SOURCE)
    object.__setattr__(supplied.contacts[0].patch, "area_m2", proven.contacts[0].patch.area_m2 + 1)
    with pytest.raises(ValueError, match="proof"):
        pallet_cycle_proof.validate_proof(SOURCE, supplied)
    assert pallet_cycle_proof.certified_geometry(SOURCE).contacts == proven.contacts


def test_validated_return_remains_caller_owned_and_cannot_mutate_cache(
    isolated_cache: None,
    proven: LocalGeometryProof,
) -> None:
    supplied = pallet_cycle_proof.certified_geometry(SOURCE)
    validated = pallet_cycle_proof.validate_proof(SOURCE, supplied)
    assert validated is supplied
    object.__setattr__(validated, "triangle_count", 0)
    assert pallet_cycle_proof.certified_geometry(SOURCE).triangle_count == proven.triangle_count
    with pytest.raises(ValueError, match="proof"):
        pallet_cycle_proof.validate_proof(SOURCE, validated)


def test_mutable_nested_sequence_cannot_alias_an_immutable_proof(
    isolated_cache: None,
    proven: LocalGeometryProof,
) -> None:
    changed: Any = list(proven.segments)
    with pytest.raises(ValueError, match="proof"):
        pallet_cycle_proof.validate_proof(SOURCE, replace(proven, segments=changed))
