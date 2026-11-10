"""Bounded source detail QA: immutable core comparison, actual mesh support,6stills."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
ITERATION = "02"
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from render_asset import render
from v3_common import xyz, runtime_xyz

module_spec = importlib.util.spec_from_file_location("pose_mesh_checks", OUT.parent / "P01.3/check_poses.py")
check = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(check)


def actual_vertices(obj):
    shape = check.tree(obj)
    return sorted(tuple(point) for point in shape["vertices"])


def closeup(name, names, direction):
    graph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj_name in names:
        evaluated = bpy.data.objects[obj_name].evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    target = (low + high) * .5
    cam = bpy.context.scene.camera
    cam.location = target + xyz(direction).normalized() * max(high - low) * 3
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    inverse = cam.rotation_euler.to_quaternion().inverted()
    projected = [inverse @ (p - target) for p in points]
    centre = Vector(tuple((min(p[i] for p in projected) + max(p[i] for p in projected)) / 2 for i in range(2)) + (0,))
    shift = cam.rotation_euler.to_quaternion() @ centre
    cam.location += shift
    target += shift
    projected = [inverse @ (p - target) for p in points]
    cam.data.ortho_scale = 2 * max(abs(p[i]) for p in projected for i in range(2)) * 1.18
    path = OUT / ("iteration-" + ITERATION) / (name + ".png")
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


old_source = OUT.parent / "P01.3/iteration-01.blend"
bpy.ops.wm.open_mainfile(filepath=str(old_source))
core = {obj.name: actual_vertices(obj) for obj in bpy.data.objects
        if obj.type == "MESH" and not obj.name.startswith("rough_")}
source = ROOT / "assets/v3/blender/worker-base.blend"
bpy.ops.wm.open_mainfile(filepath=str(source))
root = bpy.data.objects["worker_base_root"]
assert not any(obj.name.startswith("QA_ONLY") for obj in bpy.data.objects)
for name, vertices in core.items():
    assert actual_vertices(bpy.data.objects[name]) == vertices, name
shapes = {obj.name: check.tree(obj) for obj in root.children_recursive if obj.type == "MESH"}
support = []
def contact(a, b, point):
    margins = [check.margin(shapes[name], xyz(point)) for name in (a, b)]
    assert min(margins) > .0001, (a, b, margins)
    support.append({"parts": [a, b], "witness_runtime_m": point,
                    "inside_actual_closed_meshes": True, "surface_margins_m": margins})
for sign, side in ((-1, "L"), (1, "R")):
    contact("face_eye_" + side, "cuboid_head", (sign * .063, 1.355, .1495))
    contact("face_brow_" + side, "cuboid_head", (sign * .063, 1.411, .1495))
    contact("ear_" + side, "cuboid_head", (sign * .158, 1.331, -.005))
    contact("hair_temple_" + side, "cuboid_head", (sign * .163, 1.414, -.059))
contact("face_smile", "cuboid_head", (0, 1.261, .1495))
contact("hair_back", "cuboid_head", (0, 1.377, -.139))
contact("hair_back", "helmet_brim", (0, 1.460, -.141))
contact("role_badge_base", "vest_front_L", (-.105, 1.015, .129))
contact("role_badge_cart", "role_badge_base", (-.105, 1.039, .1392))
contact("role_badge_cart_handle", "role_badge_base", (-.1195, 1.042, .1395))
contact("role_badge_cart_grip", "role_badge_base", (-.127, 1.0565, .1395))
contact("role_badge_cart_handle", "role_badge_cart", (-.117, 1.037, .1410))
contact("role_badge_cart_grip", "role_badge_cart_handle", (-.123, 1.055, .1410))
for side, x in (("L", -.111), ("R", -.087)):
    contact("role_badge_cart_wheel_" + side, "role_badge_base", (x, 1.020, .1392))
letter_vertices = [runtime_xyz(p) for p in shapes["role_badge_code_01"]["vertices"]]
letter_z = [p[2] for p in letter_vertices]
assert min(letter_z) < .1395 and max(letter_z) > .1415
assert all(-.15 < p[0] < -.06 and .96 < p[1] < 1.07 for p in letter_vertices)
assert len([o for o in root.children_recursive if o.get("pivot_id")]) == 15
assert len([o for o in root.children_recursive if o.get("anchor_id")]) == 7
role_names = root["role_tint_materials"].split(";")
assert role_names == ["V3_Worker_RoleVest", "V3_Worker_RoleHeadwear"]
report = {"unchanged_actual_core_meshes_vs_P01_3": len(core), "actual_mesh_detail_contacts": support,
          "badge_code_actual_z_range_m": [min(letter_z), max(letter_z)],
          "named_role_tint_slots": role_names, "qa_gauges_in_canonical_source": False,
          "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
(OUT / ("iteration-" + ITERATION + ".actual-detail-checks.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
result = render("worker-base", 900, OUT / ("iteration-" + ITERATION))
result["closeups"] = [
    closeup("face-close", ["cuboid_head", "ear_L", "ear_R", "helmet_brim"], (1, .1, 2.7)),
    closeup("badge-close", ["role_badge_base", "role_badge_code_01", "role_badge_cart"], (.35, .1, 2.7))]
(OUT / ("iteration-" + ITERATION + ".render.json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
assert hashlib.sha256(source.read_bytes()).hexdigest() == report["source_sha256"]
print("P014_DETAILS_VERIFIED " + json.dumps({"core_meshes_unchanged": len(core),
      "actual_detail_contacts": len(support), "full_views": 4, "closeups": 2}))
