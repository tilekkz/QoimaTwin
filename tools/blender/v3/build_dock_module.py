"""P09.1 standard retail dock: source quality gate, explicit later GLB export.

All actual solids stay inside the accepted L11 jamb/header union. Origin is
floor aperture centre; +Z is inward. No door/threshold or layout mutation.
"""
import argparse
import hashlib
import json
import shutil
import sys

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

from v3_common import ROOT, reset, group, box, material, anchor, xyz, runtime_xyz, finish

SPEC = ROOT / "assets/v3/specs/dock-module.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/dock-module.blend"
STAGE = ROOT / "assets/v3/iterations/dock-module/P09.1"


def u_profile(name, data, mat, parent):
    """One connected closed U extrusion with explicit planar triangulation."""
    outer, inner = data["outer_half_width"], data["inner_half_width"]
    top, soffit = data["outer_top"], data["inner_top"]
    outline = [(-outer, 0), (-inner, 0), (-inner, soffit), (inner, soffit),
               (inner, 0), (outer, 0), (outer, top), (-outer, top)]
    polygon = [Vector((x, y, 0)) for x, y in outline]
    triangles = tessellate_polygon([polygon])
    index = {tuple(point): i for i, point in enumerate(polygon)}
    n = len(outline)
    vertices = [xyz((x, y, z)) for z in data["z"] for x, y in outline]
    faces = []
    for triangle in triangles:
        ids = [point if isinstance(point, int) else index[tuple(point)] for point in triangle]
        faces.append(tuple(reversed(ids)))
        faces.append(tuple(i + n for i in ids))
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(mat)
    if data["bevel_m"]:
        bevel = obj.modifiers.new("Small architectural bevel", "BEVEL")
        bevel.width = data["bevel_m"]
        bevel.segments = 1
        bevel.limit_method = "ANGLE"
        bevel.harden_normals = True
    normal = obj.modifiers.new("Weighted flat architectural faces", "WEIGHTED_NORMAL")
    normal.keep_sharp = True
    obj["part_id"] = name
    return obj


def build():
    data = json.loads(SPEC.read_text(encoding="utf-8"))
    root = group("dock_module_root")
    root["asset_id"] = "dock-module"
    root["reference_id"] = "R07"
    root["role"] = "standard_retail_open_gate"
    root["clear_width_m"], root["clear_height_m"] = 4.0, 4.5
    root["geometry_authority"] = "L04 OUT_W_RETAIL / exact accepted L11 collision union"
    root["reference_adaptation"] = "R07 layered architecture adapted to accepted0.25m wallband; no layout enlargement"
    root["dimension_spec_sha256"] = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    steel = material("V3_Dock_PetrolSteel", "#2E7376", .85)
    tan = material("V3_Dock_TanReveal", "#C99A60", .85)
    charcoal = material("V3_Dock_Charcoal", "#263238", .88)
    rubber = material("V3_Dock_Bumper", "#202B30", .92)
    safety = material("V3_Dock_SafetyTan", "#E3B85B", .85)
    u_profile("structural_U", data["steel_U"], steel, root)
    u_profile("stepped_tan_reveal_U", data["tan_reveal_U"], tan, root)
    for sign, side in ((-1, "L"), (1, "R")):
        foot = data["foot_each"]
        box("ground_foot_" + side, (sign * foot["centre_abs_x"], .08, .125), foot["size"], charcoal, root, .006)
        bumper = data["bumper_each"]
        for face, key in (("outside", "outside_z"), ("inside", "inside_z")):
            z0, z1 = bumper[key]
            box("bumper_" + side + "_" + face,
                (sign * bumper["centre_abs_x"], sum(bumper["y"]) / 2, (z0 + z1) / 2),
                (bumper["width"], bumper["y"][1] - bumper["y"][0], z1 - z0), rubber, root, .004)
            band = data["safety_band_each"]
            z0, z1 = band[key]
            for number, y in enumerate(band["centres_y"]):
                box("safety_band_" + side + "_" + face + "_" + str(number),
                    (sign * band["centre_abs_x"], y, (z0 + z1) / 2),
                    (band["width"], band["height"], z1 - z0), safety, root, .002)
    panel = data["header_panel_each"]
    for face, key in (("outside", "outside_z"), ("inside", "inside_z")):
        z0, z1 = panel[key]
        box("header_cover_" + face, (0, sum(panel["y"]) / 2, (z0 + z1) / 2),
            (panel["width"], panel["y"][1] - panel["y"][0], z1 - z0), charcoal, root, .002)
    for name, point in data["anchors"].items():
        anchor(name, point, root)
    return root


def save_source(iteration):
    reset()
    root = build()
    STAGE.mkdir(parents=True, exist_ok=True)
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    shutil.copy2(SOURCE, STAGE / ("iteration-" + iteration + ".blend"))
    graph = bpy.context.evaluated_depsgraph_get()
    points, count = [], 0
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(runtime_xyz(evaluated.matrix_world @ v.co) for v in mesh.vertices)
        mesh.calc_loop_triangles()
        count += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    bounds = {"min": [min(p[i] for p in points) for i in range(3)],
              "max": [max(p[i] for p in points) for i in range(3)]}
    report = {"asset_id": "dock-module", "iteration": iteration,
              "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "bounds_runtime": bounds, "evaluated_triangles": count,
              "source_meshes": sum(o.type == "MESH" for o in root.children_recursive),
              "glb_exported": False}
    (STAGE / ("iteration-" + iteration + ".source.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("DOCK_SOURCE " + json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", default="01")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.export:
        accepted_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        report = finish("dock-module", bpy.data.objects["dock_module_root"])
        report["accepted_source_before_export_sha256"] = accepted_hash
        report["accepted_snapshot"] = "assets/v3/iterations/dock-module/P09.1/iteration-01.blend"
        report["source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        (SOURCE.parent / "dock-module.stats.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        if len(args.iteration) != 2 or not args.iteration.isdigit():
            raise ValueError("Expected two-digit iteration")
        save_source(args.iteration)
