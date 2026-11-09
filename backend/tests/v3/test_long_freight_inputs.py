"""Independent source identity and exact LONG arithmetic, without any engine."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.long_freight_binding import compile_long_freight_requirements
from app.v3.long_freight_models import LongFreightRequest, LongFreightRequirements
from app.v3.workload_models import WorkloadPolicy


def request() -> LongFreightRequest:
    return LongFreightRequest(
        "v3:HU:initial:DEMO_180:01",
        "v3:slot:LONG_W:002:L1:B1",
        "v3:slot:LONG_W:001:L1:B1",
        "upright_xyz",
        "OUT_E_B2B",
        "OUTBOUND_FORKLIFT_PAIR",
        "F02",
        "FL02",
    )


def policy() -> WorkloadPolicy:
    return WorkloadPolicy(60000000, 40, 60, "normal")


@pytest.fixture(scope="module")
def bound() -> LongFreightRequirements:
    return compile_long_freight_requirements(request(), policy())


def test_source_long_fit_keeps_200kg_cargo_and_40kg_cradle_separate(
    bound: LongFreightRequirements,
) -> None:
    assert bound.static.reasons == ()
    assert bound.static.status == "prerequisites_only"
    assert bound.static.required_dimensions_m == (F("4.3"), F(".62"), F(".75"))
    assert bound.static.target_dimensions_m == (F("4.4"), F(".65"), F(".9"))
    assert bound.static.hu_mass_kg == F(200)
    assert bound.static.attachment_mass_kg == F(40)
    assert bound.static.total_lifted_kg == F(240)
    assert bound.static.pickup_design_passed and bound.static.place_design_passed
    assert bound.static.port_clear_width_m == F(6)
    assert bound.static.port_clear_height_m == F("4.5")
    assert bound.static.port_service_seconds == F(210)
    assert bound.operational_admission is False and bound.full_n3_acceptance is False


def test_all_original_stock_and_offers_remain_authority(bound: LongFreightRequirements) -> None:
    assert len(bound.authority.initial_hus) == 530
    assert sum(hu.quantity_units for hu in bound.authority.initial_hus) == 12256
    hu = next(hu for hu in bound.authority.initial_hus if hu.handling_unit_id == request().hu_id)
    assert hu.slot_id == request().source_slot_id and hu.orientation_id == "upright_xyz"
    assert hu.lot_id == "v3:lot:initial:DEMO_180" and hu.quantity_units == 24
    jobs = bound.authority.workload.jobs
    assert len(jobs) == 100
    assert sum(job.direction == "inbound" for job in jobs) == 40
    assert sum(job.direction == "outbound" for job in jobs) == 60
    assert "OUT_E_B2B" in {job.port_id for job in jobs}
    assert all(0 <= job.arrival_tick < 60000000 for job in jobs)


def test_static_pass_does_not_erase_any_actual_proof_obligation(
    bound: LongFreightRequirements,
) -> None:
    assert {item.code for item in bound.blockers} == {
        "ACTUAL_PICKUP_CONTACT_REQUIRED",
        "CRADLE_LOCK_RETENTION_REQUIRED",
        "ACTUAL_SETDOWN_CONTACT_REQUIRED",
        "LOADED_ROUTE_GATE_SWEEP_REQUIRED",
        "JOINT_ACTOR_VEHICLE_TRAFFIC_REQUIRED",
        "EXPLICIT_OPERATION_CLOCKS_REQUIRED",
        "CUSTOMER_HANDOFF_AND_STAGING_REQUIRED",
    }
    assert all(item.required_fields for item in bound.blockers)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("target_slot_id", "v3:slot:SMALL_W:001:L1:B1", "TYPE_MISMATCH"),
        ("target_slot_id", "v3:slot:FLEX_W:001:L1:B1", "TYPE_MISMATCH"),
        ("target_slot_id", "v3:slot:LONG_W:003:L1:B1", "TARGET_OCCUPIED"),
        ("orientation_id", "upright_zyx", "ORIENTATION_FORBIDDEN"),
        ("port_id", "OUT_S_EXPRESS", "PORT_CARGO_FORBIDDEN"),
        ("actor_id", "F01", "FIXED_OUTBOUND_PAIR_REQUIRED"),
        ("vehicle_id", "FL01", "FIXED_OUTBOUND_PAIR_REQUIRED"),
    ],
)
def test_invalid_physical_choices_are_explained(field: str, value: str, reason: str) -> None:
    result = compile_long_freight_requirements(replace(request(), **{field: value}), policy())
    assert result.static.status == "static_rejected"
    assert reason in result.static.reasons
    assert result.operational_admission is False


@pytest.mark.parametrize("field,value", [("hu_id", "invented"), ("source_slot_id", "invented")])
def test_false_original_identity_fails_closed(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="ORIGINAL"):
        compile_long_freight_requirements(replace(request(), **{field: value}), policy())


def test_other_free_long_target_does_not_expand_the_bounded_slice() -> None:
    value = replace(request(), target_slot_id="v3:slot:LONG_E:001:L1:B1")
    result = compile_long_freight_requirements(value, policy())
    assert "TARGET_OUT_OF_SCOPE" in result.static.reasons
    assert result.static.status == "static_rejected"
