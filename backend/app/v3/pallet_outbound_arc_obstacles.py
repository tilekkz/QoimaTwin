"""Original warehouse boxes with source XZ/top padding; no traffic or dynamic occupancy."""

import numpy as np

from app.v3.pallet_outbound_arc_models import ArcObstacles, ArcPlan
from app.v3.pallet_outbound_pickup_frames import vector
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import PickupBounds, PickupPlan, PickupSource
from app.v3.pallet_outbound_pickup_obstacles import _hu_box
from app.v3.pallet_outbound_pickup_source import document

BoxRows = tuple[tuple[str, PickupBounds], ...]


def horizontal_gap(first: PickupBounds, second: PickupBounds) -> float:
    gaps = np.maximum(np.array(first.low) - second.high, np.array(second.low) - first.high)
    return float(max(gaps[0], gaps[2]))


def check_padding(
    box: PickupBounds, obstacles: BoxRows, padding: float
) -> tuple[tuple[str, ...], float]:
    gaps = tuple(horizontal_gap(box, other) for _, other in obstacles)
    require(
        bool(gaps) and all(gap >= padding - 2e-6 for gap in gaps),
        "Continuous arc bounds violate source obstacle padding",
    )
    return tuple(sorted(name for name, _ in obstacles)), min(gaps)


def _modules(source: PickupSource) -> BoxRows:
    return tuple(
        (
            str(row["module_id"]),
            PickupBounds(
                vector(np.array(row["operating_bounds_world"]["min"])),
                vector(np.array(row["operating_bounds_world"]["max"])),
            ),
        )
        for row in document(source, "storage-slots-v3.json")["modules"]
    )


def _stock(source: PickupSource, pickup: PickupPlan) -> BoxRows:
    modules = {
        row["module_id"]: row for row in document(source, "storage-slots-v3.json")["modules"]
    }
    dimensions = {
        row["archetype_id"]: row["handling_unit"]["dimensions_xyz_m"]
        for row in document(source, "cargo-catalog-v3.json")["records"]
    }
    return tuple(
        (
            str(row["handling_unit_id"]),
            _hu_box(row, modules[row["module_id"]], dimensions[row["archetype_id"]]),
        )
        for row in document(source, "baseline-assignment-v3.json")["assignments"]
        if row["handling_unit_id"] != pickup.hu_id
    )


def check_envelope(box: PickupBounds, envelope: PickupBounds, plan: ArcPlan) -> float:
    low, high = np.array(box.low), np.array(box.high)
    pad = float(plan.padding_m)
    require(
        bool(
            np.all(low >= np.array(envelope.low) - 2e-6)
            and np.all(high <= np.array(envelope.high) + 2e-6)
        ),
        "Arc outside source envelope",
    )
    require(
        bool(
            np.all(low[[0, 2]] >= np.array(envelope.low)[[0, 2]] + pad - 2e-6)
            and np.all(high[[0, 2]] <= np.array(envelope.high)[[0, 2]] - pad + 2e-6)
        ),
        "Source horizontal envelope padding violated",
    )
    headroom = (
        min(float(plan.clear_height_m), envelope.high[1]) - box.high[1] - float(plan.top_padding_m)
    )
    require(headroom >= -2e-6, "Source top padding violated")
    return headroom


def check_obstacles(
    source: PickupSource,
    pickup: PickupPlan,
    plan: ArcPlan,
    box: PickupBounds,
) -> ArcObstacles:
    modules, module_gap = check_padding(box, _modules(source), float(plan.padding_m))
    hus, hu_gap = check_padding(box, _stock(source, pickup), float(plan.padding_m))
    raw = document(source, "layout-v3.envelope.json")["bounds"]
    envelope = PickupBounds(vector(np.array(raw["min"])), vector(np.array(raw["max"])))
    return ArcObstacles(modules, hus, module_gap, hu_gap, check_envelope(box, envelope, plan), True)
