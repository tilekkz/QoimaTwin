"""Pinned raw source and exact retained types remain authority, not caller hashes."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from app.v3.pallet_receipt_requirements import (
    compile_pallet_receipt_requirements,
    verify_pallet_receipt_requirements,
)
from tests.v3.test_pallet_receipt_requirements import BASE, VEHICLE, request


def test_false_capacity_alias_cannot_inherit_a_retained_source_hash() -> None:
    value = compile_pallet_receipt_requirements(BASE, VEHICLE, request())
    forged_port = replace(value.port)
    object.__setattr__(forged_port, "bay_capacity", True)
    with pytest.raises(ValueError):
        verify_pallet_receipt_requirements(BASE, VEHICLE, replace(value, port=forged_port))


def test_same_request_recompiles_to_identical_prospective_requirements() -> None:
    first = compile_pallet_receipt_requirements(BASE, VEHICLE, request())
    second = compile_pallet_receipt_requirements(BASE, VEHICLE, request())
    assert first == second and first.requirements_hash == second.requirements_hash
    changed = compile_pallet_receipt_requirements(
        BASE, VEHICLE, replace(request(), receipt_id="new-R2", hu_id="new-HU2", lot_id="new-lot2")
    )
    assert changed.requirements_hash != first.requirements_hash


def test_changed_raw_port_source_is_rejected_even_after_valid_compilation(tmp_path: Path) -> None:
    compile_pallet_receipt_requirements(BASE, VEHICLE, request())
    copied = tmp_path / "base"
    shutil.copytree(BASE, copied)
    path = copied / "docs/v3/contract-proposals/ports-v3.inbound.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match=r"SHA256|pinned"):
        compile_pallet_receipt_requirements(copied, VEHICLE, request())
