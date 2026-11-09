"""Declared LONG mechanical states, never inventory custody or physical execution grants."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.long_freight_models import LongFreightRequirements

VERSION = "qoima-long-mechanism-0.1.0"
ASSET_REVISION = "ceacd5180c273796ef34164b3d65e9082272650f"
ATTACHMENT_ID = "v3:attachment:long-cradle:01"
Mode = Literal["loaded_transit", "empty_cradle_transit", "joint_adjustment"]
XYZ = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class MechanismDocument:
    role: str
    path: str
    raw: bytes
    raw_sha256: str
    normalized_text_sha256: str | None


@dataclass(frozen=True, slots=True)
class JointDefinition:
    node_id: str
    component: str
    axis: str
    motion: str
    minimum: Fraction
    maximum: Fraction
    declared_pivot_m: XYZ
    decoded_translation_m: XYZ


@dataclass(frozen=True, slots=True)
class LongMechanismInterface:
    requirements: LongFreightRequirements
    documents: tuple[MechanismDocument, ...]
    joints: tuple[JointDefinition, ...]
    lower_contacts_m: tuple[XYZ, ...]
    upper_contacts_m: tuple[XYZ, ...]
    hu_mass_kg: Fraction
    attachment_mass_kg: Fraction
    total_lifted_kg: Fraction
    travel_fork_top_m: Fraction
    component_mass_split: None
    source_revision: str
    version: str
    input_hash: str


@dataclass(frozen=True, slots=True)
class JointValue:
    node_id: str
    value: Fraction


@dataclass(frozen=True, slots=True)
class LongMechanismState:
    hu_id: str | None
    lot_id: str | None
    attachment_id: str
    actor_id: str
    vehicle_id: str
    custody_owner: str
    upper_rig_location: Literal["mounted", "stowed", "unlocated"]
    declared_stow_id: str | None
    joints: tuple[JointValue, ...]
    relative_yaw_rad: Fraction
    reach_m: Fraction
    fork_top_m: Fraction
    stopped: bool


@dataclass(frozen=True, slots=True)
class MechanicalReadiness:
    requested_mode: Mode
    mechanically_ready: bool
    reasons: tuple[str, ...]
    interface_hash: str
    state_hash: str
    operational_admission: Literal[False] = False
    full_n3_acceptance: Literal[False] = False
    stock_custody_verified: Literal[False] = False
    physical_action_verified: Literal[False] = False
