"""Independent source/evidence boundary probes; no physical certification claim."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.vehicle_admission import check_handling_prerequisites, check_rating
from app.v3.vehicle_graph import decode_vehicle_graph
from app.v3.vehicle_handling import decode_handling_design
from tests.v3.test_vehicle_admission import design, evidence, request
from tests.v3.test_vehicle_fixtures import graph_documents, source_documents
from tests.v3.test_vehicle_restrictions import _long_case


def test_boolean_dimension_is_not_a_declared_exact_hu_measurement() -> None:
    value = replace(request(), dimensions_m=(F("1.2"), F("1.35"), cast(F, True)))
    result = check_handling_prerequisites(design(), value, (("source", "d" * 64),), evidence(value))
    assert not result.design_passed


def test_long_pins_cannot_also_name_independent_restraints() -> None:
    source, value, proof = _long_case()
    proof = replace(
        proof,
        restraint_ids=proof.captive_pin_ids,
        proof_hashes=(*proof.proof_hashes, ("lock", "3" * 64)),
    )
    result = check_handling_prerequisites(source, value, (("source", "d" * 64),), proof)
    assert result.design_passed
    assert not result.evidence_complete
    assert not result.operational_admission


def test_traffic_binding_must_resolve_the_arcs_actual_source_reference() -> None:
    documents = graph_documents()
    documents["layout"]["traffic_route_bindings"][0]["route_ref"] = "another-source-path"
    documents["traffic"]["mixed_traffic"]["resources"][0]["vehicle_route_refs"] = [
        "another-source-path"
    ]
    with pytest.raises(ValueError):
        decode_vehicle_graph(documents["layout"], documents["traffic"], documents["vehicle"])


def test_boolean_source_scale_is_not_numeric_unit_scale() -> None:
    documents = source_documents()
    documents["vehicle-handling-v3.json"]["loads"][0]["scale_factor"] = True
    with pytest.raises(ValueError):
        decode_handling_design(
            documents["vehicle-handling-v3.json"],
            documents["storage-slots-v3.json"],
            documents["port-resource-policy-v3.json"],
        )


@pytest.mark.parametrize("invalid", [True, float("nan"), float("inf"), -float("inf")])
def test_rating_rejects_non_exact_or_nonfinite_mass(invalid: float) -> None:
    result = check_rating(
        design().limits,
        cast(F, invalid),
        F(1),
        F(1),
        (F(400), F(400)),
    )
    assert not result


def test_manual_rating_oracles_preserve_fixed_chassis_and_fork_limits() -> None:
    limits = design().limits
    assert F(455) * F(".6") == 273
    assert F(455) * F(1) == 455
    assert F(455) / 2 == F("227.5")
    assert check_rating(limits, F(800), F(1), F("1.5"), (F(400), F(400)))
    overload = F(800) + F(1, 1000)
    assert not check_rating(limits, overload, F(1), F("1.5"), (overload / 2, overload / 2))
    assert not check_rating(limits, F(600), F(1), F(1), (F(501), F(99)))


@pytest.mark.parametrize("case", ["support", "channel", "reach", "sequence", "tick", "source"])
def test_exact_contact_reach_and_evidence_boundaries_reject_inconsistency(case: str) -> None:
    value = request()
    proof = evidence(value)
    epsilon = F(1, 10**9)
    if case in {"support", "channel"}:
        contact = (
            replace(proof.contacts[0], surface_y_m=F(".18") + epsilon)
            if case == "support"
            else replace(proof.contacts[0], channel_width_m=F(".08") - epsilon)
        )
        proof = replace(proof, contacts=(contact, proof.contacts[1]))
    elif case == "reach":
        steps = (*proof.steps[:2], replace(proof.steps[2], reach_m=F(0)), *proof.steps[3:])
        proof = replace(proof, steps=steps)
    elif case == "sequence":
        proof = replace(
            proof, steps=(*proof.steps[:2], proof.steps[3], proof.steps[2], *proof.steps[4:])
        )
    elif case == "tick":
        proof = replace(
            proof, steps=(proof.steps[0], replace(proof.steps[1], tick=True), *proof.steps[2:])
        )
    else:
        proof = replace(proof, source_hashes=(("source", "f" * 64),))
    result = check_handling_prerequisites(design(), value, (("source", "d" * 64),), proof)
    assert result.design_passed
    assert not result.evidence_complete
    assert not result.operational_admission
