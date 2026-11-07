"""Validate supplied runtime input files before publication or simulation."""

from pathlib import Path

import jsonschema

from app.contracts.assignment import Assignment
from app.contracts.base import checked_json_loads
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.errors import InvalidInputError


def validate_config_file(path: Path) -> None:
    """The typed model's JSON Schema is the backend schema until a shared one is agreed."""
    jsonschema.Draft202012Validator(SimulationConfig.model_json_schema()).validate(
        checked_json_loads(path.read_bytes())
    )


def load_assignment(path: Path, layout: Layout) -> Assignment:
    raw = path.read_bytes()
    jsonschema.Draft202012Validator(Assignment.model_json_schema()).validate(
        checked_json_loads(raw)
    )
    assignment = Assignment.from_json_text(raw)
    if assignment.layout_version != layout.layout_version:
        raise InvalidInputError("assignment layout_version does not match loaded layout")
    slots = {slot.slot_id: slot for slot in layout.slots}
    active = assignment.active_assignment
    if any(slot not in slots or slots[slot].kind != "pickface" for slot in active):
        raise InvalidInputError("active assignment references an unknown or non-pickface slot")
    if len(set(active.values())) != len(active):
        raise InvalidInputError("a SKU cannot have multiple active pickfaces")
    if any(lot.slot_id not in slots for lot in assignment.initial_lots):
        raise InvalidInputError("initial lot references an unknown slot")
    if len({lot.lot_id for lot in assignment.initial_lots}) != len(assignment.initial_lots):
        raise InvalidInputError("initial lot IDs must be unique")
    return assignment
