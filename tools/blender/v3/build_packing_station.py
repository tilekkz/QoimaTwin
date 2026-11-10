"""P08.6 packing-station source and standalone GLB export.

Run through v3/run_build.py in fresh background Blender with two threads.
Accepted frame/devices and measured anchors remain editable in the source;
v3_common.finish batches only the exported hierarchy. Shared helpers and V2
files are never modified. Earlier iteration snapshots remain read-only.
"""
from pathlib import Path
import hashlib
import json
import math

import bpy
import bmesh

from v3_common import ROOT, VERSION, reset, material, group, box, anchor, xyz, runtime_xyz, finish


ASSET_ID = "packing-station"
STAGE = "P08.6"
PLAN = ROOT / "assets/v3/specs/packing-station.dimensions.json"
ITERATION = ROOT / "assets/v3/iterations/packing-station" / STAGE


def notched_shelf(part, mat, parent):
    """Two open post pockets avoid coplanar wood/post exterior faces."""
    low, high = part["bounds_local_xyz_m"]["min"], part["bounds_local_xyz_m"]["max"]
    x0, x1, z0, z1 = low[0], high[0], low[2], high[2]
    post_x = -.78 if x1 < 0 else .78
    left, right = post_x - .052, post_x + .052
    rear, front = -.278, .278
    profile = [(x0, z0), (left, z0), (left, rear), (right, rear),
               (right, z0), (x1, z0), (x1, z1), (right, z1),
               (right, front), (left, front), (left, z1), (x0, z1)]
    count = len(profile)
    vertices = [xyz((x, y, z)) for y in (low[1], high[1]) for x, z in profile]
    faces = [tuple(range(count)), tuple(reversed(range(count, count * 2)))]
    faces += [(i, count + i, count + (i + 1) % count, (i + 1) % count)
              for i in range(count)]
    mesh = bpy.data.meshes.new(part["part_id"] + "__notched_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(part["part_id"], mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    mesh.materials.append(mat)
    bevel = obj.modifiers.new("Small crafted shelf edges", "BEVEL")
    bevel.width = .006
    bevel.segments = 1
    bevel.harden_normals = True
    normal = obj.modifiers.new("Weighted face normals", "WEIGHTED_NORMAL")
    normal.keep_sharp = True
    obj["join_detail"] = "2mm open post pockets, within approved board envelope"
    return obj


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
        "join_revision": "inset rail faces and notched lower boards",
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
        if part["part_id"].startswith("lower_shelf_"):
            obj = notched_shelf(part, mats[part["material"]], frame)
        else:
            # Overlap joins stay inside the post solids, not on their visible
            # coplanar outer faces. All trims stay within the approved bounds.
            if "side_rail" in part["part_id"]:
                size[0], size[2] = .08, .59
            if part["part_id"] == "front_low_cross_tie":
                size[0] = 1.49
            obj = box(part["part_id"], centre, size,
                      mats[part["material"]], frame, bevel=bevel)
        obj["part_id"] = part["part_id"]
        obj["role"] = "packing_frame_component"
        obj["dimension_bounds_json"] = json.dumps(bounds)
    return root


def device_box(name, low, high, mat, parent, host, bevel=.003):
    obj = box(name, [(low[k] + high[k]) / 2 for k in range(3)],
              [high[k] - low[k] for k in range(3)], mat, parent, bevel=bevel)
    obj["part_id"] = name
    obj["planned_part_id"] = host
    obj["role"] = "packing_device_component"
    return obj


def tape_roll(part, mat, parent):
    """Closed annular tube, with two open axial sides and no centre cap."""
    cx, cy, cz = part["centre_local_xyz_m"]
    count = 12
    outer = part["outer_radius_m"]
    # Circumscribe the inner polygon around the required clear-radius circle.
    inner = part["inner_radius_m"] / math.cos(math.pi / count)
    depth = part["axial_depth_m"]
    vertices = [xyz((x, cy + radius * math.cos(2 * math.pi * i / count),
                    cz + radius * math.sin(2 * math.pi * i / count)))
                for x in (cx - depth / 2, cx + depth / 2)
                for radius in (outer, inner) for i in range(count)]
    faces = []
    for i in range(count):
        n = (i + 1) % count
        faces += [(i, n, 2 * count + n, 2 * count + i),
                  (count + i, 3 * count + i, 3 * count + n, count + n),
                  (i, count + i, count + n, n),
                  (2 * count + i, 2 * count + n, 3 * count + n, 3 * count + i)]
    mesh = bpy.data.meshes.new("tape_ring__annular_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("tape_ring", mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    mesh.materials.append(mat)
    obj["part_id"] = "tape_ring"
    obj["planned_part_id"] = "tape_ring"
    obj["role"] = "open_annular_tape_roll"
    obj["minimum_inner_clear_radius_m"] = part["inner_radius_m"]
    mod = obj.modifiers.new("Small axial tape edge bevel", "BEVEL")
    mod.width, mod.segments, mod.limit_method, mod.angle_limit = .0015, 1, "ANGLE", .6
    mod.harden_normals = True
    return obj


def build():
    root = build_frame()
    root["role"] = "packing_station_interface_stage"
    spec = json.loads(PLAN.read_text(encoding="utf-8"))
    planned = {p["part_id"]: p for p in spec["parts"]}
    colors = spec["reference"]["palette"]
    mats = {k: bpy.data.materials.get("P08 | " + k) or
            material("P08 | " + k, v, roughness=.86) for k, v in colors.items()}
    mats["display"] = material("P08 | recessed display", "#B2CDCC", roughness=.86)
    mats["scan_lens"] = material("P08 | scanner lens", "#AC6651", roughness=.82)
    groups = {key: group(key + "__DEVICE", parent=root)
              for key in ("screen", "scanner", "printer", "tape")}

    def piece(name, low, high, mat, host, bevel=.003):
        return device_box(name, low, high, mats[mat],
                          groups[planned[host]["group"]], host, bevel)

    for name in ("screen_base", "screen_stem", "scanner_base", "scanner_post",
                 "printer_base", "tape_base", "tape_cutter_pedestal"):
        p = planned[name]
        b = p["bounds_local_xyz_m"]
        piece(name, b["min"], b["max"], p["material"], name)

    # Screen rear enclosure, four real bezel rails and recessed display volume.
    host = "screen_housing"
    piece("screen_rear_cover", [-.88, 1.10, -.35], [-.52, 1.40, -.325], "charcoal", host)
    for name, lo, hi in (
        ("screen_bezel_bottom", [-.88, 1.10, -.325], [-.52, 1.13, -.285]),
        ("screen_bezel_top", [-.88, 1.37, -.325], [-.52, 1.40, -.285]),
        ("screen_bezel_left", [-.88, 1.13, -.325], [-.85, 1.37, -.285]),
        ("screen_bezel_right", [-.55, 1.13, -.325], [-.52, 1.37, -.285])):
        piece(name, lo, hi, "charcoal", host, .002)
    piece("screen_recess", [-.85, 1.13, -.327], [-.55, 1.37, -.302], "display", host, .001)
    for name, lo, hi in (
        ("screen_status_block", [-.82, 1.27, -.304], [-.75, 1.34, -.297]),
        ("screen_row_1", [-.72, 1.30, -.304], [-.58, 1.32, -.297]),
        ("screen_row_2", [-.72, 1.24, -.304], [-.58, 1.26, -.297]),
        ("screen_footer", [-.82, 1.17, -.304], [-.58, 1.19, -.297])):
        piece(name, lo, hi, "offwhite", host, .0005)

    # Solid scanner head with a supported, recessed front aperture.
    host = "scanner_head"
    piece("scanner_back", [-.81, 1.10, .25], [-.57, 1.22, .378], "charcoal", host)
    for name, lo, hi in (
        ("scanner_frame_bottom", [-.81, 1.10, .378], [-.57, 1.125, .40]),
        ("scanner_frame_top", [-.81, 1.195, .378], [-.57, 1.22, .40]),
        ("scanner_frame_left", [-.81, 1.125, .378], [-.78, 1.195, .40]),
        ("scanner_frame_right", [-.60, 1.125, .378], [-.57, 1.195, .40])):
        piece(name, lo, hi, "charcoal", host, .0015)
    piece("scanner_recessed_lens", [-.78, 1.125, .376], [-.60, 1.195, .391], "scan_lens", host, .001)

    # Printer front is an actual mouth, not a coplanar dark decal on a box.
    host = "printer_housing"
    piece("printer_rear_case", [.52, .94, .10], [.70, 1.20, .31], "charcoal", host)
    for name, lo, hi in (
        ("printer_front_bottom", [.52, .94, .31], [.70, 1.00, .34]),
        ("printer_front_top", [.52, 1.05, .31], [.70, 1.20, .34]),
        ("printer_mouth_left", [.52, 1.00, .31], [.545, 1.05, .34]),
        ("printer_mouth_right", [.675, 1.00, .31], [.70, 1.05, .34])):
        piece(name, lo, hi, "charcoal", host, .0015)
    piece("printer_recess", [.545, 1.00, .308], [.675, 1.05, .315], "petrol", host, .001)
    piece("printer_inner_paper", [.55, 1.024, .314], [.65, 1.030, .34], "offwhite", host, .0005)
    piece("label_presenter", [.55, 1.024, .34], [.65, 1.030, .40], "offwhite", "label_presenter", .0005)
    tape_roll(planned["tape_ring"], mats["tan"], groups["tape"])
    measured_path = ROOT / "assets/v3/blender/packing-station.anchors.json"
    measured = json.loads(measured_path.read_text(encoding="utf-8"))
    if measured.get("asset_id") != ASSET_ID:
        raise ValueError("Expected the separately measured packing anchor manifest")
    root["anchor_manifest"] = str(measured_path.relative_to(ROOT)).replace("\\", "/")
    for item in measured["anchors"]:
        obj = anchor(item["anchor_id"], item["local_xyz_m"], root, role=item["role"])
        obj["anchor_authority"] = item["authority"]
        if item.get("initial_plan_local_xyz_m") is not None:
            obj["initial_plan_local_xyz"] = item["initial_plan_local_xyz_m"]
        if item.get("physical_part"):
            obj["physical_part"] = item["physical_part"]
        if item.get("normal_runtime"):
            obj["surface_normal_runtime"] = item["normal_runtime"]
        if item.get("normal"):
            obj["transport_facing_runtime"] = item["normal"]
        if item.get("facing"):
            obj["service_facing_runtime"] = item["facing"]
        if item.get("axis_runtime"):
            obj["axis_runtime"] = item["axis_runtime"]
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
                "planned_part_id": obj.get("planned_part_id", obj["part_id"]),
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
            "components": components,
            "anchors": {o["anchor_id"]: runtime_xyz(o.matrix_world.translation)
                        for o in root.children_recursive if o.get("anchor_id")},
            "final_asset": False, "glb_exported": False}


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
    print("P08_STAGE_SOURCE_READY " + json.dumps({k: report[k] for k in
          ["mesh_parts", "triangles", "dimensions_m", "source_sha256"]}))
    return report


if __name__ == "__main__":
    reset()
    root = build()
    root["role"] = "packing_station"
    root["final_asset"] = True
    finish(ASSET_ID, root)
