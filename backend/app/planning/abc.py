"""Frozen ABC baseline assignment from training visits (01 §9).

Ground slots are ordered by mean home round trip (homes weighted equally), then slot_id.
SKUs are ordered by descending training visits, then sku_id. The i-th SKU gets the i-th slot;
the remaining ground slots stay empty. Every active lot follows its SKU; reserve lots, their
slots and all quantities are unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.contracts.assignment import Assignment, InitialLot
from app.contracts.layout import Layout
from app.planning.errors import PlanningInputError
from app.planning.geometry import PlanningGeometry
from app.planning.visits import exact_visits, visits_hash
from app.storage.canonical_json import sha256_hex

ABC_PROVENANCE_KIND = "frozen_abc_training_visits"


def build_frozen_abc(
    layout: Layout,
    baseline: Assignment,
    training_visits: Mapping[str, float],
    *,
    geometry: PlanningGeometry | None = None,
) -> Assignment:
    """Deterministic frozen ABC assignment; training visits must cover exactly the active SKUs."""
    geo = geometry or PlanningGeometry.from_layout(layout)
    _check_baseline(layout, baseline, geo)
    visits = exact_visits(training_visits, baseline.active_assignment.values(), "training_visits")
    ranked = sorted(visits, key=lambda sku: (-visits[sku], sku))
    slots = geo.ground_slots_by_cost()
    if len(ranked) > len(slots):
        raise PlanningInputError(f"{len(ranked)} SKUs exceed {len(slots)} ground slots")
    slot_of = dict(zip(ranked, slots[: len(ranked)], strict=True))
    digest = visits_hash(training_visits)
    identity = sha256_hex(
        [
            digest,
            _placement_free_hash(baseline),
            list(baseline.empty_reserve_slots),
            layout.layout_version,
        ]
    )
    return _rebuild(baseline, slot_of, slots[len(ranked) :], digest, identity)


def _check_baseline(layout: Layout, baseline: Assignment, geo: PlanningGeometry) -> None:
    if baseline.layout_version != layout.layout_version:
        raise PlanningInputError(
            f"assignment layout {baseline.layout_version} != {layout.layout_version}"
        )
    for slot in baseline.active_assignment:
        if not geo.is_ground(slot):
            raise PlanningInputError(f"active slot {slot} is not a ground pick-face")
    skus = list(baseline.active_assignment.values())
    if len(skus) != len(set(skus)):
        raise PlanningInputError("active assignment places one SKU on two slots")
    active = active_lots(baseline)
    if set(active) != set(baseline.active_assignment):
        raise PlanningInputError("every active slot needs exactly one lot of its SKU")


def active_lots(assignment: Assignment) -> dict[str, InitialLot]:
    """Active slot -> its single lot; raises if a slot holds several lots or a foreign SKU."""
    result: dict[str, InitialLot] = {}
    for lot in assignment.initial_lots:
        sku = assignment.active_assignment.get(lot.slot_id)
        if sku is None:
            continue
        if sku != lot.sku_id or lot.slot_id in result:
            raise PlanningInputError(f"slot {lot.slot_id} does not hold exactly one {sku} lot")
        result[lot.slot_id] = lot
    return result


def _placement_free_hash(baseline: Assignment) -> str:
    """Lots and quantities without slots: the ABC result does not depend on the old placement."""
    lots = sorted(baseline.initial_lots, key=lambda lot: lot.lot_id)
    active = set(baseline.active_assignment)
    return sha256_hex(
        [
            [lot.lot_id, lot.sku_id, lot.quantity, None if lot.slot_id in active else lot.slot_id]
            for lot in lots
        ]
    )


def _rebuild(
    baseline: Assignment,
    slot_of: dict[str, str],
    empty: tuple[str, ...],
    digest: str,
    identity: str,
) -> Assignment:
    lots = []
    for lot in baseline.initial_lots:
        data = lot.model_dump(mode="json")
        if lot.slot_id in baseline.active_assignment:
            data["slot_id"] = slot_of[lot.sku_id]
        lots.append(data)
    return Assignment.from_data(
        {
            "schema_version": baseline.schema_version,
            "layout_version": baseline.layout_version,
            "assignment_id": f"frozen-abc-{identity[:16]}",
            "provenance": {
                "kind": ABC_PROVENANCE_KIND,
                "note": f"training visits sha256={digest}; base={baseline.assignment_id}",
            },
            "active_assignment": {slot: sku for sku, slot in sorted(slot_of.items())},
            "initial_lots": lots,
            "empty_pickfaces": sorted(empty),
            "empty_reserve_slots": list(baseline.empty_reserve_slots),
        }
    )
