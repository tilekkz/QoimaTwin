"""Pure exact fullness reducer; empty does not imply cargo-specific operational availability."""

from fractions import Fraction

from app.v3.coordinator_metrics_observed_values import rational
from app.v3.interface import Json
from app.v3.storage_fullness_models import FULLNESS_VERSION, ModuleCapacity, SlotCapacity, SlotLoad
from app.v3.storage_fullness_rows import ratio, slot_row, summary
from app.v3.storage_fullness_validation import capacities, observations, require


def _modules(
    slots: tuple[SlotCapacity, ...],
    modules: tuple[ModuleCapacity, ...],
    loads: dict[str, SlotLoad],
    reserved: frozenset[str],
) -> list[Json]:
    result: list[Json] = []
    for module in sorted(modules, key=lambda item: item.module_id):
        members = tuple(slot for slot in slots if slot.module_id == module.module_id)
        row = summary(members, loads, reserved)
        mass = sum((loads[slot.slot_id].gross_mass_kg for slot in members), Fraction())
        require(row["containers"] <= module.hu_capacity, "module HU capacity exceeded")
        require(mass <= module.payload_kg, "module payload exceeded")
        result.append(
            {
                "module_id": module.module_id,
                **row,
                "module_hu_capacity": module.hu_capacity,
                "module_payload_kg": rational(module.payload_kg),
                "module_payload_fraction": ratio(mass, module.payload_kg),
            }
        )
    return result


def project_storage(
    slots: tuple[SlotCapacity, ...],
    modules: tuple[ModuleCapacity, ...],
    loads: tuple[SlotLoad, ...],
    reserved: tuple[str, ...],
) -> Json:
    capacities(slots, modules)
    observations(slots, loads, reserved)
    slots = tuple(sorted(slots, key=lambda item: item.slot_id))
    mapping = {slot.slot_id: SlotLoad(slot.slot_id, 0, 0, Fraction(), Fraction()) for slot in slots}
    mapping.update((load.slot_id, load) for load in loads)
    held = frozenset(reserved)
    return {
        "version": FULLNESS_VERSION,
        "operational_admission": False,
        "availability_meaning": "unreserved_active_empty_is_not_cargo_admission",
        "volume_meaning": "container_outer_volume_over_slot_usable_volume",
        "total": summary(slots, mapping, held),
        "zones": [
            {
                "zone_id": zone,
                **summary(tuple(s for s in slots if s.zone_id == zone), mapping, held),
            }
            for zone in sorted({slot.zone_id for slot in slots})
        ],
        "modules": _modules(slots, modules, mapping, held),
        "slots": [slot_row(slot, mapping[slot.slot_id], slot.slot_id in held) for slot in slots],
    }
