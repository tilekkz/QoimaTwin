"""C08 design and evidence prerequisites. Every verdict remains non-operational."""

import hashlib
import re
from fractions import Fraction

from app.storage.canonical_json import canonical_bytes

from .vehicle_action import numeric_evidence_matches
from .vehicle_evidence import HandlingEvidence, HandlingRequest, HandlingVerdict, Hashes
from .vehicle_handling import HandlingDesign, LoadDesign, RatingLimits, SupportSlot


def check_rating(
    limits: RatingLimits,
    lifted_kg: Fraction,
    arm_m: Fraction,
    fork_top_y_m: Fraction,
    fork_shares_kg: tuple[Fraction, Fraction],
) -> bool:
    values = (lifted_kg, arm_m, fork_top_y_m, *fork_shares_kg)
    if any(not isinstance(value, Fraction) or value <= 0 for value in values):
        return False
    return (
        limits.minimum_fork_y_m <= fork_top_y_m <= limits.maximum_fork_y_m
        and lifted_kg <= limits.nominal_kg
        and lifted_kg * arm_m <= limits.moment_kg_m
        and sum(fork_shares_kg) == lifted_kg
        and fork_shares_kg[0] == fork_shares_kg[1]
        and all(share <= limits.single_fork_kg for share in fork_shares_kg)
    )


def request_digest(value: HandlingRequest) -> str:
    fields = {
        "hu_id": value.hu_id,
        "cargo_id": value.cargo_id,
        "pair_id": value.pair_id,
        "port_id": value.port_id,
        "slot_id": value.slot_id,
        "action": value.action,
        "dimensions_m": [str(v) for v in value.dimensions_m],
        "mass_kg": str(value.mass_kg),
        "fork_top_y_m": str(value.fork_top_y_m),
        "model_hashes": [[name, digest] for name, digest in value.model_hashes],
    }
    return hashlib.sha256(canonical_bytes(fields)).hexdigest()


def _valid_hashes(values: Hashes, required: set[str]) -> bool:
    names = [name for name, _ in values]
    return (
        len(names) == len(set(names))
        and required <= set(names)
        and all(name and re.fullmatch(r"[0-9a-f]{64}", digest) for name, digest in values)
    )


def _design_matches(
    design: HandlingDesign, load: LoadDesign, slot: SupportSlot, value: HandlingRequest
) -> bool:
    measurements = (*value.dimensions_m, value.mass_kg, value.fork_top_y_m)
    if len(value.dimensions_m) != 3 or any(type(v) is not Fraction or v <= 0 for v in measurements):
        return False
    if value.action not in {"pickup", "place"} or not value.hu_id or slot.blocked:
        return False
    if slot.vehicle_node_id is None or value.cargo_id not in slot.cargo_classes:
        return False
    if value.dimensions_m != load.dimensions_m or value.mass_kg != load.hu_mass_kg:
        return False
    if not all(
        size + 2 * slot.clearance_m <= room
        for size, room in zip(value.dimensions_m, slot.usable_m, strict=True)
    ):
        return False
    if value.mass_kg > slot.max_payload_kg:
        return False
    if value.fork_top_y_m != slot.support_y_m - load.support_to_fork_offset_m:
        return False
    if not any(pair[0] == value.pair_id for pair in design.pairs):
        return False
    if not any(
        p[0] == value.port_id and p[1] == value.pair_id and value.cargo_id in p[2]
        for p in design.ports
    ):
        return False
    mass = value.mass_kg + load.attachment_mass_kg
    return all(
        check_rating(design.limits, mass, arm, value.fork_top_y_m, (mass / 2, mass / 2))
        for arm in (load.travel_arm_m, load.extended_arm_m)
    )


def _bound_evidence(
    value: HandlingRequest, sources: Hashes, evidence: HandlingEvidence, attachment: bool
) -> bool:
    roles = {"cargo", "support", "vehicle"} | ({"attachment"} if attachment else set())
    proofs = {"contact", "retention", "continuous_action"} | ({"lock"} if attachment else set())
    return (
        bool(evidence.evidence_id)
        and _valid_hashes(sources, set())
        and bool(sources)
        and _valid_hashes(value.model_hashes, roles)
        and _valid_hashes(evidence.proof_hashes, proofs)
        and evidence.source_hashes == sources
        and evidence.model_hashes == value.model_hashes
        and evidence.request_sha256 == request_digest(value)
    )


def check_handling_prerequisites(
    design: HandlingDesign,
    value: HandlingRequest,
    source_hashes: Hashes,
    evidence: HandlingEvidence | None = None,
) -> HandlingVerdict:
    """Validate declared source-specific prerequisites, never authorize an operation.

    Exact C08 class dimensions/mass are supported initially. Alternative loads,
    dynamic occupancy, buffers, reservations and actual mesh proof are not inferred.
    """
    load = next((load for load in design.loads if load.cargo_id == value.cargo_id), None)
    slot = next((slot for slot in design.slots if slot.slot_id == value.slot_id), None)
    if load is None or slot is None or not _design_matches(design, load, slot, value):
        return HandlingVerdict(False, False, ("source_design_mismatch",))
    if evidence is None:
        return HandlingVerdict(True, False, ("missing_action_evidence",))
    if not _bound_evidence(value, source_hashes, evidence, bool(load.attachment_mass_kg)):
        return HandlingVerdict(True, False, ("evidence_binding_mismatch",))
    if not numeric_evidence_matches(design, load, slot, value, evidence):
        return HandlingVerdict(True, False, ("numeric_action_evidence_mismatch",))
    return HandlingVerdict(True, True, ())
