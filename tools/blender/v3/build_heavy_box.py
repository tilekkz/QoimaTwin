"""M06.3: reinforced hollow HEAVY_BOX, fixed HU and direct-underbase interface.

No ground pickup or manual 200kg carrying is implied. Reference-bound initial
dimensions stay frozen; actual model detail is saved in heavy-box.geometry.json.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, anchor, box, finish, group, material, reset, runtime_xyz, xyz

ASSET="heavy-box"
ITERATION=ROOT/"assets/v3/iterations/heavy-box/M06.3-02"
SPEC=ROOT/"assets/v3/specs/heavy-box.geometry.json"
EPS=2e-6
INPUTS=["assets/references/v3/m06-3-heavy-box.png",
        "assets/references/v3/m06-3-heavy-box.targets.json",
        "assets/references/v3/prompts/m06-3-heavy-box.txt",
        "assets/v3/specs/heavy-box.dimensions.json",
        "docs/v3/contract-proposals/cargo-catalog-v3.json",
        "docs/v3/contract-proposals/vehicle-handling-v3.json"]


def bindings():
    return [{"path":p,"sha256":hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in INPUTS]


def data():
    c=json.loads((ROOT/INPUTS[4]).read_text(encoding="utf-8"))
    record=next(r for r in c["records"] if r["archetype_id"]=="HEAVY_BOX")
    recipe=next(r for r in c["packing_recipes"] if r["archetype_id"]=="HEAVY_BOX")
    assert record["handling_unit"]["dimensions_xyz_m"]==[.8,.65,.6]
    return record,recipe


def cuboid(name,low,high,mat,parent,bevel=.0015):
    return box(name,[(a+b)/2 for a,b in zip(low,high)],[b-a for a,b in zip(low,high)],mat,parent,bevel)


def build():
    root=group(ASSET);record,_=data()
    root["role"]="handling_unit_template";root["archetype_id"]="HEAVY_BOX"
    root["reference_id"]="M06.3_REF";root["gross_mass_kg"]=200.;root["units_per_handling_unit"]=8
    root["required_handler_tag"]="forklift_operator"
    root["required_equipment_tags_json"]=json.dumps(["forklift","approved_load_support"])
    root["manual_carry_allowed"]=False;root["positioning_handles_only"]=True
    root["ground_pickup_allowed"]=False;root["raised_open_support_required"]=True
    root["operational_admission"]=False;root["source_bindings_json"]=json.dumps(bindings(),sort_keys=True)
    body=material("V3_HEAVY_charcoal","#293D46")
    frame=material("V3_HEAVY_frame","#213139")
    gasket=material("V3_HEAVY_gasket","#18262C")
    steel=material("V3_HEAVY_positioning_hardware","#929D9F",.72,.12)
    plate=material("V3_HEAVY_plain_id_plate","#D8D7CD")

    # Entire reinforced base <=.04. Central strip bears on M03's central rib;
    # fork pads remain above its voids until the two direct forks engage.
    cuboid("base_web",(-.386,.012,-.282),(.386,.04,.282),frame,root)
    cuboid("bearing_central",(-.17,0,-.27),(.17,.012,.27),frame,root,.001)
    for side,x in (("left",-.24),("right",.24)):
        cuboid(f"bearing_fork_{side}",(x-.06,0,-.27),(x+.06,.012,.27),frame,root,.001)
    for side,lo,hi in (("front",(-.36,0,.282),(.36,.04,.30)),
                       ("rear",(-.36,0,-.30),(.36,.04,-.282)),
                       ("left",(-.40,0,-.26),(-.386,.04,.26)),
                       ("right",(.386,0,-.26),(.40,.04,.26))):
        cuboid("base_edge_"+side,lo,hi,frame,root)
    # Actual .014 panels, with contained corners rather than oversize rails.
    for name,lo,hi in (("front",(-.36,.04,.268),(.36,.620,.282)),
                        ("rear",(-.36,.04,-.282),(.36,.620,-.268)),
                        ("left",(-.386,.04,-.26),(-.372,.620,.26)),
                        ("right",(.372,.04,-.26),(.386,.620,.26))):
        cuboid("panel_"+name,lo,hi,body,root)
    for ix,x in enumerate((-.38,.38)):
        for iz,z in enumerate((-.28,.28)):
            cuboid(f"corner_base_{ix}_{iz}",(x-.02,0,z-.02),(x+.02,.04,z+.02),frame,root,.002)
            cuboid(f"corner_{ix}_{iz}",(x-.02,.04,z-.02),(x+.02,.624,z+.02),frame,root,.003)
    for side,lo,hi in (("front",(-.36,.620,.268),(.36,.624,.282)),
                       ("rear",(-.36,.620,-.282),(.36,.624,-.268)),
                       ("left",(-.386,.620,-.26),(-.372,.624,.26)),
                       ("right",(.372,.620,-.26),(.386,.624,.26))):
        cuboid("gasket_"+side,lo,hi,gasket,root,.0004)
    cuboid("lid_main",(-.36,.624,-.282),(.36,.65,.282),body,root,.002)
    for side,a,b in (("left",-.40,-.36),("right",.36,.40)):
        cuboid("lid_cap_"+side,(a,.624,-.30),(b,.65,.30),frame,root,.002)

    # Two front-only open rectangular positioning pulls. Each of four bars
    # joins two real brackets, not a dark painted rectangle. No manual anchor.
    for side,x in (("left",-.21),("right",.21)):
        for tag,lo,hi in (("top",(x-.07,.448,.292),(x+.07,.460,.30)),
                          ("bottom",(x-.07,.385,.292),(x+.07,.397,.30)),
                          ("left",(x-.07,.397,.292),(x-.058,.448,.30)),
                          ("right",(x+.058,.397,.292),(x+.07,.448,.30))):
            cuboid(f"handle_{side}_{tag}",lo,hi,steel,root,.001)
        for n,xx in enumerate((x-.058,x+.058)):
            cuboid(f"handle_{side}_bracket_{n}",(xx-.011,.448,.282),
                   (xx+.011,.470,.296),steel,root,.001)
    for side,x in (("left",-.30),("right",.30)):
        cuboid(f"latch_{side}_mount",(x-.03,.628,.282),(x+.03,.640,.294),steel,root,.001)
        cuboid(f"latch_{side}_clasp",(x-.013,.592,.292),(x+.013,.634,.30),steel,root,.001)
    for side,x in (("left",-.27),("right",.27)):
        cuboid(f"hinge_{side}_lower",(x-.032,.603,-.294),(x+.032,.620,-.282),steel,root,.001)
        cuboid(f"hinge_{side}_upper",(x-.032,.624,-.294),(x+.032,.641,-.282),steel,root,.001)
        cuboid(f"hinge_{side}_barrel",(x-.034,.616,-.30),(x+.034,.628,-.288),steel,root,.001)
    cuboid("plain_id_plate",(.245,.09,.282),(.315,.12,.284),plate,root,.0004)
    anchor("anchor_support_bottom",(0,0,0),root,"handling_unit_bottom_support")
    for side,x in (("left",-.24),("right",.24)):
        anchor("anchor_direct_fork_"+side,(x,0,0),root,"direct_under_HU_bearing_contact")
    for side,x in (("left",-.21),("right",.21)):
        a=anchor("anchor_positioning_handle_"+side,(x,.4225,.30),root,"positioning_hardware_only")
        a["manual_carry_allowed"]=False
    return root


def collect(root):
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();parts=[];vertices=[];triangles=[]
    for obj in root.children_recursive:
        if obj.type!="MESH":continue
        ev=obj.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(m);bm.normal_update()
        volume=bm.calc_volume(signed=True)
        assert volume>1e-12 and all(len(e.link_faces)==2 and e.is_contiguous for e in bm.edges),(obj.name,"closed/winding/volume")
        assert all(f.calc_area()>1e-12 for f in bm.faces);bm.free()
        world=[ev.matrix_world@v.co for v in m.vertices];vs=[runtime_xyz(v) for v in world];ts=[tuple(t.vertices) for t in m.loop_triangles]
        lo=[min(v[i] for v in vs) for i in range(3)];hi=[max(v[i] for v in vs) for i in range(3)]
        bvh=BVHTree.FromPolygons(world,ts,all_triangles=True,epsilon=1e-8)
        samples=world+[sum((world[i] for i in t),Vector())/3 for t in ts]
        parts.append({"name":obj.name,"verts":vs,"tris":ts,"low":lo,"high":hi,"bvh":bvh,"samples":samples,"volume":volume})
        off=len(vertices);vertices+=world;triangles += [tuple(off+i for i in t) for t in ts];ev.to_mesh_clear()
    return parts,BVHTree.FromPolygons(vertices,triangles,all_triangles=True,epsilon=1e-8)


def triangle_box(tri,low,high):
    centre=Vector([(a+b)/2 for a,b in zip(low,high)]);half=[(b-a)/2 for a,b in zip(low,high)]
    ps=[Vector(v)-centre for v in tri];es=[ps[1]-ps[0],ps[2]-ps[1],ps[0]-ps[2]];us=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    for axis in us+[es[0].cross(es[1])]+[e.cross(a) for e in es for a in us]:
        if axis.length_squared<1e-22:continue
        p=[axis.dot(v) for v in ps];radius=sum(abs(axis[i])*half[i] for i in range(3))
        if min(p)>radius+1e-12 or max(p)<-radius-1e-12:return False
    return True


def empty(parts,low,high,name):
    low=[v+EPS for v in low];high=[v-EPS for v in high]
    for p in parts:
        if any(p["high"][i]<=low[i] or p["low"][i]>=high[i] for i in range(3)):continue
        assert not any(triangle_box([p["verts"][i] for i in t],low,high) for t in p["tris"]),(name,p["name"],"intrusion")
        near,normal,_,_=p["bvh"].find_nearest(xyz([(a+b)/2 for a,b in zip(low,high)]))
        assert near is None or normal.dot(xyz([(a+b)/2 for a,b in zip(low,high)])-near)>=-EPS,(name,"solid core")


def verify(root):
    parts,union=collect(root);record,recipe=data()
    lo=[min(p["low"][i] for p in parts) for i in range(3)];hi=[max(p["high"][i] for p in parts) for i in range(3)]
    assert all(abs(a-b)<EPS for a,b in zip(lo+hi,[-.4,0,-.3,.4,.65,.3]))
    assert all(all(abs(o.scale[i]-1)<EPS for i in range(3)) for o in [root]+list(root.children_recursive))
    empty(parts,[-.35,.06,-.25],[.35,.6,.25],"C02 full inner")
    for u in recipe["unit_instances"]:
        empty(parts,[v-s for v,s in zip(u["min_xyz_m"],[.4,0,.3])],
              [v-s for v,s in zip(u["max_xyz_m"],[.4,0,.3])],f"C02 unit{u['unit_ordinal']}")
    for side,x in (("left",-.21),("right",.21)):
        empty(parts,[x-.05,.402,.284],[x+.05,.443,.31],"real handle opening "+side)
    depths=[]
    for name,origin,direction,expected in (("front",(0,.25,0),(0,0,1),.014),("rear",(0,.25,0),(0,0,-1),.014),
                                          ("left",(0,.25,0),(-1,0,0),.014),("right",(0,.25,0),(1,0,0),.014),
                                          ("lid",(0,.30,0),(0,1,0),.026)):
        ray=xyz(direction);hit,n,_,_=union.ray_cast(xyz(origin),ray,1.)
        assert hit is not None and n.dot(ray)<-.999
        out,on,_,_=union.ray_cast(hit+ray*.00005,ray,.04)
        assert out is not None and on.dot(ray)>.999;th=(out-hit).length
        assert abs(th-expected)<EPS,(name,th,expected)
        depths.append({"part":name,"actual_thickness_m":th,"inner_hit":runtime_xyz(hit),"outer_hit":runtime_xyz(out)})
    contacts={}
    for tag,xxs in (("central",(-.14,0,.14)),("fork_left",(-.275,-.24,-.205)),("fork_right",(.205,.24,.275))):
        points=[]
        for x in xxs:
            for z in (-.23,0,.23):
                hit,n,_,_=union.ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.025)
                assert hit is not None and abs(runtime_xyz(hit)[1])<EPS and n.dot(xyz((0,-1,0)))>.999
                points.append(runtime_xyz(hit))
        contacts[tag]=points
    for x in (-.24,.24):
        empty(parts,[x-.04,-.07,-.8],[x+.04,0,.3],"relative direct blade; external floor excluded")
    adjacency={p["name"]:set() for p in parts};links=[]
    for i,a in enumerate(parts):
        for b in parts[i+1:]:
            if any(a["high"][j]<b["low"][j]-EPS or b["high"][j]<a["low"][j]-EPS for j in range(3)):continue
            connected=bool(a["bvh"].overlap(b["bvh"]))
            if not connected:
                for samples,target in ((a["samples"],b["bvh"]),(b["samples"],a["bvh"])):
                    if any((n:=target.find_nearest(v))[3] is not None and n[3]<EPS for v in samples):connected=True;break
            if connected:adjacency[a["name"]].add(b["name"]);adjacency[b["name"]].add(a["name"]);links.append([a["name"],b["name"]])
    reached={"base_web"};frontier=list(reached)
    while frontier:
        for nxt in adjacency[frontier.pop()]-reached:reached.add(nxt);frontier.append(nxt)
    assert reached==set(adjacency),("unconnected hardware",set(adjacency)-reached)
    return {"asset_id":ASSET,"method":"evaluated closed/winding/positive solids; SAT/BVH cavity/thickness/contact rays",
            "bounds_runtime":{"min":lo,"max":hi},"all_scene_node_scales_one":True,"closed_positive_outward_parts":len(parts),
            "actual_contact_links":len(links),"all_parts_connected":True,"full_C02_inner_clear":True,"unchanged_unit_AABBs_clear":len(recipe["unit_instances"]),
            "real_front_handle_openings_clear":2,"shell_thickness_rays":depths,"underside_contacts":contacts,
            "direct_relative_blades_clear":2,"external_floor_fixture_in_this_check":False,"ground_pickup_allowed":False,
            "actual_solid_volume_m3":sum(p["volume"] for p in parts),"HU_bounding_volume_m3":record["handling_unit"]["bounding_volume_m3"],
            "M03_scope":"Only planned central rib contact; no outer-rib/payload/stability or actual fixture-action approval.",
            "manual_carry_allowed":False,"operational_admission":False,"sources":bindings()}


def material_audit():
    raw=(ROOT/"frontend/public/models/v3/heavy-box.glb").read_bytes();n=struct.unpack_from("<I",raw,12)[0];g=json.loads(raw[20:20+n]);report=[]
    for m in g["materials"]:
        node=next(n for n in bpy.data.materials[m["name"]].node_tree.nodes if n.type=="BSDF_PRINCIPLED")
        source={"baseColorFactor":list(node.inputs["Base Color"].default_value),"roughnessFactor":node.inputs["Roughness"].default_value,"metallicFactor":node.inputs["Metallic"].default_value};p=m["pbrMetallicRoughness"]
        assert max(abs(a-b) for a,b in zip(source["baseColorFactor"],p["baseColorFactor"]))<1e-6
        assert all(abs(source[k]-p[k])<1e-6 for k in ("roughnessFactor","metallicFactor"))
        report.append({"name":m["name"],"source":source,"glb":p})
    return report


def saved_audit():
    p=ROOT/"assets/v3/blender/heavy-box.blend";before=hashlib.sha256(p.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(p))
    root=bpy.data.objects[ASSET];meshes=[o for o in root.children_recursive if o.type=="MESH"]
    assert all(any(m.type=="BEVEL" for m in o.modifiers) for o in meshes)
    assert root["gross_mass_kg"]==200 and not root["manual_carry_allowed"] and not root["ground_pickup_allowed"]
    mats=material_audit();assert before==hashlib.sha256(p.read_bytes()).hexdigest()
    report={"asset_id":ASSET,"mode":"read_only_saved_blend","source_sha256":before,"editable_meshes_and_bevels":len(meshes),
            "matching_materials":mats,"source_unchanged":True,"manual_or_ground_pickup_admission":False}
    (ITERATION/"saved-source-checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("M06_3_SAVED_SOURCE_CHECKS "+json.dumps({"meshes":len(meshes),"materials":len(mats),"source_unchanged":True}))


if __name__=="__main__":
    if not bpy.app.background:raise RuntimeError("Task background Blender only")
    if "--audit-source" in sys.argv:saved_audit();sys.exit(0)
    reset();root=build();report=verify(root);ITERATION.mkdir(parents=True,exist_ok=True)
    record,recipe=data()
    spec={"asset_id":ASSET,"units":"m","outer_dimensions_xyz_m":[.8,.65,.6],"origin":"floor centre,+Z front",
          "wall_thickness_m":.014,"base_max_y":.04,"lid_underside_y":.624,"lid_thickness_m":.026,
          "central_bearing_strip":{"x":[-.17,.17],"z":[-.27,.27],"bottom_y":0},"fork_pad_centres_x":[-.24,.24],"fork_pad_width_m":.12,
          "packing_inner_runtime":{"min":[-.35,.06,-.25],"max":[.35,.60,.25]},"unit_AABBs_source":"/packing_recipes/2",
          "handling_unit":record["handling_unit"],"units_baked":False,"ground_pickup_allowed":False,"manual_carry_allowed":False,
          "fixture_action_and_rating_required":True,"sources":bindings()}
    SPEC.write_text(json.dumps(spec,indent=2)+"\n",encoding="utf-8")
    finish(ASSET,root);report["source_glb_materials"]=material_audit()
    (ITERATION/"mesh-checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    for p in (ROOT/"assets/v3/blender/heavy-box.blend",ROOT/"assets/v3/blender/heavy-box.stats.json",ROOT/"frontend/public/models/v3/heavy-box.glb",SPEC,ROOT/INPUTS[3],Path(__file__)):
        shutil.copy2(p,ITERATION/p.name)
    print("M06_3_MESH_CHECKS "+json.dumps({k:report[k] for k in ("closed_positive_outward_parts","actual_contact_links","unchanged_unit_AABBs_clear","real_front_handle_openings_clear","actual_solid_volume_m3")}))
