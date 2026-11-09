"""Read-model quantities retain explicit slot, module, mass and outer-volume denominators."""

from fractions import Fraction

from app.v3.coordinator_metrics_observed_values import rational
from app.v3.interface import Json
from app.v3.storage_fullness_models import SlotCapacity, SlotLoad


def ratio(numerator: int | Fraction, denominator: int | Fraction) -> Json | None:
    return rational(Fraction(numerator) / denominator) if denominator else None


def slot_row(slot: SlotCapacity, load: SlotLoad, reserved: bool) -> Json:
    occupied = bool(load.containers)
    return {
        "slot_id": slot.slot_id,
        "module_id": slot.module_id,
        "zone_id": slot.zone_id,
        "active": slot.active,
        "reserve_only": slot.reserve_only,
        "blocked": slot.blocked,
        "reserved": reserved,
        "occupied": occupied,
        "containers": load.containers,
        "units": load.units,
        "hu_capacity": slot.hu_capacity,
        "gross_mass_kg": rational(load.gross_mass_kg),
        "payload_kg": rational(slot.payload_kg),
        "outer_volume_m3": rational(load.outer_volume_m3),
        "usable_volume_m3": rational(slot.usable_volume_m3),
        "payload_fraction": ratio(load.gross_mass_kg, slot.payload_kg),
        "volume_fraction": ratio(load.outer_volume_m3, slot.usable_volume_m3),
    }


def summary(
    slots: tuple[SlotCapacity, ...], loads: dict[str, SlotLoad], reserved: frozenset[str]
) -> Json:
    values = tuple(loads[slot.slot_id] for slot in slots)
    occupied = sum(bool(load.containers) for load in values)
    active = tuple(slot for slot in slots if slot.active)
    active_occupied = sum(bool(loads[slot.slot_id].containers) for slot in active)
    mass = sum((load.gross_mass_kg for load in values), Fraction())
    volume = sum((load.outer_volume_m3 for load in values), Fraction())
    payload = sum((slot.payload_kg for slot in slots), Fraction())
    usable = sum((slot.usable_volume_m3 for slot in slots), Fraction())
    return {
        "physical_slots": len(slots),
        "occupied_slots": occupied,
        "empty_slots": len(slots) - occupied,
        "active_slots": len(active),
        "active_occupied_slots": active_occupied,
        "active_empty_slots": len(active) - active_occupied,
        "reserved_slots": sum(slot.slot_id in reserved for slot in slots),
        "reserve_only_slots": sum(slot.reserve_only for slot in slots),
        "blocked_slots": sum(slot.blocked for slot in slots),
        "unreserved_active_empty_slots": sum(
            not loads[slot.slot_id].containers and slot.slot_id not in reserved for slot in active
        ),
        "containers": sum(load.containers for load in values),
        "units": sum(load.units for load in values),
        "hu_capacity": sum(slot.hu_capacity for slot in slots),
        "gross_mass_kg": rational(mass),
        "slot_payload_kg": rational(payload),
        "outer_volume_m3": rational(volume),
        "usable_volume_m3": rational(usable),
        "occupied_fraction": ratio(occupied, len(slots)),
        "active_occupied_fraction": ratio(active_occupied, len(active)),
        "slot_payload_fraction": ratio(mass, payload),
        "volume_fraction": ratio(volume, usable),
    }
