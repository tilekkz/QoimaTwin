"""One exact source binding and one proposed action; not a general pallet planner."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import numpy as np

from app.v3.pallet_outbound_pickup_frames import ry, vector
from app.v3.pallet_outbound_pickup_identity import identity, require, require_same
from app.v3.pallet_outbound_pickup_models import PickupPlan, PickupPose, PickupSegment, PickupSource
from app.v3.pallet_outbound_pickup_source import document, verify_pickup_source

HU_ID = "v3:HU:initial:DEMO_172:01"
METHOD = "qoima-e011-pallet-pickup-geometry-v1"


def selected(source: PickupSource) -> dict[str, Any]:
    assignment = next(
        a
        for a in document(source, "baseline-assignment-v3.json")["assignments"]
        if a["handling_unit_id"] == HU_ID
    )
    storage = document(source, "storage-slots-v3.json")
    module = next(m for m in storage["modules"] if m["module_id"] == assignment["module_id"])
    slot = next(s for s in storage["slots"] if s["slot_id"] == assignment["slot_id"])
    graph = document(source, "layout-links-v3.json")["vehicle_graph"]
    node = next(n for n in graph["nodes"] if n["node_id"] == slot["service_node_id"])
    arc = next(
        a
        for a in graph["arcs"]
        if a["arc_id"] == slot["access"]["vehicle_approach_id"] + ":segment:002:r"
    )
    catalog = next(
        c
        for c in document(source, "cargo-catalog-v3.json")["records"]
        if c["archetype_id"] == assignment["archetype_id"]
    )
    handling = document(source, "vehicle-handling-v3.json", "v3-vehicle-proposal")
    load = next(c for c in handling["loads"] if c["archetype_id"] == assignment["archetype_id"])
    pair = next(
        p
        for p in document(source, "port-resource-policy-v3.json")["forklift_pairs"]
        if p["pair_id"] == "OUTBOUND_FORKLIFT_PAIR"
    )
    return dict(
        assignment=assignment,
        module=module,
        slot=slot,
        node=node,
        arc=arc,
        catalog=catalog,
        load=load,
        pair=pair,
    )


def proposed_segments() -> tuple[PickupSegment, ...]:
    rows = (
        ("-1", ".7", "0"),
        ("-1", ".7", ".4"),
        ("-1", ".18", ".4"),
        ("0", ".18", ".4"),
        ("0", ".7", ".4"),
        ("0", ".7", "0"),
        ("-1", ".7", "0"),
    )
    poses = tuple(PickupPose(*(F(v) for v in row)) for row in rows)
    phases = (
        "extend_high",
        "lower_extended",
        "controlled_insert",
        "lift_loaded",
        "retract_loaded",
        "travel_reverse",
    )
    return tuple(
        PickupSegment(i, phase, poses[i], poses[i + 1], i >= 3) for i, phase in enumerate(phases)
    )


def _check_facts(facts: dict[str, Any]) -> None:
    a, c, p = facts["assignment"], facts["catalog"], facts["pair"]
    require(
        a["slot_id"] == "v3:slot:HEAVY_E:011:L1:B1"
        and a["quantity_units"] == 24
        and a["model_scale_factor"] == 1,
        "Original E011 HU binding required",
    )
    require(
        a["orientation_id"] == "upright_xyz"
        and c["orientation"]["permitted_orientations"][0]["local_axes_in_destination"]
        == ["+X", "+Y", "+Z"],
        "Signed HU axes required",
    )
    require(p["actor_id"] == "F02" and p["vehicle_id"] == "FL02", "Outbound pair required")
    require(
        facts["load"]["HU_gross_mass_kg"] == 455 and c["handling_unit"]["gross_mass_kg"] == 455,
        "Source mass ancestry mismatch",
    )


def compile_pickup_plan(source: PickupSource) -> PickupPlan:
    verify_pickup_source(source)
    facts = selected(source)
    _check_facts(facts)
    a, module, node = facts["assignment"], facts["module"], facts["node"]
    rotation = ry(float(module["yaw_rad"])) @ np.diag([-1.0, 1.0, -1.0])
    origin = np.array(module["world_pos"]) - rotation @ np.array([0.0, 0.0, 1.5])
    root = np.array(node["world_pos"])
    require(
        np.allclose(rotation.T @ (root - origin), [0, 0, -1], rtol=0, atol=2e-6),
        "Actual E011 prehandle differs",
    )
    bottom = np.array(a["placement"]["centre_local_xyz_m"], dtype=float)
    bottom[1] = a["placement"]["bottom_y_m"]
    hu_bottom = np.array(module["world_pos"]) + ry(float(module["yaw_rad"])) @ bottom
    plan = PickupPlan(
        METHOD,
        source.source_hash,
        HU_ID,
        a["slot_id"],
        a["module_id"],
        a["sku_id"],
        a["lot_id"],
        tuple(f"{HU_ID}:unit:{i:04d}" for i in range(1, 25)),
        "F02",
        "FL02",
        vector(root),
        float(node["yaw_rad"]),
        vector(origin),
        float(node["yaw_rad"]),
        vector(hu_bottom),
        float(module["yaw_rad"]),
        proposed_segments(),
        "proposed_six_step_exact_prehandle_v1",
        False,
        False,
        "",
    )
    return replace(plan, plan_hash=identity(plan))


def verify_pickup_plan(source: PickupSource, plan: PickupPlan) -> None:
    require_same(plan, compile_pickup_plan(source))
