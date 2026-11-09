"""Exact storage observation values, separate from cargo admission and scheduling."""

from dataclasses import dataclass
from fractions import Fraction

FULLNESS_VERSION = "qoima-storage-fullness-observation-0.1.0"


@dataclass(frozen=True, slots=True)
class SlotCapacity:
    slot_id: str
    module_id: str
    zone_id: str
    active: bool
    reserve_only: bool
    blocked: bool
    hu_capacity: int
    payload_kg: Fraction
    usable_volume_m3: Fraction


@dataclass(frozen=True, slots=True)
class ModuleCapacity:
    module_id: str
    hu_capacity: int
    payload_kg: Fraction


@dataclass(frozen=True, slots=True)
class SlotLoad:
    slot_id: str
    containers: int
    units: int
    gross_mass_kg: Fraction
    outer_volume_m3: Fraction
