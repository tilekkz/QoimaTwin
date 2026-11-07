"""Actual saved-device surface measurements; preserves initial plan history."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
spec = json.loads((ROOT / "assets/v3/specs/packing-station.dimensions.json").read_text(encoding="utf-8"))
root = next(o for o in bpy.context.scene.objects if o.get("asset_id") == "packing-station")
vertices, triangles, owners = [], [], []
graph = bpy.context.evaluated_depsgraph_get()
for obj in root.children_recursive:
    if obj.type != "MESH":
        continue
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    try:
        offset = len(vertices)
        for v in mesh.vertices:
            p = evaluated.matrix_world @ v.co
            vertices.append(Vector((p.x, p.z, -p.y)))
        for tri in mesh.loop_triangles:
            triangles.append(tuple(offset + i for i in tri.vertices))
            owners.append(obj["part_id"])
    finally:
        evaluated.to_mesh_clear()
bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
requests = {
    "anchor_scanner_contact": ((-.69, 1.16, .7), (0, 0, -1), "scanner_recessed_lens", "measured_optical_scan_surface"),
    "anchor_label_pick": ((.60, 1.3, .38), (0, -1, 0), "label_presenter", "measured_paper_pick_surface"),
    "anchor_tape_pull": ((.735, 1.06, .7), (0, 0, -1), "tape_cutter_pedestal", "measured_cutter_front_surface_not_animated_tape_end"),
    "anchor_screen_face": ((-.70, 1.33, .7), (0, 0, -1), "screen_recess", "measured_blank_display_surface"),
    "anchor_worktop_L": ((-.70, 1.5, 0), (0, -1, 0), "worktop_L", "measured_worktop_surface"),
    "anchor_worktop_R": ((.70, 1.5, 0), (0, -1, 0), "worktop_R", "measured_worktop_surface"),
}
initial = {a["anchor_id"]: a for a in spec["anchors"]}
measured = []
for aid, (origin, direction, expected, role) in requests.items():
    point, normal, index, distance = bvh.ray_cast(Vector(origin), Vector(direction), 2.)
    assert point is not None and owners[index] == expected, (aid, owners[index] if index is not None else None)
    old = initial.get(aid, {}).get("local_xyz_m")
    old_hit = bvh.find_nearest(Vector(old)) if old else None
    row = {"anchor_id": aid, "local_xyz_m": [round(c, 6) for c in point],
           "normal_runtime": [round(c, 6) for c in normal], "physical_part": owners[index],
           "role": role, "authority": "actual_saved_source_BVH_surface",
           "initial_plan_local_xyz_m": old,
           "ray_origin": list(origin), "ray_direction": list(direction),
           "actual_hit_local_xyz_m": list(point), "ray_distance_m": distance}
    if old_hit:
        row["old_proxy_nearest_actual_part"] = owners[old_hit[2]]
        row["old_proxy_distance_to_geometry_m"] = old_hit[3]
        row["override_delta_m"] = math.dist(old, row["local_xyz_m"])
    measured.append(row)
anchors = []
byid = {a["anchor_id"]: a for a in measured}
for item in spec["anchors"]:
    aid = item["anchor_id"]
    if aid in byid:
        anchors.append(byid[aid])
    else:
        row = {**item, "initial_plan_local_xyz_m": item["local_xyz_m"]}
        row["authority"] = ("unpaired_future_hand_pose_target" if "anchor_hand_work" in aid else
                            "logical_contract_service" if aid == "anchor_worker_service" else
                            "intentionally_empty_ring_axis_not_surface" if aid == "anchor_tape_ring" else
                            "transport_section_pending_pair_measurement")
        anchors.append(row)
anchors += [a for a in measured if a["anchor_id"] not in initial]
source = Path(bpy.data.filepath)
report = {"asset_id": "packing-station", "namespace": "v3", "stage": "P08.4",
          "status": "VERIFY", "units": "metres", "coordinate_system": "parent_local_runtime_XYZ_Y_up",
          "measured_at_utc": datetime.now(timezone.utc).isoformat(),
          "measured_geometry_source": "assets/v3/iterations/packing-station/P08.3/packing-station.blend",
          "measured_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
          "anchors": anchors,
          "overrides": [a for a in measured if a["initial_plan_local_xyz_m"] is not None],
          "limits": ["Hand/torso/foot workflow not accepted; changed scan/pick targets must be used by later P04, without stretching the worker.",
                     "Ring centre is intentionally in a void, not labelled a contact. Initial dimension plan remains unchanged."]}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "device-measurements.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
(ROOT / "assets/v3/blender/packing-station.anchors.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("MEASURED_P08_4_ANCHORS " + json.dumps([{k: a[k] for k in ["anchor_id", "local_xyz_m", "physical_part", "normal_runtime"]} for a in measured]))
