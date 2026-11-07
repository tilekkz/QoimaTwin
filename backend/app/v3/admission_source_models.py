"""Typed source restrictions and explicitly selected static handling capability."""

from dataclasses import dataclass
from decimal import Decimal

from app.v3.admission_models import Cargo, Handler, Slot


@dataclass(frozen=True)
class SelectedCapability:
    """Caller-declared capability, never evidence of availability or operational proof."""

    handler: Handler
    transport_tag: str
    equipment_tags: frozenset[str]


@dataclass(frozen=True)
class SourcePlacement:
    handling_unit_id: str
    slot_id: str


@dataclass(frozen=True)
class HandlingOption:
    handler_tag: str
    transport_tag: str
    equipment_tags: frozenset[str]
    archetypes: tuple[str, ...]
    manual_mass_limit_kg: Decimal | None

    def matches(self, selected: SelectedCapability, cargo: Cargo) -> bool:
        return (
            self.handler_tag == selected.handler.handler_id
            and self.transport_tag == selected.transport_tag
            and self.equipment_tags <= selected.equipment_tags
            and cargo.archetype_id in self.archetypes
            and cargo.gross_mass_kg is not None
            and (
                self.manual_mass_limit_kg is None
                or cargo.gross_mass_kg <= self.manual_mass_limit_kg
            )
        )


@dataclass(frozen=True)
class SourceCargo:
    cargo: Cargo
    storage_families: tuple[str, ...]
    modes: tuple[HandlingOption, ...]


@dataclass(frozen=True)
class SourceSlot:
    slot: Slot
    storage_family: str
    options: tuple[HandlingOption, ...]
    manual_pick_allowed: bool
    manual_mass_limit_kg: Decimal
    retrieval_blocked: bool
    retrieval_block_reason: str | None


def select_handler(
    cargo: SourceCargo, slot: SourceSlot, selected: SelectedCapability | None
) -> Handler | None:
    if selected is None:
        return None
    if not any(option.matches(selected, cargo.cargo) for option in slot.options):
        return None
    if not any(mode.matches(selected, cargo.cargo) for mode in cargo.modes):
        return None
    if selected.handler.handler_id == "manual_operator" and (
        not slot.manual_pick_allowed
        or cargo.cargo.gross_mass_kg is None
        or cargo.cargo.gross_mass_kg > slot.manual_mass_limit_kg
    ):
        return None
    return selected.handler
