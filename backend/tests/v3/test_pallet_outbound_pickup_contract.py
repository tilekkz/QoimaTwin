"""Independent retained V5 source endpoint oracles; no scheduler or engine runs."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from app.v3.pallet_outbound_pickup_identity import identity
from app.v3.pallet_outbound_pickup_models import PickupCertificate, PickupPlan, PickupSource
from app.v3.pallet_outbound_pickup_plan import compile_pickup_plan
from app.v3.pallet_outbound_pickup_source import load_pickup_source, verify_pickup_source
from app.v3.pallet_outbound_pickup_verify import certify_pickup, verify_pickup_certificate

DATA = Path(__file__).resolve().parents[2] / "data"
HU = "v3:HU:initial:DEMO_172:01"


@pytest.fixture(scope="module")
def source() -> PickupSource:
    return load_pickup_source(DATA)


@pytest.fixture(scope="module")
def plan(source: PickupSource) -> PickupPlan:
    return compile_pickup_plan(source)


@pytest.fixture(scope="module")
def certificate(source: PickupSource, plan: PickupPlan) -> PickupCertificate:
    return certify_pickup(source, plan)


def test_original_source_identity_and_proposed_action(plan: PickupPlan) -> None:
    assert (plan.hu_id, plan.actor_id, plan.vehicle_id) == (HU, "F02", "FL02")
    assert plan.slot_id == "v3:slot:HEAVY_E:011:L1:B1"
    assert plan.unit_ids == tuple(f"{HU}:unit:{i:04d}" for i in range(1, 25))
    assert plan.source_root_world == (123.2, 0.0, 29.5)
    assert plan.frame_origin_world == pytest.approx((124.2, 0.0, 29.5))
    assert plan.source_yaw_rad == 1.5707963267948966
    assert plan.hu_yaw_rad == 4.71238898038469
    assert plan.hu_bottom_world == pytest.approx((125.6, 0.18, 29.5))
    assert plan.operational_admission is False
    assert plan.positive_fore_aft_clearance is False
    assert plan.pose_policy == "proposed_six_step_exact_prehandle_v1"
    expected = (
        (-1, ".7", 0),
        (-1, ".7", ".4"),
        (-1, ".18", ".4"),
        (0, ".18", ".4"),
        (0, ".7", ".4"),
        (0, ".7", 0),
        (-1, ".7", 0),
    )
    poses = (plan.segments[0].start, *(s.end for s in plan.segments))
    assert tuple((p.root_z, p.fork_top, p.reach) for p in poses) == tuple(
        tuple(Fraction(x) for x in row) for row in expected
    )
    assert tuple(s.attached for s in plan.segments) == (False, False, False, True, True, True)


def test_six_continuous_intervals_and_actual_contacts(certificate: PickupCertificate) -> None:
    assert certificate.segment_cover_checks == (228, 228, 228, 333, 333, 333)
    assert (
        certificate.mesh_sha256
        == "b172dc6dd245208a49fdddebccd6ff5d64cc3771c4e0259dabdd633adbd2808a"
    )
    platform = [c for c in certificate.contacts if c.support == "heavy-bay__MODULE"]
    assert len(platform) == 1
    assert platform[0].patch.area_m2 == pytest.approx(0.3433920560674625, abs=1e-12)
    assert platform[0].support_margin_m == pytest.approx(0.49799996614456177, abs=1e-12)
    forks = [c for c in certificate.contacts if c.support != "heavy-bay__MODULE"]
    assert len(forks) == 8
    assert {c.pose_index for c in forks} == {3, 4, 5, 6}
    assert all(c.patch.area_m2 == pytest.approx(0.046371937248251, abs=1e-12) for c in forks)
    assert all(c.support_margin_m == pytest.approx(0.4397533720790782, abs=1e-12) for c in forks)


def test_bound_obstacles_and_loaded_first_arc_seam(certificate: PickupCertificate) -> None:
    assert len(certificate.obstacles.module_ids) == 131
    assert len(certificate.obstacles.hu_ids) == 529
    assert certificate.obstacles.minimum_axis_gap_m == pytest.approx(0.399999927145398, abs=1e-12)
    assert certificate.endpoint_root_world == (123.2, 0.0, 29.5)
    assert certificate.endpoint_axle_world == pytest.approx((123.6, 0.0, 29.5))
    assert certificate.first_arc_id == "v3:module:HEAVY_E:011:B1:vehicle:segment:002:r"
    assert certificate.endpoint_bounds.low == pytest.approx((121.7, 0, 28.9), abs=2e-6)
    assert certificate.endpoint_bounds.high == pytest.approx((124.7, 2.1, 30.1), abs=2e-6)
    assert certificate.operational_admission is False
    assert certificate.positive_fore_aft_clearance is False
    assert "loaded_route_not_proved" in certificate.limitations
    assert "seated_F02_not_proved" in certificate.limitations


def test_strict_certificate_roundtrip(
    source: PickupSource, plan: PickupPlan, certificate: PickupCertificate
) -> None:
    verify_pickup_certificate(source, plan, certificate)


def test_source_C08_policy_blocks_preserved_relative_yaw(certificate: PickupCertificate) -> None:
    assert certificate.relative_hu_yaw_rad == 3.141592653589793
    assert (
        certificate.travel_orientation_status
        == "not_admitted_pending_C08_relative_yaw_frame_binding"
    )
    assert "nominal_job_load_frame_semantics_not_resolved" in certificate.limitations
    assert certificate.operational_admission is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_id", "F01"),
        ("vehicle_id", "FL01"),
        ("hu_id", HU + ":other"),
        ("hu_yaw_rad", 1.5707963267948966),
        ("operational_admission", 0),
        ("positive_fore_aft_clearance", True),
        ("source_hash", "0" * 64),
        ("source_root_world", (123.2, False, 29.5)),
    ],
)
def test_plan_changes_never_inherit_source_authority(
    source: PickupSource, plan: PickupPlan, field: str, value: Any
) -> None:
    with pytest.raises(ValueError):
        certify_pickup(source, replace(plan, **{field: value}))


def test_numeric_alias_in_proposed_pose_rejects(source: PickupSource, plan: PickupPlan) -> None:
    first = plan.segments[0]
    changed = replace(first, start=replace(first.start, root_z=-1))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        certify_pickup(source, replace(plan, segments=(changed, *plan.segments[1:])))


def test_duplicate_original_unit_id_rejects(source: PickupSource, plan: PickupPlan) -> None:
    with pytest.raises(ValueError):
        certify_pickup(source, replace(plan, unit_ids=(plan.unit_ids[0],) * 24))


@pytest.mark.parametrize(
    "field,value",
    [
        ("operational_admission", 0),
        ("positive_fore_aft_clearance", True),
        ("segment_cover_checks", (True, 228, 228, 333, 333, 333)),
        ("endpoint_root_world", (123.15, 0.0, 29.5)),
        ("certificate_hash", "0" * 64),
        ("source_hash", "f" * 64),
    ],
)
def test_claimed_certificate_requires_fresh_geometry(
    source: PickupSource,
    plan: PickupPlan,
    certificate: PickupCertificate,
    field: str,
    value: Any,
) -> None:
    with pytest.raises(ValueError):
        verify_pickup_certificate(source, plan, replace(certificate, **{field: value}))


def test_raw_source_and_shape_tampering_reject(source: PickupSource) -> None:
    first = source.documents[0]
    bad = replace(first, raw=first.raw + b" ")
    with pytest.raises(ValueError):
        verify_pickup_source(replace(source, documents=(bad, *source.documents[1:])))
    with pytest.raises(ValueError):
        verify_pickup_source(replace(source, documents=source.documents[:-1]))


def test_missing_source_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_pickup_source(tmp_path)


@pytest.mark.parametrize(
    "suffix",
    [
        "baseline-assignment-v3.json",
        "storage-slots-v3.json",
        "forklift-pallet-low-fixture.glb",
        "provenance.json",
    ],
)
def test_rehashed_wrong_raw_input_cannot_self_certify(source: PickupSource, suffix: str) -> None:
    documents = list(source.documents)
    index = next(i for i, d in enumerate(documents) if d.path.endswith(suffix))
    documents[index] = replace(documents[index], raw=documents[index].raw + b" ")
    changed = replace(source, documents=tuple(documents), source_hash="")
    changed = replace(changed, source_hash=identity(changed))
    with pytest.raises(ValueError, match=r"source|provenance"):
        verify_pickup_source(changed)


def test_rehashed_plan_cannot_change_source_heading(source: PickupSource, plan: PickupPlan) -> None:
    changed = replace(plan, hu_yaw_rad=plan.source_yaw_rad, plan_hash="")
    changed = replace(changed, plan_hash=identity(changed))
    with pytest.raises(ValueError):
        certify_pickup(source, changed)


def test_rehashed_false_contact_cannot_self_certify(
    source: PickupSource, plan: PickupPlan, certificate: PickupCertificate
) -> None:
    first = certificate.contacts[0]
    changed_patch = replace(first.patch, area_m2=1.0)
    changed = replace(
        certificate,
        contacts=(replace(first, patch=changed_patch), *certificate.contacts[1:]),
        certificate_hash="",
    )
    changed = replace(changed, certificate_hash=identity(changed))
    with pytest.raises(ValueError):
        verify_pickup_certificate(source, plan, changed)


def test_numeric_equal_contact_metadata_is_not_exact_type(
    source: PickupSource, plan: PickupPlan, certificate: PickupCertificate
) -> None:
    first = certificate.contacts[1]
    assert first.patch.maximum_gap_m == 0.0
    patch = replace(first.patch, maximum_gap_m=False)
    changed = replace(
        certificate,
        contacts=(certificate.contacts[0], replace(first, patch=patch), *certificate.contacts[2:]),
    )
    with pytest.raises(ValueError):
        verify_pickup_certificate(source, plan, changed)
