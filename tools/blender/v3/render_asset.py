"""Deferred neutral four-view QA; run only when root grants the render queue.

blender --background --factory-startup assets/v3/blender/<id>.blend --threads 2 --python
tools/blender/v3/render_asset.py -- <id> [--size 900] [--out /absolute/path]

Actual evaluated vertices determine fit. Studio floor/camera are created outside
the asset hierarchy and never saved back into its editable .blend or GLB.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v3_common import ROOT, STUDIO_COLLECTION, xyz


def render(asset_id, size=900, output=None):
    if not bpy.app.background:
        raise RuntimeError("Use the queued task-background renderer")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", asset_id):
        raise ValueError("Invalid V3 asset_id")
    roots = [obj for obj in bpy.context.scene.objects
             if obj.get("namespace") == "v3" and obj.get("asset_id") == asset_id]
    if len(roots) != 1:
        raise ValueError("Open exactly one matching saved V3 asset root")
    root = roots[0]
    objects = ([root] if root.type == "MESH" else []) + [
        obj for obj in root.children_recursive if obj.type == "MESH"]
    graph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
        evaluated.to_mesh_clear()
    if not points:
        raise ValueError("No asset vertices to frame")
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    target = (low + high) * .5
    extent = max(high - low)
    studio = bpy.data.collections.get(STUDIO_COLLECTION)
    if studio is None:
        studio = bpy.data.collections.new(STUDIO_COLLECTION)
        bpy.context.scene.collection.children.link(studio)
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in objects:
            obj.hide_render = True
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.studiolight_rotate_z = .35
    shading.color_type = "MATERIAL"
    shading.show_shadows = True
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.curvature_ridge_factor = .65
    shading.curvature_valley_factor = .55
    shading.show_specular_highlight = False
    shading.background_type = "WORLD"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("V3_QA_World")
    scene.world.color = (.48, .49, .48)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = .7
    bpy.ops.mesh.primitive_plane_add(size=extent * 10,
                                     location=(target.x, target.y, low.z - .002))
    floor = bpy.context.object
    floor.name = "STUDIO_ONLY__floor"
    floor.color = (.65, .66, .64, 1)
    for collection in list(floor.users_collection):
        collection.objects.unlink(floor)
    studio.objects.link(floor)
    mat = bpy.data.materials.new("STUDIO_ONLY__neutral_floor")
    mat.diffuse_color = (.65, .66, .64, 1)
    floor.data.materials.append(mat)
    data = bpy.data.cameras.new("STUDIO_ONLY__camera")
    cam = bpy.data.objects.new("STUDIO_ONLY__camera", data)
    studio.objects.link(cam)
    scene.camera = cam
    data.type = "ORTHO"
    data.clip_start = max(.001, extent * .001)
    data.clip_end = extent * 20
    output = Path(output) if output else ROOT / "assets/v3/previews" / asset_id
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for name, runtime_direction in (("front", (0, .02, 1)), ("side", (1, .02, 0)),
                                    ("rear", (0, .02, -1)), ("three-quarter", (1.25, .8, 1.6))):
        cam.location = target + xyz(runtime_direction).normalized() * extent * 3
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        inverse = cam.rotation_euler.to_quaternion().inverted()
        projected = [inverse @ (point - target) for point in points]
        original_low = [min(p[i] for p in projected) for i in range(2)]
        original_high = [max(p[i] for p in projected) for i in range(2)]
        old_scale = max(original_high[i] - original_low[i] for i in range(2)) * 1.16
        centre = Vector(((original_low[0] + original_high[0]) * .5,
                         (original_low[1] + original_high[1]) * .5, 0))
        # World AABB midpoint need not be the centre of the projected vertices.
        # Translate camera AND its target in camera-right/up; orientation stays
        # fixed. Then fit max absolute projected extent, not an assumed span/2.
        shift = cam.rotation_euler.to_quaternion() @ centre
        view_target = target + shift
        cam.location += shift
        projected = [inverse @ (point - view_target) for point in points]
        half_extent = max(abs(p[i]) for p in projected for i in range(2))
        data.ortho_scale = 2 * half_extent * 1.16
        low_xy = [min(p[i] for p in projected) for i in range(2)]
        high_xy = [max(p[i] for p in projected) for i in range(2)]
        ndc_low = [2 * value / data.ortho_scale for value in low_xy]
        ndc_high = [2 * value / data.ortho_scale for value in high_xy]
        if max(abs(v) for v in ndc_low + ndc_high) > 1 / 1.16 + .000001:
            raise AssertionError("Projected asset does not have its full framing margin")
        pixel_bounds = {"left": (.5 + low_xy[0] / data.ortho_scale) * size,
                        "right": (.5 + high_xy[0] / data.ortho_scale) * size,
                        "top": (.5 - high_xy[1] / data.ortho_scale) * size,
                        "bottom": (.5 - low_xy[1] / data.ortho_scale) * size}
        reports[name] = {"original_projected_bounds": {"min": original_low, "max": original_high},
                         "old_max_abs_ndc": max(abs(v) * 2 / old_scale for v in original_low + original_high),
                         "projected_centre_shift": list(centre[:2]),
                         "projected_bounds": {"min": low_xy, "max": high_xy},
                         "ortho_scale": data.ortho_scale, "margin_factor": 1.16,
                         "ndc_bounds": {"min": ndc_low, "max": ndc_high},
                         "expected_asset_pixel_bounds": pixel_bounds}
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        reports[name]["png"] = str(output / (name + ".png"))
        reports[name]["sha256"] = hashlib.sha256((output / (name + ".png")).read_bytes()).hexdigest()
    report = {"asset_id": asset_id, "output": str(output), "resolution_px": [size, size],
              "fit_method": "projected bbox recenter +2*maxabs extent*1.16", "exposure": .7,
              "views": reports}
    print("V3_QA_RENDERED " + json.dumps(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_id")
    parser.add_argument("--size", type=int, default=900)
    parser.add_argument("--out")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    render(args.asset_id, args.size, args.out)
