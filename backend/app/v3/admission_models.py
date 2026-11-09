"""Frozen input values for static V3 compatibility; no resource availability claims."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Dimensions = tuple[Decimal, Decimal, Decimal]
Reason = Literal[
    "RESERVE_ACCESS_BLOCKED",
    "TYPE_MISMATCH",
    "ORIENTATION_FORBIDDEN",
    "DIMENSION_MISMATCH",
    "UNKNOWN_MASS",
    "OVERWEIGHT",
    "SLOT_CAPACITY",
    "MODULE_OVERWEIGHT",
    "HANDLER_UNAVAILABLE",
    "HEIGHT_ACCESS_UNAVAILABLE",
    "PATH_CLEARANCE",
]


@dataclass(frozen=True)
class Cargo:
    archetype_id: str
    dimensions: Dimensions
    gross_mass_kg: Decimal | None
    orientations: tuple[str, ...]


@dataclass(frozen=True)
class Slot:
    slot_id: str
    module_id: str
    dimensions: Dimensions
    max_payload_kg: Decimal
    max_handling_units: int
    module_max_payload_kg: Decimal
    allowed_archetypes: tuple[str, ...]
    orientations: tuple[str, ...]
    clearance_m: Decimal
    support_y_m: Decimal
    service_height_m: Decimal
    reserve_only: bool = False
    required_handler_ids: tuple[str, ...] = ("manual",)


@dataclass(frozen=True)
class Handler:
    handler_id: str
    archetypes: tuple[str, ...]
    max_payload_kg: Decimal
    max_service_height_m: Decimal


@dataclass(frozen=True)
class StorageState:
    slot_hus: int = 0
    slot_mass_kg: Decimal = Decimal(0)
    module_mass_kg: Decimal = Decimal(0)


@dataclass(frozen=True)
class RouteProof:
    """Trusted route evaluator's static result bound to exact candidate inputs."""

    layout_hash: str
    cargo: Cargo
    slot_id: str
    handler: Handler
    reachable: bool


@dataclass(frozen=True)
class Admission:
    reasons: tuple[Reason, ...]
    bottom_y_m: Decimal | None = None
    top_y_m: Decimal | None = None
    headroom_m: Decimal | None = None
    operational_admission: Literal[False] = False
    cost_evaluated: Literal[False] = False

    @property
    def eligible(self) -> bool:
        return not self.reasons
