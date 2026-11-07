"""Check numeric declared evidence; do not pretend to verify actual mesh triangles."""

from fractions import Fraction

from .vehicle_evidence import HandlingEvidence, HandlingRequest
from .vehicle_handling import HandlingDesign, LoadDesign, SupportSlot

PICKUP_STAGES = (
    "stop_and_reserve_action_space",
    "extend_high",
    "lower_extended",
    "engage_or_release",
    "lift_extended_to_travel_height",
    "retract_high",
)
PLACE_STAGES = (
    "stop_and_reserve_action_space",
    "extend_high",
    "lower_extended",
    "engage_or_release",
    "withdraw_extended",
    "lift_extended_to_travel_height",
    "retract_high",
)


def _contacts(
    design: HandlingDesign, load: LoadDesign, slot: SupportSlot, evidence: HandlingEvidence
) -> bool:
    if evidence.support_id != slot.slot_id or evidence.support_y_m != slot.support_y_m:
        return False
    contacts = evidence.contacts
    if len(contacts) != 2 or {c.fork_index for c in contacts} != {0, 1}:
        return False
    for contact in contacts:
        numbers = (
            contact.centre_x_m,
            contact.centre_z_m,
            contact.surface_y_m,
            contact.channel_width_m,
            contact.channel_height_m,
        )
        if type(contact.fork_index) is not int or any(type(n) is not Fraction for n in numbers):
            return False
        if contact.centre_x_m != load.fork_centres_x_m[contact.fork_index]:
            return False
        if contact.surface_y_m != slot.support_y_m:
            return False
        if abs(contact.centre_z_m) >= load.dimensions_m[2] / 2:
            return False
        if abs(contact.centre_x_m) + design.limits.fork_width_m / 2 > load.dimensions_m[0] / 2:
            return False
        if contact.channel_width_m < design.limits.fork_width_m:
            return False
        if contact.channel_height_m < design.limits.fork_thickness_m:
            return False
    return True


def _stage_pose(
    stage: str, load: LoadDesign, value: HandlingRequest, reach: Fraction
) -> tuple[Fraction, Fraction]:
    extension = Fraction(0) if stage in {PICKUP_STAGES[0], PICKUP_STAGES[-1]} else reach
    low = {"lower_extended", "engage_or_release", "withdraw_extended"}
    height = value.fork_top_y_m if stage in low else load.travel_fork_y_m
    return extension, height


def _steps(
    design: HandlingDesign, load: LoadDesign, value: HandlingRequest, evidence: HandlingEvidence
) -> bool:
    stages = PICKUP_STAGES if value.action == "pickup" else PLACE_STAGES
    if tuple(step.stage for step in evidence.steps) != stages:
        return False
    pair = next(p for p in design.pairs if p[0] == value.pair_id)
    required = {f"actor:{pair[1]}", f"vehicle:{pair[2]}", f"action:{value.slot_id}"}
    previous = -1
    for step in evidence.steps:
        if type(step.reach_m) is not Fraction or type(step.fork_top_y_m) is not Fraction:
            return False
        if type(step.tick) is not int or step.tick < 0 or step.tick <= previous:
            return False
        previous = step.tick
        stopped = step.stage != "withdraw_extended"
        if step.stopped is not stopped or not required <= set(step.held_resources):
            return False
        reach, height = _stage_pose(step.stage, load, value, design.limits.reach_stroke_m)
        if step.reach_m != reach or step.fork_top_y_m != height:
            return False
    return True


def numeric_evidence_matches(
    design: HandlingDesign,
    load: LoadDesign,
    slot: SupportSlot,
    value: HandlingRequest,
    evidence: HandlingEvidence,
) -> bool:
    if not _contacts(design, load, slot, evidence) or not _steps(design, load, value, evidence):
        return False
    if load.attachment_mass_kg:
        if len(set(evidence.captive_pin_ids)) != 2 or len(set(evidence.restraint_ids)) < 2:
            return False
        if set(evidence.captive_pin_ids) & set(evidence.restraint_ids):
            return False
        if not all(
            isinstance(name, str) and name.strip()
            for name in evidence.captive_pin_ids + evidence.restraint_ids
        ):
            return False
    return True
