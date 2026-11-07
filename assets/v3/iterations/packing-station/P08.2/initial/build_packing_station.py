"""P08.2 editable packing frame only; no runtime/final GLB publication.

Run through v3/run_build.py in fresh background Blender with two threads.
Later children add approved devices; the frame remains a separately inspectable
source checkpoint. Shared helpers and V2 files are never modified.
"""
from pathlib import Path
import hashlib
import json

import bpy

from v3_common import ROOT, VERSION, reset, material, group, box, runtime_xyz


ASSET_ID = "packing-station"
STAGE = "P08.2"
PLAN = ROOT / "assets/v3/specs/packing-station.dimensions.json"
ITERATION = ROOT / "assets/v3/iterations/packing-station" / STAGE


def build_frame():
    spec = json.loads(PLAN.read_text(encoding="utf-8"))
    root = group("packing-station__MODULE")
    for key, value in {
        "asset_id": ASSET_ID, "role": "packing_station_frame_stage",
        "stage": STAGE, "reference_id": "R04", "layout_version": VERSION,
        "dimension_plan": str(PLAN.relative_to(ROOT)).replace("\\", "/"),
        "worktop_y_m": .92, "clear_opening_width_m": 1.,
        "guarded_spur_width_m": .90, "world_centre_z_m": 5.2,
        "fixed_max_world_z_m": 5.65, "contains_cargo": False,
        "contains_worker": False, "final_asset": False,
    }.items():
        root[key] = value
    frame = group("frame__ASSEMBLY", parent=root)
    mats = {name: material("P08 | " + name, color, roughness=.86)
            for name, color in spec["reference"]["palette"].items()
            if name in {"tan", "petrol", "charcoal"}}
    for part in spec["parts"]:
        if part["group"] != "frame":
            continue
        bounds = part["bounds_local_xyz_m"]
        low, high = bounds["min"], bounds["max"]
        centre = [(low[k] + high[k]) / 2 for k in range(3)]
        size = [high[k] - low[k] for k in range(3)]
        bevel = .006 if part["part_id"].startswith("foot_") else .008
        obj = box(part["part_id"], centre, size,
                  mats[part["material"]], frame, bevel=bevel)
        obj["part_id"] = part["part_id"]
        obj["role"] = "packing_frame_component"
        obj["dimension_bounds_json"] = json.dumps(bounds)
    return root


def source_metrics(root):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    components = []
    all_points = []
    triangle_count = 0
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            points = [runtime_xyz(evaluated.matrix_world @ v.co) for v in mesh.vertices]
            mesh.calc_loop_triangles()
            triangle_count += len(mesh.loop_triangles)
            all_points.extend(points)
            components.append({
                "part_id": obj["part_id"], "mesh": obj.name,
                "bounds_runtime": {
                    "min": [min(p[k] for p in points) for k in range(3)],
                    "max": [max(p[k] for p in points) for k in range(3)]},
                "vertices": len(mesh.vertices),
                "triangles": len(mesh.loop_triangles),
                "materials": [m.name for m in obj.data.materials],
            })
        finally:
            evaluated.to_mesh_clear()
    bounds = {"min": [min(p[k] for p in all_points) for k in range(3)],
              "max": [max(p[k] for p in all_points) for k in range(3)]}
    return {"asset_id": ASSET_ID, "stage": STAGE,
            "method": "Actual evaluated bevel mesh vertices in runtime Y-up metres",
            "namespace": "v3", "layout_version": VERSION,
            "bounds_runtime": bounds,
            "dimensions_m": [bounds["max"][k] - bounds["min"][k] for k in range(3)],
            "mesh_parts": len(components), "triangles": triangle_count,
            "components": components, "final_asset": False, "glb_exported": False}


def save_stage(root):
    if not bpy.app.background:
        raise RuntimeError("Use task-background Blender only")
    ITERATION.mkdir(parents=True, exist_ok=True)
    source = ROOT / "assets/v3/blender/packing-station.blend"
    source.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    snapshot = ITERATION / "packing-station.blend"
    snapshot.write_bytes(source.read_bytes())
    report = source_metrics(root)
    report.update(source=str(source), snapshot=str(snapshot),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest())
    (ITERATION / "source-metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("P08_2_SOURCE_READY " + json.dumps({k: report[k] for k in
          ["mesh_parts", "triangles", "dimensions_m", "source_sha256"]}))
    return report


if __name__ == "__main__":
    reset()
    save_stage(build_frame())
