"""Opt-in storage read model from an already validated settled native observation.

This reducer does not validate journal causality, certify a handler/route, mutate a
run or migrate its publication version. The native reader remains that authority.
"""

from app.v3.coordinator_metrics_inventory import inventory
from app.v3.coordinator_metrics_observed_values import unavailable
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.interface import Json
from app.v3.storage_fullness_observation import slot_loads, slot_reservations
from app.v3.storage_fullness_projection import project_storage
from app.v3.storage_fullness_source import source_capacities
from app.v3.storage_fullness_validation import integer


def coordinator_storage_fullness(
    profile: CoordinatorProfile, outcome: CoordinatorOutcome, point: CoordinatorSnapshot
) -> Json:
    integer(point.tick)
    capacities = source_capacities(profile)
    if capacities is None:
        return unavailable("Analytical profile has no authoritative source storage capacities")
    slots, modules = capacities
    slot_ids = frozenset(slot.slot_id for slot in slots)
    observed = inventory(profile, outcome, point)
    loads = slot_loads(point, observed["owners"], slot_ids)
    reserved = slot_reservations(point, slot_ids)
    return {
        "available": True,
        "tick": point.tick,
        "boundary": "settled_tick_inclusive",
        "scope": "source_storage_slots_only",
        "state_authority": "requires_validated_native_observation",
        **project_storage(slots, modules, loads, reserved),
    }
