"""Four complete source views and two explicitly framed architectural crops."""
from pathlib import Path
import hashlib
import json
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent / "iteration-01"
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from render_asset import render
from v3_common import xyz

bpy.ops.wm.open_mainfile(filepath=str(ROOT / "assets/v3/blender/environment-shell.blend"))
report = render("environment-shell", 900, OUT)


def detail(name, low, high, direction):
    points = [xyz((x, y, z)) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
    target = xyz([(a+b)/2 for a, b in zip(low, high)])
    cam = bpy.context.scene.camera
    cam.location = target + xyz(direction).normalized()*40
    cam.rotation_euler = (target-cam.location).to_track_quat("-Z", "Y").to_euler()
    inverse = cam.rotation_euler.to_quaternion().inverted()
    projected = [inverse@(point-target) for point in points]
    centre = Vector(tuple((min(p[i] for p in projected)+max(p[i] for p in projected))/2 for i in range(2))+(0,))
    shift = cam.rotation_euler.to_quaternion()@centre
    cam.location += shift
    target += shift
    projected = [inverse@(point-target) for point in points]
    cam.data.ortho_scale = 2*max(abs(p[i]) for p in projected for i in range(2))*1.12
    path = OUT / (name+".png")
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "explicit_context_crop_runtime_bounds": {"min": low, "max": high}}


report["architectural_detail_crops"] = [detail("corner-SW-close", [0, -.55, 0], [14, 8, 14], (1, .65, 1)),
                                         detail("port-IN_W-close", [0, -.55, 12.8], [4, 8, 23.2], (1.8, .5, .6))]
(OUT.parent / "iteration-01.render.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
print("SHELL_SOURCE_RENDERED4complete+2architectural_crops")
