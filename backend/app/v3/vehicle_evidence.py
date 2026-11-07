"""Backend-proposed evidence envelope. Hashes identify claims, not physical proof."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from .vehicle_types import XYZ

Hashes = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class HandlingRequest:
    hu_id: str
    cargo_id: str
    pair_id: str
    port_id: str
    slot_id: str
    action: Literal["pickup", "place"]
    dimensions_m: XYZ
    mass_kg: Fraction
    fork_top_y_m: Fraction
    model_hashes: Hashes


@dataclass(frozen=True, slots=True)
class Contact:
    fork_index: int
    centre_x_m: Fraction
    centre_z_m: Fraction
    surface_y_m: Fraction
    channel_width_m: Fraction
    channel_height_m: Fraction


@dataclass(frozen=True, slots=True)
class ActionStep:
    stage: str
    tick: int
    reach_m: Fraction
    fork_top_y_m: Fraction
    stopped: bool
    held_resources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HandlingEvidence:
    evidence_id: str
    request_sha256: str
    source_hashes: Hashes
    model_hashes: Hashes
    support_id: str
    support_y_m: Fraction
    contacts: tuple[Contact, ...]
    steps: tuple[ActionStep, ...]
    proof_hashes: Hashes
    captive_pin_ids: tuple[str, ...]
    restraint_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HandlingVerdict:
    design_passed: bool
    evidence_complete: bool
    reasons: tuple[str, ...]

    @property
    def operational_admission(self) -> Literal[False]:
        return False

    @property
    def requires_actual_mesh_verifier(self) -> Literal[True]:
        return True
