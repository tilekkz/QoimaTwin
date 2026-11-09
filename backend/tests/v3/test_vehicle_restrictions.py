"""Source-shaped negative cases and bounded placement/attachment evidence."""

from dataclasses import replace
from fractions import Fraction as F
from types import MappingProxyType

from app.v3.vehicle_admission import check_handling_prerequisites, request_digest
from app.v3.vehicle_evidence import HandlingEvidence, HandlingRequest
from app.v3.vehicle_graph import decode_vehicle_graph
from app.v3.vehicle_handling import HandlingDesign
from app.v3.vehicle_source import VehicleAdapter
from tests.v3.test_vehicle_admission import design, evidence, request
from tests.v3.test_vehicle_fixtures import graph_documents


def test_candidate_intersection_never_creates_reverse_or_wrong_pair_permission() -> None:
    docs = graph_documents()
    graph = decode_vehicle_graph(docs["layout"], docs["traffic"], docs["vehicle"])
    adapter = VehicleAdapter("hand-fixture", (), graph, design(), MappingProxyType({}))
    assert adapter.declared_loaded_arc("AB", "PALLET_LOAD", "INBOUND_FORKLIFT_PAIR")
    assert not adapter.declared_loaded_arc("BA", "PALLET_LOAD", "INBOUND_FORKLIFT_PAIR")
    assert not adapter.declared_loaded_arc("AB", "PALLET_LOAD", "OUTBOUND_FORKLIFT_PAIR")
    assert not adapter.declared_loaded_arc("AB", "LONG_BUNDLE", "INBOUND_FORKLIFT_PAIR")
    assert not adapter.operational_admission


def test_bare_profile_does_not_become_loaded_even_if_cargo_fits() -> None:
    docs = graph_documents()
    docs["layout"]["vehicle_graph"]["arcs"][0]["allowed_geometry_profile_ids"] = ["unloaded_bare"]
    graph = decode_vehicle_graph(docs["layout"], docs["traffic"], docs["vehicle"])
    adapter = VehicleAdapter("hand-fixture", (), graph, design(), MappingProxyType({}))
    assert not adapter.declared_loaded_arc("AB", "PALLET_LOAD", "INBOUND_FORKLIFT_PAIR")


def test_place_requires_explicit_extended_withdrawal_before_empty_lift() -> None:
    value = replace(request(), action="place")
    proof = evidence(value)
    assert not check_handling_prerequisites(
        design(), value, (("source", "d" * 64),), proof
    ).evidence_complete
    withdraw = replace(proof.steps[3], stage="withdraw_extended", tick=4_000_000, stopped=False)
    steps = (
        *proof.steps[:4],
        withdraw,
        replace(proof.steps[4], tick=5_000_000),
        replace(proof.steps[5], tick=6_000_000),
    )
    proof = replace(proof, steps=steps)
    verdict = check_handling_prerequisites(design(), value, (("source", "d" * 64),), proof)
    assert verdict.evidence_complete and not verdict.operational_admission


def test_source_reserve_slot_cannot_pass_geometric_evidence() -> None:
    source = design()
    source = replace(source, slots=(replace(source.slots[0], blocked=True),))
    value = request()
    assert not check_handling_prerequisites(
        source, value, (("source", "d" * 64),), evidence(value)
    ).design_passed


def test_reduced_slot_payload_or_envelope_cannot_pass_bound_evidence() -> None:
    source = design()
    value = request()
    for slot in (
        replace(source.slots[0], max_payload_kg=F(454)),
        replace(source.slots[0], usable_m=(F(1), F(1), F(1))),
    ):
        assert not check_handling_prerequisites(
            replace(source, slots=(slot,)), value, (("source", "d" * 64),), evidence(value)
        ).design_passed


def test_evidence_identity_changes_with_hu_or_direction_and_is_exact() -> None:
    value = request()
    assert request_digest(value) == request_digest(replace(value))
    assert request_digest(value) != request_digest(replace(value, hu_id="HU2"))
    assert request_digest(value) != request_digest(replace(value, action="place"))
    proof = evidence(value)
    assert not check_handling_prerequisites(
        design(), replace(value, hu_id="HU2"), (("source", "d" * 64),), proof
    ).evidence_complete


def _long_design() -> HandlingDesign:
    source = design()
    dims = (F("4.2"), F(".52"), F(".65"))
    load = replace(
        source.loads[0],
        cargo_id="LONG_BUNDLE",
        dimensions_m=dims,
        hu_mass_kg=F(200),
        attachment_mass_kg=F(40),
        travel_fork_y_m=F(".75"),
        support_to_fork_offset_m=F(".05"),
        local_profile="long_loaded",
    )
    slot = replace(
        source.slots[0],
        usable_m=(F("4.4"), F(".65"), F(".9")),
        support_y_m=F(".25"),
        max_payload_kg=F(600),
        cargo_classes=frozenset({"LONG_BUNDLE"}),
    )
    return replace(
        source,
        loads=(load,),
        slots=(slot,),
        ports=(("IN_W_BULK", "INBOUND_FORKLIFT_PAIR", frozenset({"LONG_BUNDLE"})),),
    )


def _long_case() -> tuple[HandlingDesign, HandlingRequest, HandlingEvidence]:
    source = _long_design()
    value = replace(
        request(),
        cargo_id="LONG_BUNDLE",
        dimensions_m=source.loads[0].dimensions_m,
        mass_kg=F(200),
        fork_top_y_m=F(".20"),
        model_hashes=(*request().model_hashes, ("attachment", "2" * 64)),
    )
    proof = evidence(value)
    contacts = tuple(replace(c, surface_y_m=F(".25")) for c in proof.contacts)
    steps = tuple(
        replace(s, fork_top_y_m=F(".20") if s.fork_top_y_m == F(".18") else F(".75"))
        for s in proof.steps
    )
    return (
        source,
        value,
        replace(
            proof,
            support_y_m=F(".25"),
            contacts=contacts,
            steps=steps,
            captive_pin_ids=("pin-left", "pin-right"),
            restraint_ids=("strap-left", "strap-right"),
        ),
    )


def test_long_attachment_requires_matching_lock_proof_not_only_pin_names() -> None:
    source, value, proof = _long_case()
    assert value.mass_kg + source.loads[0].attachment_mass_kg == F(240)
    verdict = check_handling_prerequisites(source, value, (("source", "d" * 64),), proof)
    assert verdict.design_passed and not verdict.evidence_complete
    proof = replace(proof, proof_hashes=(*proof.proof_hashes, ("lock", "3" * 64)))
    verdict = check_handling_prerequisites(source, value, (("source", "d" * 64),), proof)
    assert verdict.evidence_complete and not verdict.operational_admission
