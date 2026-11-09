"""Pure declared-state interlock. A satisfied prerequisite never authorizes physical motion."""

from fractions import Fraction

from app.v3.long_mechanism_models import (
    ATTACHMENT_ID,
    JointValue,
    LongMechanismInterface,
    LongMechanismState,
    MechanicalReadiness,
    Mode,
)
from app.v3.long_mechanism_source import verify_long_mechanism_interface
from app.v3.pallet_outbound_pickup_identity import identity, require


def _state_types(state: LongMechanismState) -> None:
    require(type(state) is LongMechanismState, "Exact mechanism state required")
    text = (
        state.attachment_id,
        state.actor_id,
        state.vehicle_id,
        state.custody_owner,
        state.upper_rig_location,
    )
    require(all(type(v) is str and v for v in text), "Exact nonempty state identities required")
    optional = state.hu_id, state.lot_id, state.declared_stow_id
    require(
        all(v is None or (type(v) is str and bool(v)) for v in optional),
        "Exact optional state identities required",
    )
    require(
        type(state.stopped) is bool and type(state.joints) is tuple,
        "Exact stopped flag and joint tuple required",
    )
    require(
        all(type(v) is Fraction for v in (state.relative_yaw_rad, state.reach_m, state.fork_top_m)),
        "Exact rational mechanism coordinates required",
    )
    require(
        state.upper_rig_location in {"mounted", "stowed", "unlocated"}, "Unknown upper rig location"
    )
    require(state.reach_m >= 0 and state.fork_top_m >= 0, "Negative mechanism pose")


def _binding(interface: LongMechanismInterface, state: LongMechanismState, mode: Mode) -> None:
    request = interface.requirements.request
    require(
        (state.attachment_id, state.actor_id, state.vehicle_id, state.custody_owner)
        == (ATTACHMENT_ID, request.actor_id, request.vehicle_id, "vehicle:" + request.vehicle_id),
        "Declared attachment/pair/custody reference differs",
    )
    original = next(
        h
        for h in interface.requirements.authority.initial_hus
        if h.handling_unit_id == request.hu_id
    )
    require(
        (state.hu_id, state.lot_id) == (original.handling_unit_id, original.lot_id)
        or (mode != "loaded_transit" and state.hu_id is None and state.lot_id is None),
        "Original LONG HU/lot reference differs",
    )
    require(
        state.declared_stow_id is None or state.upper_rig_location == "stowed",
        "Stow reference conflicts with rig location",
    )


def _joint_values(interface: LongMechanismInterface, state: LongMechanismState) -> None:
    require(len(state.joints) == 8, "Exact eight joint values required")
    for actual, source in zip(state.joints, interface.joints, strict=True):
        require(
            type(actual) is JointValue
            and type(actual.node_id) is str
            and type(actual.value) is Fraction,
            "Exact typed joint value required",
        )
        require(actual.node_id == source.node_id, "Joint IDs/order differ from source")
        require(source.minimum <= actual.value <= source.maximum, "Joint outside source range")


def _loaded(interface: LongMechanismInterface, state: LongMechanismState) -> tuple[str, ...]:
    reasons = []
    if any(j.value != 0 for j in state.joints):
        reasons.append("LONG_JOINT_NOT_CLOSED")
    if state.upper_rig_location != "mounted":
        reasons.append("UPPER_RIG_NOT_MOUNTED")
    if state.relative_yaw_rad != 0:
        reasons.append("LONG_RELATIVE_YAW_FORBIDDEN")
    if state.reach_m != 0 or state.fork_top_m != interface.travel_fork_top_m:
        reasons.append("LONG_TRAVEL_POSE_REQUIRED")
    return tuple(reasons)


def _empty(state: LongMechanismState) -> tuple[str, ...]:
    reasons = []
    if state.hu_id is not None:
        reasons.append("EMPTY_CRADLE_HAS_HU")
    if state.upper_rig_location != "stowed":
        reasons.append("UPPER_RIG_MUST_BE_STOWED")
    reasons.append("STOW_AUTHORITY_MISSING")
    return tuple(reasons)


def check_long_mechanism(
    interface: LongMechanismInterface, state: LongMechanismState, requested_mode: Mode
) -> MechanicalReadiness:
    verified = verify_long_mechanism_interface(interface)
    mode: object = requested_mode
    require(
        type(mode) is str
        and mode in {"loaded_transit", "empty_cradle_transit", "joint_adjustment"},
        "Unknown LONG mechanism mode",
    )
    _state_types(state)
    _binding(verified, state, requested_mode)
    _joint_values(verified, state)
    if requested_mode == "loaded_transit":
        reasons = _loaded(verified, state)
    elif requested_mode == "empty_cradle_transit":
        reasons = _empty(state)
    else:
        reasons = () if state.stopped else ("STOPPED_HANDLING_REQUIRED",)
    return MechanicalReadiness(
        requested_mode, not reasons, reasons, verified.input_hash, identity(state)
    )
