"""Reject duplicate/type-aliased capacities and impossible observed quantities."""

from fractions import Fraction

from app.v3.storage_fullness_models import ModuleCapacity, SlotCapacity, SlotLoad


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("Storage fullness: " + reason)


def integer(value: int, minimum: int = 0) -> None:
    require(type(value) is int and value >= minimum, "invalid exact integer")


def quantity(value: Fraction, positive: bool = False) -> None:
    require(type(value) is Fraction, "invalid exact rational quantity")
    require(value > 0 if positive else value >= 0, "invalid quantity sign")


def identity(value: str) -> None:
    require(type(value) is str and bool(value.strip()), "invalid identity")


def capacities(slots: tuple[SlotCapacity, ...], modules: tuple[ModuleCapacity, ...]) -> None:
    require(type(slots) is tuple and type(modules) is tuple, "immutable capacities required")
    for module in modules:
        require(type(module) is ModuleCapacity, "invalid module capacity")
        identity(module.module_id)
        integer(module.hu_capacity, 1)
        quantity(module.payload_kg, True)
    for slot in slots:
        require(type(slot) is SlotCapacity, "invalid slot capacity")
        for key in (slot.slot_id, slot.module_id, slot.zone_id):
            identity(key)
        require(
            all(type(v) is bool for v in (slot.active, slot.reserve_only, slot.blocked)),
            "exact capacity flags required",
        )
        require(not slot.active or not (slot.reserve_only or slot.blocked), "active blocked slot")
        integer(slot.hu_capacity, 1)
        quantity(slot.payload_kg, True)
        quantity(slot.usable_volume_m3, True)
    require(len({s.slot_id for s in slots}) == len(slots), "duplicate slot")
    require(len({m.module_id for m in modules}) == len(modules), "duplicate module")
    require({s.module_id for s in slots} == {m.module_id for m in modules}, "module coverage")


def observations(
    slots: tuple[SlotCapacity, ...], loads: tuple[SlotLoad, ...], reserved: tuple[str, ...]
) -> None:
    require(type(loads) is tuple and type(reserved) is tuple, "immutable observations required")
    mapping = {slot.slot_id: slot for slot in slots}
    for load in loads:
        require(type(load) is SlotLoad, "invalid slot load")
        identity(load.slot_id)
        require(load.slot_id in mapping, "unknown observed slot")
        integer(load.containers)
        integer(load.units)
        quantity(load.gross_mass_kg)
        quantity(load.outer_volume_m3)
        slot = mapping[load.slot_id]
        require(load.containers <= slot.hu_capacity, "slot HU capacity exceeded")
        require(load.gross_mass_kg <= slot.payload_kg, "slot payload exceeded")
        require(load.outer_volume_m3 <= slot.usable_volume_m3, "slot volume exceeded")
        require(
            bool(load.containers) or not (load.units or load.gross_mass_kg or load.outer_volume_m3),
            "empty slot has cargo",
        )
        require(not load.containers or load.outer_volume_m3 > 0, "missing outer volume")
    require(len({load.slot_id for load in loads}) == len(loads), "duplicate slot observation")
    for slot_id in reserved:
        identity(slot_id)
        require(slot_id in mapping, "unknown reserved slot")
    require(len(set(reserved)) == len(reserved), "duplicate slot reservation")
