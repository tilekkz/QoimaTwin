"""One M08 PALLET_LOAD HU, exact C02 contents; task-background source first."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
import bmesh

from v3_common import ROOT, VERSION, reset, group, box, anchor, material, xyz, runtime_xyz, finish

ASSET_ID = "pallet-load"
PLAN = ROOT / "assets/v3/specs/pallet-load.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/pallet-load.blend"


def carton_body(name, centre, mats, parent):
    """Closed carton with material regions on shared faces, no label overlays."""
    xs = [-.18, .025, .105, .18]
    ys = [-.13, -.065, -.015, .13]
    zs = [-.14, .14]
    vertices = []; lookup = {}; faces = []; indices = []

    def face(points, mat=0):
        ids = []
        for point in points:
            key = tuple(point)
            if key not in lookup:
                lookup[key] = len(vertices); vertices.append(xyz(point))
            ids.append(lookup[key])
        faces.append(ids); indices.append(mat)

    for z in zs:
        for i in range(3):
            for j in range(3):
                face([(xs[i], ys[j], z), (xs[i+1], ys[j], z),
                      (xs[i+1], ys[j+1], z), (xs[i], ys[j+1], z)],
                     1 if i == j == 1 else 0)
    for x in [xs[0], xs[-1]]:
        for j in range(3):
            face([(x, ys[j], zs[0]), (x, ys[j+1], zs[0]),
                  (x, ys[j+1], zs[1]), (x, ys[j], zs[1])])
    for y in [ys[0], ys[-1]]:
        for i in range(3):
            face([(xs[i], y, zs[0]), (xs[i+1], y, zs[0]),
                  (xs[i+1], y, zs[1]), (xs[i], y, zs[1])],
                 2 if y == ys[-1] and i == 1 else 0)
    mesh = bpy.data.meshes.new(name + "__closed_carton")
    mesh.from_pydata(vertices, [], faces); mesh.update()
    for polygon, index in zip(mesh.polygons, indices): polygon.material_index = index
    for mat in [mats["carton"], mats["offwhite"], mats["wood"]]: mesh.materials.append(mat)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    obj.parent = parent; obj.location = xyz(centre)
    bevel = obj.modifiers.new("Contained carton edge folds", "BEVEL")
    bevel.width = .002; bevel.segments = 1; bevel.limit_method = "ANGLE"; bevel.harden_normals = True
    normal = obj.modifiers.new("Weighted planar carton normals", "WEIGHTED_NORMAL"); normal.keep_sharp = True
    return obj


def build(stage="initial"):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    for binding in [plan["source_C02"], plan["source_C08"], plan["reference"]]:
        if hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest() != binding["sha256"]:
            raise ValueError("Stale M08 source/reference binding: " + binding["path"])
    root = group("pallet-load__HU")
    for key, value in {"asset_id": ASSET_ID, "role": "cargo_handling_unit", "archetype_id": "PALLET_LOAD",
                       "reference_id": "M08_REF", "reference_sha256": plan["reference"]["sha256"],
                       "author_stage": "M08-" + stage, "origin": "floor_centre", "units_per_HU": 24,
                       "HU_count": 1, "contains_inventory": False, "prototype_contents_not_stock": True,
                       "declared_gross_mass_kg": 455., "mass_computed_from_mesh": False,
                       "operational_admission": False, "c02_source_sha256": plan["source_C02"]["sha256"],
                       "c08_source_sha256": plan["source_C08"]["sha256"],
                       "dimension_plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest()}.items(): root[key] = value
    mats = {name: material("PALLET_LOAD | " + name, color, roughness=.86) for name, color in plan["palette"].items()}
    for part in plan["parts"]:
        b = part["bounds_local_xyz_m"]; lo, hi = b["min"], b["max"]
        obj = box(part["part_id"], [(lo[k]+hi[k])/2 for k in range(3)],
                  [hi[k]-lo[k] for k in range(3)], mats[part["material"]], root, bevel=part["bevel_m"])
        obj["part_id"] = part["part_id"]; obj["role"] = "integral_HU_packaging"
        obj["planned_bounds_json"] = json.dumps(b)
    for unit in plan["unit_positions"]:
        b = unit["bounds_local_xyz_m"]; lo, hi = b["min"], b["max"]
        centre = [(lo[k]+hi[k])/2 for k in range(3)]; ordinal = unit["unit_ordinal"]
        frame = group(f"unit__{ordinal:03d}", root, centre)
        frame["role"] = "HU_content_unit_frame"; frame["unit_ordinal"] = ordinal
        frame["packaged_dimensions_xyz_m"] = [.36, .26, .28]
        frame["canonical_bounds_HU_json"] = json.dumps(b); frame["prototype_contents_not_stock"] = True
        # Sibling bodies batch efficiently while explicit per-unit frames survive.
        obj = carton_body(f"unit_body_{ordinal:03d}", centre, mats, root)
        obj["part_id"] = obj.name; obj["role"] = "packaged_carton_contents"
        obj["unit_ordinal"] = ordinal; obj["content_frame_id"] = frame.name
        obj["canonical_bounds_HU_json"] = json.dumps(b)
    for item in plan["anchors"]:
        obj = anchor(item["anchor_id"], item["local_xyz_m"], root, role=item["role"])
        obj["mass_computed_from_mesh"] = False
    bpy.context.view_layer.update()
    return root


def metrics(root):
    graph=bpy.context.evaluated_depsgraph_get();parts=[];points=[];materials=set();triangles=0
    for obj in root.children_recursive:
        if obj.type!="MESH":continue
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles();vertices=[runtime_xyz(evaluated.matrix_world@v.co) for v in mesh.vertices]
            normals=[runtime_xyz((evaluated.matrix_world.to_3x3().inverted().transposed()@n.vector).normalized()) for n in mesh.corner_normals]
            payload={"vertices":[[round(c,8) for c in p] for p in vertices],
                     "normals":[[round(c,8) for c in p] for p in normals],
                     "triangles":[(list(t.vertices),t.material_index) for t in mesh.loop_triangles],
                     "materials":[m.name for m in obj.data.materials]}
            parts.append({"part_id":obj["part_id"],"triangles":len(mesh.loop_triangles),
                          "bounds_runtime":{"min":[min(p[k] for p in vertices) for k in range(3)],"max":[max(p[k] for p in vertices) for k in range(3)]},
                          "modifiers":[{"name":m.name,"type":m.type} for m in obj.modifiers],
                          "signature":hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
                          "geometry_signature":hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k!="materials"},sort_keys=True).encode()).hexdigest()})
            points+=vertices;triangles+=len(mesh.loop_triangles);materials.update(m.name for m in obj.data.materials)
        finally:evaluated.to_mesh_clear()
    parts.sort(key=lambda p:p["part_id"])
    bounds={"min":[min(p[k] for p in points) for k in range(3)],"max":[max(p[k] for p in points) for k in range(3)]}
    return {"asset_id":ASSET_ID,"namespace":"v3","version":VERSION,"mesh_parts":len(parts),"triangles":triangles,
            "materials":sorted(materials),"bounds_runtime":bounds,"dimensions_xyz_m":[bounds["max"][k]-bounds["min"][k] for k in range(3)],
            "components":parts,"anchors":{o["anchor_id"]:runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get("anchor_id")}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--snapshot",default="initial");parser.add_argument("--export",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*",args.snapshot):raise ValueError("Use a simple new checkpoint name")
    directory=ROOT/"assets/v3/iterations/pallet-load"/args.snapshot
    if directory.exists():raise FileExistsError("Preserve existing checkpoint; choose another --snapshot")
    directory.mkdir(parents=True);reset();root=build(args.snapshot);before=metrics(root)
    if before["mesh_parts"]!=84 or before["triangles"]>10000 or len(before["anchors"])!=2:raise ValueError("PALLET_LOAD budget/anchor mismatch")
    SOURCE.parent.mkdir(parents=True,exist_ok=True);bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    if args.export:
        finish(ASSET_ID,root);bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        reopened=next(o for o in bpy.data.objects if o.get("asset_id")==ASSET_ID and o.parent is None)
        if metrics(reopened)!=before:raise ValueError("Editable source changed after finish/reopen")
    snapshot=directory/"pallet-load.blend";snapshot.write_bytes(SOURCE.read_bytes())
    before.update(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),dimension_plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),glb_exported=args.export)
    (directory/"source-metrics.json").write_text(json.dumps(before,indent=2)+"\n",encoding="utf-8")
    (directory/"dimension-plan.json").write_bytes(PLAN.read_bytes())
    print("M08_SOURCE_READY "+json.dumps({k:before[k] for k in ["mesh_parts","triangles","dimensions_xyz_m","source_sha256","glb_exported"]}))


if __name__=="__main__":main()
