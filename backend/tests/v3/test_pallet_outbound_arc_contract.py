"""One source-bound first arc, no engine or operational travel grant."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.v3.pallet_outbound_arc_plan import compile_arc_plan, verify_arc_plan
from app.v3.pallet_outbound_arc_verify import certify_arc, verify_arc_certificate
from app.v3.pallet_outbound_pickup_identity import identity
from app.v3.pallet_outbound_pickup_models import PickupCertificate, PickupPlan, PickupSource
from app.v3.pallet_outbound_pickup_plan import compile_pickup_plan
from app.v3.pallet_outbound_pickup_source import load_pickup_source
from app.v3.pallet_outbound_pickup_verify import certify_pickup


@pytest.fixture(scope="module")
def pickup() -> tuple[PickupSource, PickupPlan, PickupCertificate]:
    source = load_pickup_source(Path(__file__).resolve().parents[2] / "data")
    plan = compile_pickup_plan(source)
    return source, plan, certify_pickup(source, plan)


def test_exact_first_arc_preserves_pickup_and_pending_policy(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
) -> None:
    plan = compile_arc_plan(*pickup)
    assert plan.arc_id == "v3:module:HEAVY_E:011:B1:vehicle:segment:002:r"
    assert plan.start == pickup[1].segments[-1].end
    assert plan.end.root_z == F(-1) - F("0.7917096231345369")
    assert plan.motion_direction == -1 and plan.unit_ids == pickup[1].unit_ids
    assert plan.padding_m == plan.top_padding_m == F(1, 4)
    assert plan.destination_stop_allowed is None
    result = certify_arc(*pickup, plan)
    assert result.cover_checks == 333 and result.moving_solids == 152
    assert len(result.contacts) == 4
    assert len(result.obstacles.module_ids) == 132 and len(result.obstacles.hu_ids) == 529
    assert result.obstacles.minimum_module_gap_m == pytest.approx(0.3, abs=2e-6)
    assert result.obstacles.minimum_hu_gap_m >= 0.79
    assert result.obstacles.top_headroom_m > 5.64
    assert not result.operational_admission and not plan.operational_admission
    assert (
        result.travel_orientation_status
        == "NOT_ADMITTED_PENDING_EXPLICIT_PALLET_SIGNED_FRAME_BINDING"
    )
    assert result.relative_hu_yaw_rad == pytest.approx(3.141592653589793)
    verify_arc_certificate(*pickup, plan, result)
    assert certify_arc(*pickup, plan) == result


@pytest.mark.parametrize(
    "field,value",
    [
        ("motion_direction", True),
        ("arc_id", "invented"),
        ("padding_m", F(1, 10)),
        ("destination_stop_allowed", True),
        ("hu_id", "clone"),
        ("source_yaw_rad", 0.0),
    ],
)
def test_retained_rehashed_plan_cannot_change_source(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    field: str,
    value: Any,
) -> None:
    plan = compile_arc_plan(*pickup)
    forged = replace(plan, **{field: value}, plan_hash="")
    forged = replace(forged, plan_hash=identity(forged))
    with pytest.raises(ValueError):
        verify_arc_plan(*pickup, forged)


def test_rehashed_raw_source_and_pickup_certificate_reject(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
) -> None:
    source, plan, certificate = pickup
    doc = source.documents[1]
    changed = replace(doc, raw=doc.raw + b" ")
    altered = replace(
        source, documents=(source.documents[0], changed, *source.documents[2:]), source_hash=""
    )
    altered = replace(altered, source_hash=identity(altered))
    with pytest.raises(ValueError):
        compile_arc_plan(altered, plan, certificate)
    forged = replace(certificate, relative_hu_yaw_rad=0.0, certificate_hash="")
    forged = replace(forged, certificate_hash=identity(forged))
    with pytest.raises(ValueError):
        compile_arc_plan(source, plan, forged)


@pytest.mark.parametrize(
    "field,value", [("cover_checks", True), ("moving_solids", 152.0), ("operational_admission", 0)]
)
def test_rehashed_certificate_aliases_do_not_bypass_recomputation(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    field: str,
    value: Any,
) -> None:
    plan = compile_arc_plan(*pickup)
    certificate = certify_arc(*pickup, plan)
    forged = replace(certificate, **{field: value}, certificate_hash="")
    forged = replace(forged, certificate_hash=identity(forged))
    with pytest.raises(ValueError):
        verify_arc_certificate(*pickup, plan, forged)
