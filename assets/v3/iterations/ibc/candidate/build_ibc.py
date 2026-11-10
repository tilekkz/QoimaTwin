"""One sealed IBC unit in an integral cage; fixed C02 frames, source first."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import bpy
import bmesh

from v3_common import ROOT, VERSION, reset, group, box, cylinder, anchor, material, xyz, runtime_xyz, finish

ASSET_ID = "ibc"
PLAN = ROOT / "assets/v3/specs/ibc.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/ibc.blend"


def closed_mesh(name, vertices, faces, mat, parent, smooth=False):
    mesh = bpy.data.meshes.new(name + "__mesh")
    mesh.from_pydata([xyz(p) for p in vertices], [], faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    for polygon in mesh.polygons: polygon.use_smooth = smooth
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj); obj.parent = parent
    if smooth:
        normal = obj.modifiers.new("Weighted bottle panel normals", "WEIGHTED_NORMAL"); normal.keep_sharp = True
    return obj


def bottle(plan, mat, parent):
    vertices = []; rings = plan["primary_container_plan"]["actual_body_ring_plan"]
    for ring in rings:
        half, rear, front, radius = ring["half_x"],ring["rear_z"],ring["front_z"],ring["corner_radius"]
        for cx,cz,start in [(half-radius,front-radius,0),(-half+radius,front-radius,90),
                            (-half+radius,rear+radius,180),(half-radius,rear+radius,270)]:
            for j in range(4):
                angle=math.radians(start+30*j)
                vertices.append((cx+radius*math.cos(angle),ring["y"],cz+radius*math.sin(angle)))
    count=16;faces=[tuple(reversed(range(count))),tuple(range((len(rings)-1)*count,len(rings)*count))]
    for r in range(len(rings)-1):
        for i in range(count):faces.append((r*count+i,r*count+(i+1)%count,(r+1)*count+(i+1)%count,(r+1)*count+i))
    return closed_mesh("primary_bottle",vertices,faces,mat,parent,True)


def outlet_ring(mat,parent,inner_mat):
    vertices=[];faces=[];count=16
    for z in [.422,.44]:
        for radius in [.034,.022]:
            vertices += [(radius*math.cos(2*math.pi*i/count),.205+radius*math.sin(2*math.pi*i/count),z) for i in range(count)]
    for i in range(count):
        j=(i+1)%count
        faces += [(i,j,2*count+j,2*count+i),(count+i,3*count+i,3*count+j,count+j),
                  (i,count+i,count+j,j),(2*count+i,2*count+j,3*count+j,3*count+i)]
    obj=closed_mesh("primary_outlet_annulus",vertices,faces,mat,parent)
    obj.data.materials.append(inner_mat)
    for polygon in obj.data.polygons:
        radii=[math.hypot(runtime_xyz(obj.data.vertices[i].co)[0],runtime_xyz(obj.data.vertices[i].co)[1]-.205) for i in polygon.vertices]
        if all(abs(radius-.022)<1e-6 for radius in radii):polygon.material_index=1
    return obj


def rounded_cylinder(name,loc,radius,depth,mat,parent,axis="Y"):
    obj=cylinder(name,loc,radius,depth,mat,parent,axis=axis,vertices=16)
    bevel=obj.modifiers.new("Contained cap and port rim bevel", "BEVEL")
    bevel.width=.001;bevel.segments=1;bevel.harden_normals=True
    normal=obj.modifiers.new("Weighted cap and port normals","WEIGHTED_NORMAL");normal.keep_sharp=True
    return obj


def build(stage="initial"):
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    for binding in [plan["source_C02"],plan["source_C08"],plan["reference"]]:
        if hashlib.sha256((ROOT/binding["path"]).read_bytes()).hexdigest()!=binding["sha256"]:
            raise ValueError("Stale IBC source/reference "+binding["path"])
    root=group("ibc__HU")
    for key,value in {"asset_id":ASSET_ID,"role":"cargo_handling_unit","archetype_id":"IBC","reference_id":"M09_REF",
                      "reference_sha256":plan["reference"]["sha256"],"author_stage":"M09-"+stage,"origin":"floor_centre",
                      "HU_count":1,"units_per_HU":1,"prototype_contents_not_stock":True,"contains_inventory":False,
                      "declared_gross_mass_kg":654.,"declared_primary_unit_gross_mass_kg":614.,"symbolic_fluid_mass_kg":600.,
                      "mass_computed_from_mesh":False,"fluid_units":0,"operational_admission":False,
                      "c02_source_sha256":plan["source_C02"]["sha256"],"c08_source_sha256":plan["source_C08"]["sha256"],
                      "dimension_plan_sha256":hashlib.sha256(PLAN.read_bytes()).hexdigest()}.items():root[key]=value
    mats={name:material("IBC | "+name,color,roughness=.86) for name,color in plan["palette"].items()}
    for part in plan["parts"]:
        b=part["bounds_local_xyz_m"];lo,hi=b["min"],b["max"]
        obj=box(part["part_id"],[(lo[k]+hi[k])/2 for k in range(3)],[hi[k]-lo[k] for k in range(3)],mats[part["material"]],root,bevel=part["bevel_m"])
        obj["part_id"]=part["part_id"];obj["role"]="integral_IBC_cage_and_support"
        obj["planned_bounds_json"]=json.dumps(b)
    frame=group("unit__001",root,plan["unit_frame_local_xyz_m"])
    frame["role"]="HU_content_unit_frame";frame["unit_ordinal"]=1;frame["packaged_dimensions_xyz_m"]=[1.08,1.02,.88]
    frame["canonical_bounds_HU_json"]=json.dumps(plan["unit_bounds_HU_local"]);frame["prototype_contents_not_stock"]=True
    primary=[bottle(plan,mats["offwhite"],root),
             rounded_cylinder("primary_neck",[0,1.09,0],.09,.03,mats["offwhite"],root),
             rounded_cylinder("primary_cap",[0,1.1075,0],.10,.035,mats["petrol"],root),
             rounded_cylinder("primary_inlet",[0,.205,.375],.035,.04,mats["offwhite"],root,"Z"),
             rounded_cylinder("primary_valve",[0,.205,.412],.04,.036,mats["petrol"],root,"Z"),
             outlet_ring(mats["offwhite"],root,mats["charcoal"]),
             rounded_cylinder("primary_valve_stem",[0,.2475,.411],.009,.045,mats["petrol"],root),
             box("primary_valve_handle",[0,.275,.411],[.08,.02,.02],mats["petrol"],root,bevel=.002)]
    for obj in primary:
        obj["part_id"]=obj.name;obj["role"]="sealed_primary_container_component";obj["unit_ordinal"]=1
        obj["content_frame_id"]=frame.name;obj["intentional_primary_mating_joints"]=True
    for item in plan["anchors_plan"]:
        obj=anchor(item["anchor_id"],item["local_xyz_m"],root,role=item["role"]);obj["mass_computed_from_mesh"]=False
    bpy.context.view_layer.update();return root


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
    directory=ROOT/"assets/v3/iterations/ibc"/args.snapshot
    if directory.exists():raise FileExistsError("Preserve existing checkpoint; choose another --snapshot")
    directory.mkdir(parents=True);reset();root=build(args.snapshot);before=metrics(root)
    if before["mesh_parts"]!=52 or before["triangles"]>7000 or len(before["anchors"])!=2:raise ValueError("IBC budget/anchor mismatch")
    SOURCE.parent.mkdir(parents=True,exist_ok=True);bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    if args.export:
        finish(ASSET_ID,root);bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        reopened=next(o for o in bpy.data.objects if o.get("asset_id")==ASSET_ID and o.parent is None)
        if metrics(reopened)!=before:raise ValueError("Editable source changed after finish/reopen")
    snapshot=directory/"ibc.blend";snapshot.write_bytes(SOURCE.read_bytes())
    before.update(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),dimension_plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),glb_exported=args.export)
    (directory/"source-metrics.json").write_text(json.dumps(before,indent=2)+"\n",encoding="utf-8")
    (directory/"dimension-plan.json").write_bytes(PLAN.read_bytes())
    print("M09_SOURCE_READY "+json.dumps({k:before[k] for k in ["mesh_parts","triangles","dimensions_xyz_m","source_sha256","glb_exported"]}))


if __name__=="__main__":main()
