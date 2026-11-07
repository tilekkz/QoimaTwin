"""P09.3 ordinary-scale shell, root-approved NE cutaway, no warehouse contents.

Source build and accepted-source export are separate. Old gate assets/helpers
remain read-only; six profiles are rebuilt to exact port dimensions.
"""
import argparse
import hashlib
import json
import shutil
import sys

import bpy

from v3_common import ROOT, reset, group, box, material, anchor, finish, xyz, runtime_xyz
from build_dock_module import u_profile

SPEC = ROOT / "assets/v3/specs/environment-shell.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/environment-shell.blend"
STAGE = ROOT / "assets/v3/iterations/environment-shell/P09.3"


def tag(obj, category, display_only=False):
    obj["shell_component_class"] = category
    obj["display_only"] = display_only
    return obj


def bounded_box(part, mat, parent, category, bevel=.008, display_only=False):
    b = part["bounds"]
    centre = [(b["min"][i]+b["max"][i])/2 for i in range(3)]
    size = [b["max"][i]-b["min"][i] for i in range(3)]
    return tag(box(part["name"], centre, size, mat, parent, bevel), category, display_only)


def wall_solid(part, mats, parent):
    """One closed finite wall prism, integrated face bands without overlays."""
    b = part["bounds"]
    x0, y0, z0 = b["min"]
    x1, y1, z1 = b["max"]
    levels = sorted({y0, y1} | {v for v in (.9, y1-.12) if y0 < v < y1})
    vertices = [xyz((x, y, z)) for y in levels for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
    faces = [(0, 1, 2, 3), tuple(reversed(range((len(levels)-1)*4, len(levels)*4)))]
    material_indices = [0 if y0 < .9 else 1, 2]
    for j in range(len(levels)-1):
        mid = (levels[j]+levels[j+1])/2
        slot = 0 if mid < .9 else 2 if mid >= y1-.12 else 1
        for i in range(4):
            faces.append((j*4+i, (j+1)*4+i, (j+1)*4+(i+1)%4, j*4+(i+1)%4))
            material_indices.append(slot)
    mesh = bpy.data.meshes.new(part["name"]+"_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(part["name"], mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    for mat in (mats["petrol"], mats["wall"], mats["charcoal"]): mesh.materials.append(mat)
    for polygon, index in zip(mesh.polygons, material_indices): polygon.material_index = index
    bevel = obj.modifiers.new("Small wall edge", "BEVEL")
    bevel.width, bevel.segments, bevel.limit_method, bevel.harden_normals = .008, 1, "ANGLE", True
    normal = obj.modifiers.new("Flat architectural face normals", "WEIGHTED_NORMAL")
    normal.keep_sharp = True
    return tag(obj, "wall")


def port_frame(gate, parent, mats):
    pid, data = gate["port_id"], gate["construction"]
    root = group("GATE__"+pid, parent, gate["position"])
    root.rotation_euler.z = gate["yaw_rad"]
    root["port_id"] = pid
    root["clear_width_m"], root["clear_height_m"] = gate["clear_width_m"], gate["clear_height_m"]
    root["forward_description"] = "+Zinward; physical yaw independent of traffic direction"
    prefix = pid+"__"
    tag(u_profile(prefix+"structural_U", data["steel_U"], mats["gate_steel"], root), "gate_frame")
    tag(u_profile(prefix+"tan_reveal_U", data["tan_reveal_U"], mats["gate_tan"], root), "gate_frame")
    for sign, side in ((-1, "L"), (1, "R")):
        foot = data["foot_each"]
        tag(box(prefix+"foot_"+side, (sign*foot["centre_abs_x"], .08, .125), foot["size"], mats["gate_charcoal"], root, .006), "gate_frame")
        bumper = data["bumper_each"]
        for face, key in (("outside", "outside_z"), ("inside", "inside_z")):
            z0, z1 = bumper[key]
            tag(box(prefix+"bumper_"+side+"_"+face, (sign*bumper["centre_abs_x"], sum(bumper["y"])/2, (z0+z1)/2),
                    (bumper["width"], bumper["y"][1]-bumper["y"][0], z1-z0), mats["gate_rubber"], root, .004), "gate_frame")
            band = data["safety_band_each"]
            z0, z1 = band[key]
            for number, y in enumerate(band["centres_y"]):
                tag(box(prefix+"safety_"+side+"_"+face+str(number), (sign*band["centre_abs_x"], y, (z0+z1)/2),
                        (band["width"], band["height"], z1-z0), mats["gate_safety"], root, .002), "gate_frame")
    panel = data["header_panel_each"]
    for face, key in (("outside", "outside_z"), ("inside", "inside_z")):
        z0, z1 = panel[key]
        tag(box(prefix+"header_cover_"+face, (0, sum(panel["y"])/2, (z0+z1)/2),
                (panel["width"], panel["y"][1]-panel["y"][0], z1-z0), mats["gate_charcoal"], root, .002), "gate_frame")
    half = gate["clear_width_m"]/2
    for suffix, point in (("floor", (0, 0, 0)), ("clear_left", (-half, 0, .125)),
                          ("clear_right", (half, 0, .125)), ("clear_top", (0, gate["clear_height_m"], .125)),
                          ("wall_inside", (0, 0, .25))):
        anchor("PORT__"+pid+"__"+suffix, point, root)
    return root


def build():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    root = group("environment_shell_root")
    root["asset_id"], root["reference_id"] = "environment-shell", "R07/R08"
    root["role"] = "empty_architectural_cutaway_shell"
    root["operational_floor_bounds_json"] = json.dumps(spec["operational_floor_bounds"])
    root["ceiling_limit_y_m"] = 8
    root["display_plinth_bounds_json"] = json.dumps(spec["display_plinth"]["bounds"])
    root["cutaway_json"] = json.dumps(spec["cutaway"])
    root["dimension_spec_sha256"] = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    root["scope"] = "No racks/stock/people/vehicles/roof; not final scene density/lighting approval"
    mats = {name: material("V3_Shell_"+name, color, .88) for name, color in spec["materials"].items()}
    mats.update(gate_steel=material("V3_Dock_PetrolSteel", "#2E7376", .85),
                gate_tan=material("V3_Dock_TanReveal", "#C99A60", .85),
                gate_charcoal=material("V3_Dock_Charcoal", "#263238", .88),
                gate_rubber=material("V3_Dock_Bumper", "#202B30", .92),
                gate_safety=material("V3_Dock_SafetyTan", "#E3B85B", .85))
    floor = group("FLOOR_SUPPORTS", root)
    bounded_box(spec["floor_slab"], mats["floor"], floor, "floor_support", 0)
    bounded_box(spec["display_plinth"], mats["plinth"], floor, "display_plinth", .10, True)
    walls = group("ARCHITECTURE__WALLS", root)
    for part in spec["walls"]: wall_solid(part, mats, walls)
    columns = group("ARCHITECTURE__COLUMNS", root)
    for col in spec["columns"]:
        for part in col["pieces"]:
            shaft = part["name"].endswith("shaft")
            bounded_box(part, mats["petrol"] if shaft else mats["charcoal"], columns, "column", .016 if shaft else .012)
    windows = group("ARCHITECTURE__OPAQUE_WINDOWS", root)
    for window in spec["windows"]:
        bounded_box(window["backing"], mats["charcoal"], windows, "opaque_window", .006)
        for part in window["panes"]: bounded_box(part, mats["opaque_pane"], windows, "opaque_window", .003)
    for gate in spec["gates"]: port_frame(gate, root, mats)
    for name, point in (("anchor_floor_SW", (0, 0, 0)), ("anchor_floor_SE", (144, 0, 0)),
                        ("anchor_floor_NW", (0, 0, 72)), ("anchor_floor_NE", (144, 0, 72)),
                        ("anchor_ceiling_8m", (72, 8, 36))): anchor(name, point, root)
    return root


def save_source(iteration):
    reset()
    root = build()
    bpy.context.view_layer.update()
    STAGE.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    shutil.copy2(SOURCE, STAGE/("iteration-"+iteration+".blend"))
    graph = bpy.context.evaluated_depsgraph_get()
    components, points, triangles = {}, [], 0
    for obj in root.children_recursive:
        if obj.type != "MESH": continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        vertices = [runtime_xyz(evaluated.matrix_world@v.co) for v in mesh.vertices]
        mesh.calc_loop_triangles()
        components[obj.name] = {"bounds_runtime": {"min": [min(p[i] for p in vertices) for i in range(3)],
                                                  "max": [max(p[i] for p in vertices) for i in range(3)]},
                                "category": obj.get("shell_component_class"), "display_only": bool(obj.get("display_only")),
                                "parent": obj.parent.name, "triangles": len(mesh.loop_triangles), "modifiers": len(obj.modifiers)}
        points.extend(vertices)
        triangles += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    report = {"asset_id": "environment-shell", "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "source_meshes": len(components), "evaluated_triangles": triangles,
              "bounds_runtime": {"min": [min(p[i] for p in points) for i in range(3)], "max": [max(p[i] for p in points) for i in range(3)]},
              "root_scale": list(root.scale), "components": components, "glb_exported": False}
    for name in ("source-geometry.json", "iteration-"+iteration+".source.json"):
        (STAGE/name).write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print("SHELL_SOURCE "+json.dumps({k: v for k, v in report.items() if k != "components"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", default="01")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.export:
        accepted_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        report = finish("environment-shell", bpy.data.objects["environment_shell_root"])
        report["accepted_source_before_export_sha256"] = accepted_hash
        report["source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        report["accepted_snapshot"] = "assets/v3/iterations/environment-shell/P09.3/iteration-"+args.iteration+".blend"
        (SOURCE.parent/"environment-shell.stats.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    else:
        if len(args.iteration) != 2 or not args.iteration.isdigit(): raise ValueError("Expected two-digit iteration")
        save_source(args.iteration)
