"""Queued short source poses/closeups only; no source save or GLB export."""
from pathlib import Path
import hashlib
import json
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from render_asset import render
from v3_common import xyz

OUT = Path(__file__).resolve().parent


def closeup(name, names, direction):
    points = []
    graph = bpy.context.evaluated_depsgraph_get()
    for obj_name in names:
        obj = bpy.data.objects[obj_name]
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    target = (low + high) * .5
    extent = max(high - low)
    scene = bpy.context.scene
    cam = scene.camera
    cam.location = target + xyz(direction).normalized() * extent * 3
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    inverse = cam.rotation_euler.to_quaternion().inverted()
    projected = [inverse @ (point - target) for point in points]
    centre = Vector(tuple((min(p[i] for p in projected) + max(p[i] for p in projected)) / 2 for i in range(2)) + (0,))
    shift = cam.rotation_euler.to_quaternion() @ centre
    cam.location += shift
    target += shift
    projected = [inverse @ (point - target) for point in points]
    cam.data.ortho_scale = 2 * max(abs(p[i]) for p in projected for i in range(2)) * 1.18
    directory = OUT / "closeups"
    directory.mkdir(exist_ok=True)
    path = directory / (name + ".png")
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "focus_objects": names, "runtime_camera_direction": direction}


results = {}
for pose in ("neutral", "bent-arm", "bent-knee", "waist-bend"):
    bpy.ops.wm.open_mainfile(filepath=str(OUT / (pose + ".blend")))
    result = render("worker-base", 900, OUT / pose)
    result["closeups"] = []
    if pose == "neutral":
        result["closeups"].append(closeup("neutral-hand-gauge",
            ["mitten_R_spine", "mitten_R_upper_pad", "mitten_R_lower_pad", "mitten_R_thumb", "QA_ONLY__grip_gauge_R"], (1, .35, 1.7)))
    elif pose == "bent-arm":
        result["closeups"].append(closeup("bent-elbow-hand",
            ["upper_sleeve_R", "fore_sleeve_R", "cuff_R", "mitten_R_spine", "mitten_R_upper_pad", "mitten_R_lower_pad", "mitten_R_thumb", "QA_ONLY__grip_gauge_R"], (1.4, .3, 1.2)))
    elif pose == "bent-knee":
        result["closeups"].append(closeup("bent-hip-knee-sole",
            ["pelvis_cloth", "trouser_thigh_R", "trouser_shin_R", "boot_R"], (1.5, .25, 1.1)))
    else:
        result["closeups"].append(closeup("waist-back",
            ["pelvis_cloth", "shirt_core", "vest_back"], (1, .1, -1.7)))
        result["closeups"].append(closeup("neck-bent",
            ["short_neck", "cuboid_head", "connected_shoulder_band"], (1.5, .15, 1.4)))
    results[pose] = result
    (OUT / (pose + ".render.json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("P013_POSES_RENDERED " + json.dumps({"poses": 4, "full_views": 16,
      "closeups": sum(len(result["closeups"]) for result in results.values())}))
