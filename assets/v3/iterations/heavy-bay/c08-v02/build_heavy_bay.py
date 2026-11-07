"""M03 source-first empty HEAVY module; use task-background Blender only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy

from v3_common import ROOT, VERSION, reset, group, box, anchor, material, xyz, runtime_xyz, finish

ASSET_ID = "heavy-bay"
PLAN = ROOT / "assets/v3/specs/heavy-bay.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/heavy-bay.blend"


def build(stage="initial"):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if hashlib.sha256((ROOT/plan["source_contract"]["path"]).read_bytes()).hexdigest() != plan["source_contract"]["sha256"]:
        raise ValueError("Current C04 source differs from reviewed HEAVY dimension plan")
    if hashlib.sha256((ROOT/plan["C08_interface"]["path"]).read_bytes()).hexdigest() != plan["C08_interface"]["sha256"]:
        raise ValueError("Current C08 source differs from reviewed HEAVY dimension plan")
    root = group("heavy-bay__MODULE")
    for key,value in {"asset_id":ASSET_ID,"role":"storage_module","storage_family":"HEAVY",
                      "reference_id":"R13.3","reference_sha256":plan["reference"]["sha256"],
                      "author_stage":"M03-"+stage,"origin":"floor_centre","contains_inventory":False,
                      "usable_bays":1,"usable_levels":1,"operational_admission":False,
                      "support_pattern":"three_ribs_two_open_top_channels","full_floor_support":False,
                      "c08_source_sha256":plan["C08_interface"]["sha256"],
                      "dimension_plan_sha256":hashlib.sha256(PLAN.read_bytes()).hexdigest(),
                      "c04_source_sha256":plan["source_contract"]["sha256"]}.items():root[key]=value
    mats={name:material("HEAVY | "+name,color,roughness=.86) for name,color in plan["palette"].items()}
    for part in plan["parts"]:
        b=part["bounds_local_xyz_m"];lo,hi=b["min"],b["max"]
        obj=box(part["part_id"],[(lo[k]+hi[k])/2 for k in range(3)],
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
    directory=ROOT/"assets/v3/iterations/heavy-bay"/args.snapshot
    if directory.exists():raise FileExistsError("Preserve existing checkpoint; choose another --snapshot")
    directory.mkdir(parents=True);reset();root=build(args.snapshot);before=metrics(root)
    if before["mesh_parts"]!=17 or before["triangles"]>1200 or len(before["anchors"])!=1:raise ValueError("HEAVY budget/anchor mismatch")
    SOURCE.parent.mkdir(parents=True,exist_ok=True);bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    if args.export:
        finish(ASSET_ID,root);bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        reopened=next(o for o in bpy.data.objects if o.get("asset_id")==ASSET_ID and o.parent is None)
        if metrics(reopened)!=before:raise ValueError("Editable source changed after finish/reopen")
    snapshot=directory/"heavy-bay.blend";snapshot.write_bytes(SOURCE.read_bytes())
    before.update(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),dimension_plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),glb_exported=args.export)
    (directory/"source-metrics.json").write_text(json.dumps(before,indent=2)+"\n",encoding="utf-8")
    (directory/"dimension-plan.json").write_bytes(PLAN.read_bytes())
    print("M03_SOURCE_READY "+json.dumps({k:before[k] for k in ["mesh_parts","triangles","dimensions_xyz_m","source_sha256","glb_exported"]}))


if __name__=="__main__":main()
