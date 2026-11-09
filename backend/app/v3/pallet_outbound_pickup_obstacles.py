"""Conservative source module/initial-HU bounds; no dynamic occupancy assertion."""

from typing import Any

import numpy as np

from app.v3.pallet_outbound_pickup_frames import ry, vector
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import (
    PickupBounds,
    PickupObstacles,
    PickupPlan,
    PickupSource,
)
from app.v3.pallet_outbound_pickup_source import document


def separation(first: PickupBounds, second: PickupBounds) -> float:
    gap = np.maximum(np.array(first.low) - second.high, np.array(second.low) - first.high)
    return float(gap.max())


def _modules(
    source: PickupSource, plan: PickupPlan, action: PickupBounds
) -> tuple[tuple[str, ...], list[float]]:
    identifiers, gaps = [], []
    for module in document(source, "storage-slots-v3.json")["modules"]:
        if module["module_id"] == plan.module_id:
            continue
        box = module["operating_bounds_world"]
        bounds = PickupBounds(vector(np.array(box["min"])), vector(np.array(box["max"])))
        gap = separation(action, bounds)
        require(gap >= 0.0, "Other source module intersects pickup action bounds")
        identifiers.append(str(module["module_id"]))
        gaps.append(gap)
    return tuple(sorted(identifiers)), gaps


def _hu_box(cargo: dict[str, Any], module: dict[str, Any], dimensions: list[float]) -> PickupBounds:
    require(
        cargo["orientation_id"] == "upright_xyz" and cargo["model_scale_factor"] == 1,
        "Unsupported original stock orientation/scale",
    )
    rotation = ry(module["yaw_rad"])
    centre = np.array(module["world_pos"]) + rotation @ cargo["placement"]["centre_local_xyz_m"]
    half = np.abs(rotation) @ (np.array(dimensions) / 2)
    return PickupBounds(vector(centre - half), vector(centre + half))


def _stock(source: PickupSource, plan: PickupPlan, action: PickupBounds) -> tuple[str, ...]:
    modules = {m["module_id"]: m for m in document(source, "storage-slots-v3.json")["modules"]}
    dimensions = {
        c["archetype_id"]: c["handling_unit"]["dimensions_xyz_m"]
        for c in document(source, "cargo-catalog-v3.json")["records"]
    }
    result = []
    for cargo in document(source, "baseline-assignment-v3.json")["assignments"]:
        if cargo["handling_unit_id"] == plan.hu_id:
            continue
        box = _hu_box(cargo, modules[cargo["module_id"]], dimensions[cargo["archetype_id"]])
        require(separation(action, box) >= 0.0, "Other original HU intersects pickup action bounds")
        result.append(str(cargo["handling_unit_id"]))
    return tuple(sorted(result))


def check_obstacles(
    source: PickupSource, plan: PickupPlan, action: PickupBounds
) -> PickupObstacles:
    module_ids, gaps = _modules(source, plan, action)
    hu_ids = _stock(source, plan, action)
    envelope = document(source, "layout-v3.envelope.json")["bounds"]
    require(
        bool(
            np.all(np.array(action.low) >= np.array(envelope["min"]) - 2e-6)
            and np.all(np.array(action.high) <= np.array(envelope["max"]) + 2e-6)
        ),
        "Pickup action outside source envelope",
    )
    return PickupObstacles(module_ids, hu_ids, min(gaps), True)
