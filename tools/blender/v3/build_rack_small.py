"""M01 SMALL source-first build; background Blender, two threads, no live scene.

Default saves a unique source checkpoint. Pass --export only after source-view
review; v3_common.finish retains editable parts/modifiers before material batches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
import bmesh

from v3_common import ROOT, VERSION, reset, group, box, anchor, material, xyz, runtime_xyz, finish

ASSET_ID = "rack-small"
PLAN = ROOT / "assets/v3/specs/rack-small.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/rack-small.blend"


def recessed_deck(part, mat, parent):
    """Closed extruded deck with actual recess, no internal split wood faces."""
    profile = part["profile_yz_m"]
    low, high = part["bounds_local_xyz_m"]["min"][0], part["bounds_local_xyz_m"]["max"][0]
    count = len(profile)
    verts = [xyz((x, y, z)) for x in (low, high) for y, z in profile]
    faces = [tuple(range(count)), tuple(reversed(range(count, 2 * count)))]
    faces += [(i, count + i, count + (i + 1) % count, (i + 1) % count) for i in range(count)]
    mesh = bpy.data.meshes.new(part["part_id"] + "__recessed_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    weights = mesh.attributes.new(name="bevel_weight_edge", type="FLOAT", domain="EDGE")
    for edge in mesh.edges:
        a, b = [runtime_xyz(mesh.vertices[i].co) for i in edge.vertices]
        concave_long_edge = abs(a[0] - b[0]) > 1 and any(
            abs(a[1] - y) < 1e-6 and abs(a[2] - z) < 1e-6 for y, z in part["skip_concave_bevel_yz_m"])
        weights.data[edge.index].value = 0 if concave_long_edge else 1
    obj = bpy.data.objects.new(part["part_id"], mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent;mesh.materials.append(mat)
    bevel = obj.modifiers.new("Small convex deck bevels", "BEVEL")
    bevel.width = part["bevel_m"];bevel.segments = 1
    bevel.limit_method = "WEIGHT";bevel.harden_normals = True
    normals = obj.modifiers.new("Weighted deck normals", "WEIGHTED_NORMAL")
    normals.keep_sharp = True
    return obj


def build(stage="initial"):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    source_contract = ROOT / plan["source_contract"]["path"]
    if hashlib.sha256(source_contract.read_bytes()).hexdigest() != plan["source_contract"]["sha256"]:
        raise ValueError("C04 source changed; review dimension plan before rebuilding")
    root = group("rack-small__MODULE")
    for key, value in {
        "asset_id": ASSET_ID, "role": "storage_module", "storage_family": "SMALL",
        "reference_id": "R13.1", "reference_sha256": plan["reference"]["sha256"],
        "author_stage": "M01-" + stage, "origin": "floor_centre", "contains_inventory": False,
        "usable_bays": 5, "usable_levels": 2, "operational_admission": False,
        "dimension_plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "c04_source_sha256": plan["source_contract"]["sha256"],
        "usable_envelopes_json": json.dumps(plan["anchors"]),
        "rear_strip_role": "Visible structural rear deck only; no additional address or deeper usable bin",
        "floor_role": "Recessed petrol top exactly on supportY; no wood top underneath",
    }.items():
        root[key] = value
    mats = {key: material("SMALL | " + key, color, roughness=.86)
            for key, color in plan["palette"].items()}
    for part in plan["parts"]:
        bounds = part["bounds_local_xyz_m"]
        lo, hi = bounds["min"], bounds["max"]
        if part.get("kind") == "recessed_deck":
            obj = recessed_deck(part, mats[part["material"]], root)
        else:
            obj = box(part["part_id"], [(lo[k] + hi[k]) / 2 for k in range(3)],
                      [hi[k] - lo[k] for k in range(3)], mats[part["material"]], root,
                      bevel=part["bevel_m"])
        obj["part_id"] = part["part_id"]
        obj["role"] = "empty_storage_fixture_component"
        obj["planned_bounds_json"] = json.dumps(bounds)
    for item in plan["anchors"]:
        obj = anchor(item["anchor_id"], item["local_xyz_m"], root,
                     role="storage_slot_bottom_centre")
        obj["level"] = item["level"]
        obj["bay"] = item["bay"]
        obj["usable_dimensions_xyz_m"] = item["usable_dimensions_xyz_m"]
        obj["usable_bounds_module_json"] = json.dumps(item["usable_bounds_module_local"])
        obj["prototype_source_slot_id"] = item["prototype_source_slot_id"]
        obj["not_inventory_instance_id"] = True
    bpy.context.view_layer.update()
    return root


def metrics(root):
    graph = bpy.context.evaluated_depsgraph_get()
    components, points, triangles, materials = [], [], 0, set()
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            verts = [runtime_xyz(evaluated.matrix_world @ v.co) for v in mesh.vertices]
            normals = [runtime_xyz((evaluated.matrix_world.to_3x3().inverted().transposed() @ n.vector).normalized()) for n in mesh.corner_normals]
            payload = {"vertices": [[round(v, 8) for v in p] for p in verts],
                       "normals": [[round(v, 8) for v in p] for p in normals],
                       "triangles": [(list(t.vertices), t.material_index) for t in mesh.loop_triangles],
                       "materials": [m.name for m in obj.data.materials]}
            components.append({"part_id": obj["part_id"], "triangles": len(mesh.loop_triangles),
                               "bounds_runtime": {"min": [min(v[k] for v in verts) for k in range(3)],
                                                  "max": [max(v[k] for v in verts) for k in range(3)]},
                               "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
                               "signature": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()})
            points += verts
            triangles += len(mesh.loop_triangles)
            materials.update(m.name for m in obj.data.materials)
        finally:
            evaluated.to_mesh_clear()
    components.sort(key=lambda item: item["part_id"])
    bounds = {"min": [min(p[k] for p in points) for k in range(3)],
              "max": [max(p[k] for p in points) for k in range(3)]}
    return {"asset_id": ASSET_ID, "namespace": "v3", "version": VERSION,
            "method": "Actual evaluated world vertices/normals in runtime XYZ metres",
            "mesh_parts": len(components), "triangles": triangles, "materials": sorted(materials),
            "bounds_runtime": bounds, "dimensions_xyz_m": [bounds["max"][k] - bounds["min"][k] for k in range(3)],
            "components": components,
            "anchors": {obj["anchor_id"]: runtime_xyz(obj.matrix_world.translation)
                        for obj in root.children_recursive if obj.get("anchor_id")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="initial")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.snapshot):
        raise ValueError("Use a simple task-local snapshot name")
    directory = ROOT / "assets/v3/iterations/rack-small" / args.snapshot
    if directory.exists():
        raise FileExistsError("Preserve existing checkpoint; choose a new --snapshot")
    directory.mkdir(parents=True)
    reset()
    root = build(args.snapshot)
    before = metrics(root)
    expected_parts = len(json.loads(PLAN.read_text(encoding="utf-8"))["parts"])
    if before["mesh_parts"] != expected_parts or before["triangles"] > 3000 or len(before["anchors"]) != 10:
        raise ValueError("Unexpected SMALL component, triangle or anchor budget")
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    if args.export:
        finish(ASSET_ID, root)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        reopened = next(o for o in bpy.data.objects if o.get("asset_id") == ASSET_ID and o.parent is None)
        if metrics(reopened) != before:
            raise ValueError("Editable source differs after common export/reopen")
    snapshot = directory / "rack-small.blend"
    snapshot.write_bytes(SOURCE.read_bytes())
    before.update(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  dimension_plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),
                  source=str(SOURCE), snapshot=str(snapshot), glb_exported=args.export)
    (directory / "source-metrics.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    print("M01_SOURCE_READY " + json.dumps({key: before[key] for key in
          ["mesh_parts", "triangles", "dimensions_xyz_m", "source_sha256", "glb_exported"]}))


if __name__ == "__main__":
    main()
