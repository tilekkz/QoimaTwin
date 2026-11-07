"""Independent C08 arithmetic and fail-closed local action prerequisites."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.vehicle_admission import check_handling_prerequisites, check_rating, request_digest
from app.v3.vehicle_evidence import ActionStep, Contact, HandlingEvidence, HandlingRequest
from app.v3.vehicle_handling import HandlingDesign, LoadDesign, RatingLimits, SupportSlot


def design() -> HandlingDesign:
    limits = RatingLimits(
        F(1000), F(800), F(500), F(".18"), F("1.5"), F(".4"), F(".4"), F(".08"), F(".07")
    )
    load = LoadDesign(
        "PALLET_LOAD",
        (F("1.2"), F("1.35"), F(1)),
        F(455),
        F(0),
        F(".6"),
        F(1),
        F(".7"),
        F(0),
        (F("-.4"), F(".4")),
        "nonlong_forklift",
        frozenset({"AB"}),
    )
    slot = SupportSlot(
        "slot",
        "B",
        (F("1.4"), F("1.5"), F("1.2")),
        F(".18"),
        F(".05"),
        F(1000),
        False,
        frozenset({"PALLET_LOAD"}),
    )
    return HandlingDesign(
        limits,
        (load,),
        (slot,),
        (("INBOUND_FORKLIFT_PAIR", "F01", "FL01"),),
        (("IN_W_BULK", "INBOUND_FORKLIFT_PAIR", frozenset({"PALLET_LOAD"})),),
    )


def request() -> HandlingRequest:
    return HandlingRequest(
        "HU1",
        "PALLET_LOAD",
        "INBOUND_FORKLIFT_PAIR",
        "IN_W_BULK",
        "slot",
        "pickup",
        (F("1.2"), F("1.35"), F(1)),
        F(455),
        F(".18"),
        (("cargo", "a" * 64), ("support", "b" * 64), ("vehicle", "c" * 64)),
    )


def evidence(value: HandlingRequest) -> HandlingEvidence:
    stages = (
        "stop_and_reserve_action_space",
        "extend_high",
        "lower_extended",
        "engage_or_release",
        "lift_extended_to_travel_height",
        "retract_high",
    )
    reach = (F(0), F(".4"), F(".4"), F(".4"), F(".4"), F(0))
    height = (F(".7"), F(".7"), F(".18"), F(".18"), F(".7"), F(".7"))
    held = ("actor:F01", "vehicle:FL01", "action:slot")
    steps = tuple(
        ActionStep(stage, i * 1_000_000, r, y, True, held)
        for i, (stage, r, y) in enumerate(zip(stages, reach, height, strict=True))
    )
    contacts = tuple(
        Contact(i, x, F(0), F(".18"), F(".08"), F(".07")) for i, x in enumerate((F("-.4"), F(".4")))
    )
    return HandlingEvidence(
        "declared-test",
        request_digest(value),
        (("source", "d" * 64),),
        value.model_hashes,
        "slot",
        F(".18"),
        contacts,
        steps,
        (("contact", "e" * 64), ("retention", "f" * 64), ("continuous_action", "1" * 64)),
        (),
        (),
    )


@pytest.mark.parametrize(
    ("mass", "arm", "height", "expected"),
    [
        (455, "1", "1.5", True),
        (654, "1", "1.5", True),
        (801, "1", "1.5", False),
        (1001, ".2", "1.5", False),
        (455, "1", "1.500001", False),
    ],
)
def test_source_rating_limits(mass: int, arm: str, height: str, expected: bool) -> None:
    assert (
        check_rating(design().limits, F(mass), F(arm), F(height), (F(mass, 2), F(mass, 2)))
        is expected
    )


def test_fork_shares_cannot_hide_overload_or_missing_mass() -> None:
    limits = design().limits
    assert not check_rating(limits, F(600), F(1), F(1), (F(501), F(99)))
    assert not check_rating(limits, F(600), F(1), F(1), (F(100), F(100)))


def test_source_symmetrical_rating_does_not_authorize_off_centre_load() -> None:
    assert not check_rating(design().limits, F(600), F(1), F(1), (F(400), F(200)))


def test_missing_actual_evidence_fails_closed() -> None:
    result = check_handling_prerequisites(design(), request(), (("source", "d" * 64),))
    assert result.design_passed
    assert not result.evidence_complete
    assert not result.operational_admission
    assert "missing_action_evidence" in result.reasons


def test_matching_numeric_evidence_still_does_not_grant_actual_operation() -> None:
    value = request()
    result = check_handling_prerequisites(design(), value, (("source", "d" * 64),), evidence(value))
    assert result.design_passed and result.evidence_complete
    assert not result.operational_admission
    assert result.requires_actual_mesh_verifier


@pytest.mark.parametrize(
    "mutation",
    [
        "hash",
        "support",
        "height",
        "channels",
        "contacts",
        "sequence",
        "reach",
        "moving",
        "resources",
        "time",
        "proof",
    ],
)
def test_matching_hash_alone_cannot_bypass_concrete_evidence(mutation: str) -> None:
    value = request()
    proof = evidence(value)
    if mutation == "hash":
        proof = replace(proof, model_hashes=(("vehicle", "0" * 64),))
    elif mutation == "support":
        proof = replace(proof, support_id="invented")
    elif mutation == "height":
        proof = replace(proof, support_y_m=F(".19"))
    elif mutation == "channels":
        proof = replace(
            proof,
            contacts=(replace(proof.contacts[0], channel_height_m=F(".06")), proof.contacts[1]),
        )
    elif mutation == "contacts":
        proof = replace(proof, contacts=(proof.contacts[0], proof.contacts[0]))
    elif mutation == "sequence":
        proof = replace(proof, steps=proof.steps[::-1])
    elif mutation in {"reach", "moving", "resources", "time"}:
        step = proof.steps[2]
        if mutation == "reach":
            step = replace(step, reach_m=F(0))
        elif mutation == "moving":
            step = replace(step, stopped=False)
        elif mutation == "resources":
            step = replace(step, held_resources=())
        else:
            step = replace(step, tick=-1)
        proof = replace(proof, steps=(*proof.steps[:2], step, *proof.steps[3:]))
    else:
        proof = replace(proof, proof_hashes=())
    result = check_handling_prerequisites(design(), value, (("source", "d" * 64),), proof)
    assert not result.evidence_complete
    assert not result.operational_admission


@pytest.mark.parametrize("mutation", ["pair", "port", "mass", "dimensions", "slot", "height"])
def test_concrete_request_is_checked_against_source_design(mutation: str) -> None:
    value = request()
    if mutation == "pair":
        value = replace(value, pair_id="OUTBOUND_FORKLIFT_PAIR")
    elif mutation == "port":
        value = replace(value, port_id="IN_E_PARCEL")
    elif mutation == "mass":
        value = replace(value, mass_kg=F(1200))
    elif mutation == "dimensions":
        value = replace(value, dimensions_m=(F(10), F(1), F(1)))
    elif mutation == "slot":
        value = replace(value, slot_id="unknown")
    else:
        value = replace(value, fork_top_y_m=F(".19"))
    result = check_handling_prerequisites(design(), value, (("source", "d" * 64),), evidence(value))
    assert not result.design_passed


def test_nonfinite_contact_cannot_satisfy_channel_requirement() -> None:
    value = request()
    proof = evidence(value)
    invalid = replace(proof.contacts[0], channel_height_m=float("nan"))  # type: ignore[arg-type]
    proof = replace(proof, contacts=(invalid, proof.contacts[1]))
    result = check_handling_prerequisites(design(), value, (("source", "d" * 64),), proof)
    assert not result.evidence_complete


def test_boolean_fork_index_cannot_identify_actual_fork() -> None:
    value = request()
    proof = evidence(value)
    proof = replace(
        proof, contacts=(replace(proof.contacts[0], fork_index=False), proof.contacts[1])
    )
    assert not check_handling_prerequisites(
        design(), value, (("source", "d" * 64),), proof
    ).evidence_complete
