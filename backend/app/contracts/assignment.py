"""Slot assignment and initial lots (contracts/assignment.example.json)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, PositiveInt

from app.contracts.base import FrozenModel, NonEmptyStr


class AssignmentProvenance(FrozenModel):
    kind: NonEmptyStr
    note: str = ""


class InitialLot(FrozenModel):
    lot_id: NonEmptyStr
    sku_id: NonEmptyStr
    slot_id: NonEmptyStr
    quantity: PositiveInt


class Assignment(FrozenModel):
    schema_version: Literal["2.0"]
    layout_version: NonEmptyStr
    assignment_id: NonEmptyStr
    provenance: AssignmentProvenance
    active_assignment: dict[str, str] = Field(description="pick-face slot id -> SKU id")
    initial_lots: tuple[InitialLot, ...]
    empty_pickfaces: tuple[str, ...] = ()
    empty_reserve_slots: tuple[str, ...] = ()

    def slot_of(self) -> dict[str, str]:
        """SKU id -> active pick-face slot id."""
        return {sku: slot for slot, sku in self.active_assignment.items()}
