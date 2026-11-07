"""P09.2 freight family: rebuild exact7m/6m variants, no global scaling.

The accepted dock construction is imported read-only. Source quality iteration
and final export remain separate commands; neither variant overwrites the dock.
"""
import argparse
import hashlib
import json
import shutil
import sys

import bpy

from v3_common import ROOT, reset, group, material, box, anchor, finish, runtime_xyz
from build_dock_module import u_profile

SPEC = ROOT / "assets/v3/specs/large-gate.dimensions.json"


def build(asset_id):
    family = json.loads(SPEC.read_text(encoding="utf-8"))
    variant = family["variants"][asset_id]
    data = variant["construction"]
    root = group(variant["root_name"])
    root["asset_id"], root["port_id"] = asset_id, variant["port_id"]
    root["reference_id"], root["role"] = "R07", "large_freight_open_gate"
    root["clear_width_m"], root["clear_height_m"] = variant["clear_width_m"], 4.5
    root["dimension_spec_sha256"] = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    root["geometry_authority"] = "L05/L11 exact accepted port wallband; not operational forklift admission"
    root["forward_description"] = "+Z inward; outbound motion may be opposite to module forward"
    root["parameter_method"] = "rebuilt coordinates; unit root scale, fixed part thickness"
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
    for name, point in variant["anchors"].items():
        anchor(name, point, root)
    return root


def source_stage(asset_id, iteration):
    reset()
    root = build(asset_id)
    source = ROOT / "assets/v3/blender" / (asset_id + ".blend")
    stage = ROOT / "assets/v3/iterations" / asset_id / "P09.2"
    stage.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.update()
    assert tuple(root.scale) == (1, 1, 1)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    shutil.copy2(source, stage / ("iteration-" + iteration + ".blend"))
    graph = bpy.context.evaluated_depsgraph_get()
    points, triangles = [], 0
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(runtime_xyz(evaluated.matrix_world @ v.co) for v in mesh.vertices)
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    report = {"asset_id": asset_id, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "bounds_runtime": {"min": [min(p[i] for p in points) for i in range(3)],
                                 "max": [max(p[i] for p in points) for i in range(3)]},
              "source_meshes": 18, "evaluated_triangles": triangles, "root_scale": list(root.scale),
              "glb_exported": False}
    (stage / ("iteration-" + iteration + ".source.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FREIGHT_SOURCE " + json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=("large-gate", "large-gate-b2b"), default="large-gate")
    parser.add_argument("--iteration", default="01")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.export:
        variant = json.loads(SPEC.read_text(encoding="utf-8"))["variants"][args.asset]
        source = ROOT / "assets/v3/blender" / (args.asset + ".blend")
        accepted_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        bpy.ops.wm.open_mainfile(filepath=str(source))
        report = finish(args.asset, bpy.data.objects[variant["root_name"]])
        report["accepted_source_before_export_sha256"] = accepted_hash
        report["accepted_snapshot"] = "assets/v3/iterations/" + args.asset + "/P09.2/iteration-" + args.iteration + ".blend"
        report["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        (source.parent / (args.asset + ".stats.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        if len(args.iteration) != 2 or not args.iteration.isdigit():
            raise ValueError("Expected two-digit iteration")
        source_stage(args.asset, args.iteration)
