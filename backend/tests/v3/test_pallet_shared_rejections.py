"""Unsupported full-source/receipt claims are explicit, not fabricated successes."""

from dataclasses import replace

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_shared_engine import PalletSharedEngine
from app.v3.pallet_shared_models import PalletSharedError
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture
from tests.v3.test_pallet_shared_fixtures import shared_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


@pytest.mark.parametrize(
    "change,reason",
    [
        ("source", "UNSUPPORTED_SOURCE_INITIAL_PLACEMENT"),
        ("receipt", "UNSUPPORTED_PALLET_RECEIPT"),
        ("slot", "UNSUPPORTED_PALLET_SLOT"),
        ("driver", "INITIAL_SEATED_DRIVER_REQUIRED"),
    ],
)
def test_explicit_unsupported_boundaries(
    proven: LocalGeometryProof,
    change: str,
    reason: str,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    if change == "source":
        profile = replace(profile, inventory_scope="source")
    elif change == "receipt":
        profile = replace(profile, jobs=(replace(profile.jobs[0], operation="receipt"),))
    elif change == "slot":
        profile = replace(profile, platform_id="v3:slot:HEAVY_E:002:L1:B1")
    else:
        profile = replace(profile, initial_driver_state="walking")
    with pytest.raises(PalletSharedError) as error:
        PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    assert error.value.code == reason


def test_original_proof_cannot_be_replaced_by_self_declared_pass(
    proven: LocalGeometryProof,
) -> None:
    forged = replace(proven, mesh_sha256="0" * 64)
    with pytest.raises(ValueError):
        PalletSharedEngine(shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, forged)


def test_a_small_hu_is_not_authorized_by_the_pallet_geometry_proof(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    profile = replace(profile, hu_id="HU1", jobs=(replace(profile.jobs[0], hu_id="HU1"),))
    with pytest.raises(PalletSharedError) as error:
        PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    assert error.value.code == "UNSUPPORTED_PALLET_CLASS"


def test_boolean_ready_time_is_not_an_integer_microsecond(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    object.__setattr__(profile.jobs[0], "ready_tick", False)
    with pytest.raises(PalletSharedError) as error:
        PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    assert error.value.code == "INVALID_PALLET_JOB"


def test_cycle_cannot_materialize_an_undeclared_pallet(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    profile = replace(
        profile, hu_id="future-PALLET", jobs=(replace(profile.jobs[0], hu_id="future-PALLET"),)
    )
    with pytest.raises(PalletSharedError) as error:
        PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    assert error.value.code == "EXISTING_PALLET_REQUIRED"


@pytest.mark.parametrize("field", ["hu_id", "driver_anchor", "model_sha256"])
def test_local_physical_identities_require_exact_text(
    proven: LocalGeometryProof,
    field: str,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    object.__setattr__(profile, field, True)
    with pytest.raises(PalletSharedError) as error:
        PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    assert error.value.code == "TYPED_PALLET_IDENTITY_REQUIRED"
