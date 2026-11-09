"""New conditional fit evidence cannot inherit an old pair or become a runtime grant."""

import subprocess
import sys
from dataclasses import replace
from typing import Any

import pytest

from app.v3.pallet_operator_fit_models import OperatorFitCertificate, OperatorFitSource
from app.v3.pallet_operator_fit_verify import certify_operator_fit, verify_operator_fit_certificate
from app.v3.pallet_outbound_pickup_identity import identity
from app.v3.pallet_outbound_pickup_models import PickupPlan
from app.v3.pallet_outbound_pickup_plan import compile_pickup_plan
from tests.v3.test_pallet_operator_fit_fixtures import BACKEND, source


@pytest.fixture(scope="module")
def evidence() -> tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate]:
    inputs = source()
    plan = compile_pickup_plan(inputs.pickup)
    return inputs, plan, certify_operator_fit(inputs, plan)


def test_fresh_actual_F02_FL02_conditional_evidence(
    evidence: tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate],
) -> None:
    inputs, plan, result = evidence
    assert (result.actor_id, result.vehicle_id, result.pair_id) == (
        "F02",
        "FL02",
        "OUTBOUND_FORKLIFT_PAIR",
    )
    assert result.source_hash == inputs.source_hash and result.pickup_plan_hash == plan.plan_hash
    assert (result.checks.body_solids, result.checks.vehicle_solids) == (57, 68)
    assert result.checks.body_triangles == 2848
    assert result.checks.interval_cover_checks == (18,) * 6
    assert result.checks.wheel_cover_checks == 12
    assert len(result.checks.anchors) == 5
    assert result.conditional_body_root_world == pytest.approx((122.585, 0.29, 29.5))
    assert result.operational_admission is False
    assert result.actual_initial_state_proved is False
    assert result.boarding_path_proved is False
    assert result.travel_admission is False
    fresh = verify_operator_fit_certificate(inputs, plan, result)
    assert fresh == result and fresh is not result


@pytest.mark.parametrize("field,value", [("actor_id", "F01"), ("vehicle_id", "FL01")])
def test_old_pair_plan_never_inherits_outbound_identity(
    evidence: tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate],
    field: str,
    value: Any,
) -> None:
    inputs, plan, _ = evidence
    changed = replace(plan, **{field: value, "plan_hash": ""})
    changed = replace(changed, plan_hash=identity(changed))
    with pytest.raises(ValueError):
        certify_operator_fit(inputs, changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operational_admission", 0),
        ("actual_initial_state_proved", True),
        ("boarding_path_proved", True),
        ("travel_admission", True),
        ("actor_id", "F01"),
        ("method", "old-inbound-proof"),
        ("conditional_body_root_world", (122.585, 0.29, 29.6)),
    ],
)
def test_rehashed_certificate_metadata_is_not_authority(
    evidence: tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate],
    field: str,
    value: Any,
) -> None:
    inputs, plan, result = evidence
    changed = replace(result, **{field: value, "certificate_hash": ""})
    changed = replace(changed, certificate_hash=identity(changed))
    with pytest.raises(ValueError):
        verify_operator_fit_certificate(inputs, plan, changed)


def test_rehashed_fake_contact_requires_recomputed_mesh(
    evidence: tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate],
) -> None:
    inputs, plan, result = evidence
    first, *others = result.checks.contacts
    contacts = (replace(first, patch=replace(first.patch, area_m2=9.0)), *others)
    changed = replace(result, checks=replace(result.checks, contacts=contacts), certificate_hash="")
    changed = replace(changed, certificate_hash=identity(changed))
    with pytest.raises(ValueError):
        verify_operator_fit_certificate(inputs, plan, changed)


def test_public_import_has_no_engine_scheduler_or_ledger() -> None:
    code = (
        "import sys; import app.v3.pallet_operator_fit_verify; "
        "bad=[m for m in sys.modules if m=='simpy' or m.startswith('app.v3.coordinator') "
        "or m.startswith('app.v3.pallet_shared') or m=='app.v3.stock_ledger']; "
        "assert not bad, bad"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], check=False, capture_output=True, text=True, cwd=BACKEND
    )
    assert result.returncode == 0, result.stderr


def test_rehashed_nested_numeric_alias_rejects(
    evidence: tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate],
) -> None:
    inputs, plan, result = evidence
    checks = replace(result.checks, body_solids=57.0)  # type: ignore[arg-type]
    changed = replace(result, checks=checks, certificate_hash="")
    changed = replace(changed, certificate_hash=identity(changed))
    with pytest.raises(ValueError):
        verify_operator_fit_certificate(inputs, plan, changed)


def test_rehashed_different_motion_cannot_reuse_seating_certificate(
    evidence: tuple[OperatorFitSource, PickupPlan, OperatorFitCertificate],
) -> None:
    inputs, plan, result = evidence
    first = replace(plan.segments[0], phase="other-motion")
    changed = replace(plan, segments=(first, *plan.segments[1:]), plan_hash="")
    changed = replace(changed, plan_hash=identity(changed))
    with pytest.raises(ValueError):
        verify_operator_fit_certificate(inputs, changed, result)
