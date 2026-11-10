"""M05 source-first empty FLEX module; use task-background Blender only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
import bmesh

from v3_common import ROOT, VERSION, reset, group, box, anchor, material, xyz, runtime_xyz, finish

ASSET_ID = "flex-bay"
PLAN = ROOT / "assets/v3/specs/flex-bay.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/flex-bay.blend"


def notched_extrusion(part, mat, parent):
    """One closed broad base/deck with two real rear-post corner cutouts."""
    profile = part["profile_xz_m"]
    low, high = part["bounds_local_xyz_m"]["min"][1], part["bounds_local_xyz_m"]["max"][1]
    count = len(profile)
    vertices = [xyz((x, y, z)) for y in (low, high) for x, z in profile]
    faces = [tuple(range(count)), tuple(reversed(range(count, 2 * count)))]
    faces += [(i, count + i, count + (i + 1) % count, (i + 1) % count) for i in range(count)]
    mesh = bpy.data.meshes.new(part["part_id"] + "__notched_mesh")
    mesh.from_pydata(vertices, [], faces);mesh.update()
    bm = bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    weights = mesh.attributes.new(name="bevel_weight_edge", type="FLOAT", domain="EDGE")
    for edge in mesh.edges:
        a, b = [runtime_xyz(mesh.vertices[i].co) for i in edge.vertices]
        concave_vertical = abs(a[1]-b[1]) > .015 and any(
            abs(a[0]-x)<1e-6 and abs(a[2]-z)<1e-6 for x,z in part["skip_concave_bevel_xz_m"])
        weights.data[edge.index].value = 0 if concave_vertical else 1
    obj = bpy.data.objects.new(part["part_id"], mesh)
    bpy.context.collection.objects.link(obj);obj.parent = parent;mesh.materials.append(mat)
    bevel = obj.modifiers.new("Small contained convex bevels", "BEVEL")
    bevel.width = part["bevel_m"];bevel.segments = 1;bevel.limit_method = "WEIGHT";bevel.harden_normals = True
    normals = obj.modifiers.new("Weighted planar normals", "WEIGHTED_NORMAL");normals.keep_sharp = True
    return obj


def build(stage="initial"):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if hashlib.sha256((ROOT/plan["source_contract"]["path"]).read_bytes()).hexdigest() != plan["source_contract"]["sha256"]:
        raise ValueError("Current C04 source differs from reviewed FLEX dimension plan")
    root = group("flex-bay__MODULE")
    for key,value in {"asset_id":ASSET_ID,"role":"storage_module","storage_family":"FLEX",
                      "reference_id":"R13.5","reference_sha256":plan["reference"]["sha256"],
                      "author_stage":"M05-"+stage,"origin":"floor_centre","contains_inventory":False,
                      "usable_bays":1,"usable_levels":1,"operational_admission":False,
                      "open_front_and_sides":True,"rear_uprights":2,
                      "dimension_plan_sha256":hashlib.sha256(PLAN.read_bytes()).hexdigest(),
                      "c04_source_sha256":plan["source_contract"]["sha256"]}.items():root[key]=value
    mats={name:material("FLEX | "+name,color,roughness=.86) for name,color in plan["palette"].items()}
    for part in plan["parts"]:
        b=part["bounds_local_xyz_m"];lo,hi=b["min"],b["max"]
        if part["kind"]=="notched_extrusion":obj=notched_extrusion(part,mats[part["material"]],root)
        else:obj=box(part["part_id"],[(lo[k]+hi[k])/2 for k in range(3)],
                     [hi[k]-lo[k] for k in range(3)],mats[part["material"]],root,bevel=part["bevel_m"])
        obj["part_id"]=part["part_id"];obj["role"]="empty_storage_fixture_component"
        obj["planned_bounds_json"]=json.dumps(b)
    item=plan["anchors"][0]
    obj=anchor(item["anchor_id"],item["local_xyz_m"],root,role="storage_slot_bottom_centre")
    obj["usable_dimensions_xyz_m"]=item["usable_dimensions_xyz_m"]
    obj["usable_bounds_module_json"]=json.dumps(item["usable_bounds_module_local"])
    obj["prototype_source_slot_id"]=item["prototype_source_slot_id"]
    obj["not_inventory_instance_id"]=True
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
                          "signature":hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()})
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
    directory=ROOT/"assets/v3/iterations/flex-bay"/args.snapshot
    if directory.exists():raise FileExistsError("Preserve existing checkpoint; choose another --snapshot")
    directory.mkdir(parents=True);reset();root=build(args.snapshot);before=metrics(root)
    if before["mesh_parts"]!=15 or before["triangles"]>1200 or len(before["anchors"])!=1:raise ValueError("FLEX budget/anchor mismatch")
    SOURCE.parent.mkdir(parents=True,exist_ok=True);bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    if args.export:
        finish(ASSET_ID,root);bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        reopened=next(o for o in bpy.data.objects if o.get("asset_id")==ASSET_ID and o.parent is None)
        if metrics(reopened)!=before:raise ValueError("Editable source changed after finish/reopen")
    snapshot=directory/"flex-bay.blend";snapshot.write_bytes(SOURCE.read_bytes())
    before.update(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),dimension_plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),glb_exported=args.export)
    (directory/"source-metrics.json").write_text(json.dumps(before,indent=2)+"\n",encoding="utf-8")
    (directory/"dimension-plan.json").write_bytes(PLAN.read_bytes())
    print("M05_SOURCE_READY "+json.dumps({k:before[k] for k in ["mesh_parts","triangles","dimensions_xyz_m","source_sha256","glb_exported"]}))


if __name__=="__main__":main()
