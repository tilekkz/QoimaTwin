"""Read current container geometry and held place leases without forecasting availability."""

from fractions import Fraction

from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.interface import Json
from app.v3.stock_validation import vector
from app.v3.storage_fullness_models import SlotLoad
from app.v3.storage_fullness_validation import identity, require

PLACE_PREFIXES = ("receipt:place:", "whole:place:", "relocation:place:")


def slot_reservations(point: CoordinatorSnapshot, slot_ids: frozenset[str]) -> tuple[str, ...]:
    require(type(point.leases) is tuple, "immutable leases required")
    seen: set[str] = set()
    reserved: list[str] = []
    for lease in point.leases:
        require(type(lease) is tuple and len(lease) == 2, "invalid lease pair")
        resource, job = lease
        identity(resource)
        identity(job)
        require(resource not in seen, "duplicate resource lease")
        seen.add(resource)
        if ":place:" not in resource:
            continue
        owner = resource.split(":place:", 1)[1]
        if owner in slot_ids or owner.startswith("v3:slot:"):
            require(resource.startswith(PLACE_PREFIXES), "unrecognized storage place lease")
            require(owner in slot_ids, "unknown reserved source slot")
            reserved.append(owner)
    return tuple(sorted(reserved))


def slot_loads(
    point: CoordinatorSnapshot, owners: list[Json], slot_ids: frozenset[str]
) -> tuple[SlotLoad, ...]:
    volume = {key: Fraction() for key in slot_ids}
    for container in point.stock.containers:
        if container.owner_id in volume:
            vector(container.recipe.outer)
            x, y, z = container.recipe.outer
            volume[container.owner_id] += x * y * z
    rows = []
    for row in owners:
        if row["kind"] != "slot":
            continue
        key = row["owner_id"]
        require(key in slot_ids, "unknown observed storage owner")
        mass = row["gross_mass_kg"]
        rows.append(
            SlotLoad(
                key,
                row["containers"],
                sum(row["units_by_sku"].values()),
                Fraction(mass["numerator"], mass["denominator"]),
                volume[key],
            )
        )
    require(len(rows) == len(slot_ids), "missing observed storage owner")
    return tuple(rows)
