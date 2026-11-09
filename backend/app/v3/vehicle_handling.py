"""Exact source C08 design limits; compatibility is not equipment availability."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from .runtime_graph_source import _array, _name, _names, _number, _object
from .vehicle_graph import vector3
from .vehicle_types import XYZ, XZ


@dataclass(frozen=True, slots=True)
class RatingLimits:
    nominal_kg: Fraction
    moment_kg_m: Fraction
    single_fork_kg: Fraction
    minimum_fork_y_m: Fraction
    maximum_fork_y_m: Fraction
    chassis_reference_z_m: Fraction
    reach_stroke_m: Fraction
    fork_width_m: Fraction
    fork_thickness_m: Fraction


@dataclass(frozen=True, slots=True)
class LoadDesign:
    cargo_id: str
    dimensions_m: XYZ
    hu_mass_kg: Fraction
    attachment_mass_kg: Fraction
    travel_arm_m: Fraction
    extended_arm_m: Fraction
    travel_fork_y_m: Fraction
    support_to_fork_offset_m: Fraction
    fork_centres_x_m: XZ
    local_profile: str
    allowed_arc_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class SupportSlot:
    slot_id: str
    vehicle_node_id: str | None
    usable_m: XYZ
    support_y_m: Fraction
    clearance_m: Fraction
    max_payload_kg: Fraction
    blocked: bool
    cargo_classes: frozenset[str]


@dataclass(frozen=True, slots=True)
class HandlingDesign:
    limits: RatingLimits
    loads: tuple[LoadDesign, ...]
    slots: tuple[SupportSlot, ...]
    pairs: tuple[tuple[str, str, str], ...]
    ports: tuple[tuple[str, str | None, frozenset[str]], ...]


def _limits(document: Mapping[str, object]) -> RatingLimits:
    rating = _object(document.get("rating_design"))
    reach = _object(document.get("stopped_reach_handling_design"))
    fork = _object(document.get("fork_design"))
    return RatingLimits(
        _number(rating.get("nominal_capacity_kg")),
        _number(rating.get("moment_budget_kg_m")),
        _number(rating.get("maximum_single_fork_share_kg")),
        _number(reach.get("minimum_fork_top_y_m")),
        _number(rating.get("maximum_fork_top_handling_y_m")),
        _number(rating.get("rating_reference_z_m")),
        _number(reach.get("extension_m")),
        _number(fork.get("width_each_m")),
        _number(fork.get("thickness_m")),
    )


def _load(value: object, limits: RatingLimits, allowed: Mapping[str, frozenset[str]]) -> LoadDesign:
    row = _object(value)
    cargo = _name(row.get("archetype_id"))
    centres = _array(row.get("fork_centres_x_m"))
    if len(centres) != 2 or _number(row.get("scale_factor")) != 1 or cargo not in allowed:
        raise ValueError("source load requires two forks, unit scale and explicit C08 arc set")
    cog = vector3(row.get("cog_local_xyz_m"))
    if cog[0] != 0:
        raise ValueError("C08 rating is restricted to symmetric lateral CoG")
    arm = cog[2] - limits.chassis_reference_z_m
    extended = _number(row.get("extended_handling_rating_arm_from_fixed_Z04_m"))
    if arm <= 0 or abs(extended - arm - limits.reach_stroke_m) > Fraction(1, 10**12):
        raise ValueError("extended moment must retain the fixed chassis reference")
    hu_mass = _number(row.get("HU_gross_mass_kg"))
    attachment = _number(row.get("attachment_mass_kg"), positive=False)
    if attachment < 0 or hu_mass + attachment != _number(row.get("total_lifted_mass_kg")):
        raise ValueError("C08 lifted mass must include attachment")
    fork_y = _number(row.get("fork_top_travel_y_m"))
    bottom = vector3(_object(row.get("cargo_bounds_local_m")).get("min"))[1]
    return LoadDesign(
        cargo,
        vector3(row.get("handling_unit_dimensions_xyz_m")),
        hu_mass,
        attachment,
        arm,
        extended,
        fork_y,
        bottom - fork_y,
        (_number(centres[0], positive=False), _number(centres[1], positive=False)),
        _name(row.get("local_geometry_profile_id")),
        allowed[cargo],
    )


def _slot(value: object) -> SupportSlot:
    row = _object(value)
    access = _object(row.get("access"))
    node = access.get("vehicle")
    blocked = row.get("reserve_only") is not False or row.get("retrieval_blocked") is not False
    return SupportSlot(
        _name(row.get("slot_id")),
        _name(node) if node is not None else None,
        vector3(row.get("usable_dimensions_xyz_m")),
        _number(row.get("service_height_m")),
        _number(row.get("clearance_each_side_m")),
        _number(row.get("max_payload_kg")),
        blocked,
        _names(row, "allowed_cargo_archetype_ids"),
    )


def decode_handling_design(
    handling: Mapping[str, object], slots: Mapping[str, object], policy: Mapping[str, object]
) -> HandlingDesign:
    limits = _limits(handling)
    allowed = {
        _name(row.get("archetype_id")): _names(row, "allowed_arc_ids")
        for value in _array(handling.get("per_cargo_arc_eligibility"))
        for row in [_object(value)]
    }
    pairs = tuple(
        (_name(row.get("pair_id")), _name(row.get("actor_id")), _name(row.get("vehicle_id")))
        for value in _array(policy.get("forklift_pairs"))
        for row in [_object(value)]
    )
    ports = tuple(
        (
            _name(row.get("port_id")),
            _name(row["equipment_pair_ref"]) if row.get("equipment_pair_ref") else None,
            _names(row, "forklift_cargo_archetype_ids"),
        )
        for value in _array(handling.get("ports"))
        for row in [_object(value)]
    )
    loads = tuple(_load(value, limits, allowed) for value in _array(handling.get("loads")))
    supports = tuple(_slot(value) for value in _array(slots.get("slots")))
    for identifiers in (
        [load.cargo_id for load in loads],
        [slot.slot_id for slot in supports],
        [pair[0] for pair in pairs],
        [port[0] for port in ports],
    ):
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate vehicle design identifier")
    return HandlingDesign(limits, loads, supports, pairs, ports)
