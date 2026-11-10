"""M06.1: real thin folded carton shell, fixed C02 HU, no content instances.

Background Blender only. Source is saved editable before GLB batching. The
independent M06.1_REF raster preceded geometry and was separately root approved.
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

ASSET="small-carton"
ITERATION=ROOT/"assets/v3/iterations/small-carton/M06.1-01"
SPEC=ROOT/"assets/v3/specs/small-carton.dimensions.json"
EPS=3e-7
INPUTS=["assets/references/v3/m06-1-small-carton.png",
        "assets/references/v3/m06-1-small-carton.targets.json",
        "assets/references/v3/prompts/m06-1-small-carton.txt",
        "assets/references/v3/r03-dimension-targets.json",
        "docs/v3/contract-proposals/cargo-catalog-v3.json"]


def bindings():
    return [{"path":p,"sha256":hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in INPUTS]


def carton_data():
    data=json.loads((ROOT/INPUTS[-1]).read_text(encoding="utf-8"))
    record=next(r for r in data["records"] if r["archetype_id"]=="SMALL_CARTON")
    recipe=next(r for r in data["packing_recipes"] if r["archetype_id"]=="SMALL_CARTON")
    assert record["handling_unit"]["dimensions_xyz_m"]==[.32,.24,.24]
    return record,recipe


def cuboid(name,low,high,mat,parent,bevel=.00025):
    return box(name,[(a+b)/2 for a,b in zip(low,high)],
               [b-a for a,b in zip(low,high)],mat,parent,bevel)


def arrow(name,x,y,root,mat):
    # A genuinely thin ink extrusion attached to the front paper face.
    outline=[(-.0021,0),(.0021,0),(.0021,.017),(.0065,.017),
             (0,.028),(-.0065,.017),(-.0021,.017)]
    points=[xyz((x+xx,y+yy,z)) for z in (.1195,.11965) for xx,yy in outline]
    n=len(outline)
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name+"_mesh");mesh.from_pydata(points,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj.parent=root;mesh.materials.append(mat)
    return obj


def build():
    root=group(ASSET);record,_=carton_data()
    root["role"]="handling_unit_template"
    root["archetype_id"]="SMALL_CARTON"
    root["reference_id"]="M06.1_REF"
    root["gross_mass_kg"]=record["handling_unit"]["gross_mass_kg"]
    root["units_per_handling_unit"]=24
    root["contents_semantics"]="C02 packaged-unit data; no stock or baked interior HU copies"
    root["operational_admission"]=False
    root["source_bindings_json"]=json.dumps(bindings(),sort_keys=True)
    tan=material("V3_SMALL_cardboard_tan","#C99A60")
    buff=material("V3_SMALL_paper_tape","#DEC08A")
    paper=material("V3_SMALL_label_paper","#E8E3D9")
    ink=material("V3_SMALL_ink","#293D46")

    # Wall faces reserve .0005 at front/rear for the attached tape, within the
    # unchanged .24 HU depth. Walls/bottom have real .003 thickness.
    cuboid("shell_bottom",(-.16,0,-.1195),(.16,.003,.1195),tan,root)
    cuboid("shell_front",(-.16,.003,.1165),(.16,.2365,.1195),tan,root)
    cuboid("shell_rear",(-.16,.003,-.1195),(.16,.2365,-.1165),tan,root)
    cuboid("shell_left",(-.16,.003,-.1165),(-.157,.2365,.1165),tan,root)
    cuboid("shell_right",(.157,.003,-.1165),(.16,.2365,.1165),tan,root)
    # Two flush major flaps. Their tiny centre butt seam is sealed by tape;
    # contained short underflaps are genuine material, not an oversized rim.
    cuboid("lid_major_left",(-.16,.2365,-.1195),(-.0004,.2395,.1195),tan,root,.00015)
    cuboid("lid_major_right",(.0004,.2365,-.1195),(.16,.2395,.1195),tan,root,.00015)
    cuboid("lid_under_front",(-.157,.2335,.0905),(.157,.2365,.1165),tan,root,.00015)
    cuboid("lid_under_rear",(-.157,.2335,-.1165),(.157,.2365,-.0905),tan,root,.00015)
    # A .0005 paper tape band, physically folded over both edges. Tail tops
    # reach .24 so they share finite faces with the top strip, not just an edge.
    cuboid("tape_top",(-.017,.2395,-.1195),(.017,.24,.1195),buff,root,.00003)
    cuboid("tape_front",(-.017,.19,.1195),(.017,.24,.12),buff,root,.00003)
    cuboid("tape_rear",(-.017,.19,-.12),(.017,.24,-.1195),buff,root,.00003)
    cuboid("label_paper",(-.135,.153,.1195),(-.051,.198,.11975),paper,root,.00005)
    for i,(width,y) in enumerate(((.059,.187),(.046,.177),(.029,.167)),1):
        cuboid(f"label_line_{i}",(-.124,y-.0014,.11975),(-.124+width,y+.0014,.11990),ink,root,.00002)
    arrow("up_arrow_left",.105,.036,root,ink)
    arrow("up_arrow_right",.126,.036,root,ink)
    cuboid("arrow_baseline",(.094,.029,.1195),(.137,.031,.11965),ink,root,.00002)
    anchor("anchor_support_bottom",(0,0,0),root,"handling_unit_bottom_support")
    anchor("anchor_hand_grip_left",(-.16,.12,0),root,"candidate_manual_contact")
    anchor("anchor_hand_grip_right",(.16,.12,0),root,"candidate_manual_contact")
    return root


def collect(root):
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    parts=[];vertices=[];triangles=[]
    for obj in root.children_recursive:
        if obj.type!="MESH":continue
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
        bm=bmesh.new();bm.from_mesh(mesh);bm.normal_update()
        volume=bm.calc_volume(signed=True)
        assert volume>1e-12 and all(len(e.link_faces)==2 and e.is_contiguous for e in bm.edges),(obj.name,"volume/manifold/winding")
        assert all(f.calc_area()>1e-13 for f in bm.faces),(obj.name,"degenerate face")
        bm.free()
        world=[evaluated.matrix_world@v.co for v in mesh.vertices];runtime=[runtime_xyz(v) for v in world]
        tris=[tuple(t.vertices) for t in mesh.loop_triangles]
        low=[min(p[i] for p in runtime) for i in range(3)];high=[max(p[i] for p in runtime) for i in range(3)]
        bvh=BVHTree.FromPolygons(world,tris,all_triangles=True,epsilon=1e-8)
        samples=world+[sum((world[i] for i in t),Vector())/3 for t in tris]
        parts.append({"name":obj.name,"verts":runtime,"triangles":tris,"low":low,"high":high,
                      "bvh":bvh,"samples":samples,"volume":volume})
        off=len(vertices);vertices+=world;triangles += [tuple(off+i for i in t) for t in tris]
        evaluated.to_mesh_clear()
    return parts,BVHTree.FromPolygons(vertices,triangles,all_triangles=True,epsilon=1e-8)


def triangle_box(tri,low,high):
    centre=Vector([(a+b)/2 for a,b in zip(low,high)]);half=[(b-a)/2 for a,b in zip(low,high)]
    ps=[Vector(p)-centre for p in tri];edges=[ps[1]-ps[0],ps[2]-ps[1],ps[0]-ps[2]]
    units=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    axes=units+[edges[0].cross(edges[1])]+[e.cross(a) for e in edges for a in units]
    for axis in axes:
        if axis.length_squared<1e-22:continue
        values=[axis.dot(p) for p in ps];radius=sum(abs(axis[i])*half[i] for i in range(3))
        if min(values)>radius+1e-12 or max(values)<-radius-1e-12:return False
    return True


def empty_box(parts,low,high,name):
    low=[x+EPS for x in low];high=[x-EPS for x in high]
    for p in parts:
        if any(p["high"][i]<=low[i] or p["low"][i]>=high[i] for i in range(3)):continue
        assert not any(triangle_box([p["verts"][i] for i in t],low,high) for t in p["triangles"]),(name,"triangle intrusion",p["name"])
        # All components whose broadphase can reach the packing cavity are
        # convex wall/flap boxes. Thin concave arrows are far outside it.
        centre=xyz([(a+b)/2 for a,b in zip(low,high)]);near,normal,_,_=p["bvh"].find_nearest(centre)
        assert near is None or normal.dot(centre-near)>=-EPS,(name,"solid core",p["name"])


def verify(root):
    parts,union=collect(root);record,recipe=carton_data()
    low=[min(p["low"][i] for p in parts) for i in range(3)];high=[max(p["high"][i] for p in parts) for i in range(3)]
    assert all(abs(a-b)<EPS for a,b in zip(low+high,[-.16,0,-.12,.16,.24,.12]))
    inner_low=[-.145,.015,-.105];inner_high=[.145,.225,.105]
    empty_box(parts,inner_low,inner_high,"C02 exact packing inner")
    for unit in recipe["unit_instances"]:
        lo=[v-s for v,s in zip(unit["min_xyz_m"],[.16,0,.12])]
        hi=[v-s for v,s in zip(unit["max_xyz_m"],[.16,0,.12])]
        empty_box(parts,lo,hi,f"C02 unit {unit['unit_ordinal']}")
    # Actual two-surface ray thickness at plain wall/bottom/flap locations.
    depth=[]
    for name,origin,direction in (("left",(0,.12,0),(-1,0,0)),("right",(0,.12,0),(1,0,0)),
                                  ("front",(0,.12,0),(0,0,1)),("rear",(0,.12,0),(0,0,-1)),
                                  ("bottom",(0,.12,0),(0,-1,0)),("major_lid",(.07,.12,0),(0,1,0))):
        ray=xyz(direction);hit,normal,_,distance=union.ray_cast(xyz(origin),ray,.5)
        assert hit is not None and normal.dot(ray)<-.999,("missing inward shell surface",name)
        outer,outer_normal,_,_=union.ray_cast(hit+ray*.00001,ray,.006)
        assert outer is not None and outer_normal.dot(ray)>.999,("missing outer shell surface",name)
        thickness=(outer-hit).length
        assert abs(thickness-.003)<EPS,(name,"not3mm",thickness)
        depth.append({"part":name,"inner_hit":runtime_xyz(hit),"outer_hit":runtime_xyz(outer),"thickness_m":thickness})
    support=[]
    for x in (-.12,0,.12):
        for z in (-.08,0,.08):
            hit,normal,_,_=union.ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.02)
            assert hit is not None and abs(runtime_xyz(hit)[1])<EPS and normal.dot(xyz((0,-1,0)))>.999
            support.append(runtime_xyz(hit))
    # Surface contacts, with broadphase only as a candidate filter.
    adjacency={p["name"]:set() for p in parts};links=[]
    for i,a in enumerate(parts):
        for b in parts[i+1:]:
            if any(a["high"][j]<b["low"][j]-EPS or b["high"][j]<a["low"][j]-EPS for j in range(3)):continue
            contact=bool(a["bvh"].overlap(b["bvh"]))
            if not contact:
                for samples,target in ((a["samples"],b["bvh"]),(b["samples"],a["bvh"])):
                    if any((near:=target.find_nearest(v))[3] is not None and near[3]<EPS for v in samples):contact=True;break
            if contact:adjacency[a["name"]].add(b["name"]);adjacency[b["name"]].add(a["name"]);links.append([a["name"],b["name"]])
    reached={"shell_bottom"};frontier=list(reached)
    while frontier:
        for nxt in adjacency[frontier.pop()]-reached:reached.add(nxt);frontier.append(nxt)
    assert reached==set(adjacency),("loose material/part",set(adjacency)-reached)
    solid_volume=sum(p["volume"] for p in parts)
    assert solid_volume < .2*record["handling_unit"]["bounding_volume_m3"],"painted solid core"
    return {"asset_id":ASSET,"method":"evaluated closed-solid winding, triangle/openAABB SAT, BVH double-surface thickness/rays and actual contact graph",
            "bounds_runtime":{"min":low,"max":high},"positive_closed_consistently_outward_parts":len(parts),
            "actual_part_contact_edges":len(links),"all_parts_joined_to_bottom":True,
            "packing_inner_bounds_clear":{"min":inner_low,"max":inner_high},"unchanged_C02_unit_AABBs_clear":len(recipe["unit_instances"]),
            "empty_hollow_interior":True,"actual_solid_volume_m3":solid_volume,"HU_bounding_volume_m3":record["handling_unit"]["bounding_volume_m3"],
            "actual_shell_thickness_rays":depth,"actual_floor_support_points":support,"sources":bindings(),
            "contents_baked":False,"operational_admission":False,"root_browser_and_khronos":"pending"}


def specification():
    record,recipe=carton_data()
    return {"asset_id":ASSET,"reference_id":"M06.1_REF","namespace":"v3","units":"m","up_axis":"Y","front_axis":"+Z","origin":"floor centre",
            "outer_dimensions_xyz_m":[.32,.24,.24],"wall_bottom_majorflap_thickness_m":.003,
            "tape_thickness_m":.0005,"tape_width_m":.034,"major_flap_seam_width_m":.0008,
            "shell_inner_bounds_runtime":{"min":[-.157,.003,-.1165],"max":[.157,.2365,.1165]},
            "underflap_bottom_y":.2335,"packing_inner_bounds_runtime":{"min":[-.145,.015,-.105],"max":[.145,.225,.105]},
            "minimum_extra_clearance_to_packing_inner_m":.0085,"handling_unit":record["handling_unit"],"unit":record["unit"],
            "packing_recipe_source":"/packing_recipes/0","packing_grid_counts_xyz":recipe["grid_counts_xyz"],
            "unit_contents_geometry_baked":False,"source_bindings":bindings(),"operational_admission":False}


def material_audit(root):
    raw=(ROOT/"frontend/public/models/v3/small-carton.glb").read_bytes();n=struct.unpack_from("<I",raw,12)[0];gltf=json.loads(raw[20:20+n]);report=[]
    for item in gltf["materials"]:
        mat=bpy.data.materials[item["name"]];node=next(n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
        source={"baseColorFactor":list(node.inputs["Base Color"].default_value),"roughnessFactor":node.inputs["Roughness"].default_value,"metallicFactor":node.inputs["Metallic"].default_value}
        pbr=item["pbrMetallicRoughness"]
        assert max(abs(a-b) for a,b in zip(source["baseColorFactor"],pbr["baseColorFactor"]))<1e-6
        assert all(abs(source[k]-pbr[k])<1e-6 for k in ("roughnessFactor","metallicFactor"))
        report.append({"name":item["name"],"source":source,"glb":pbr})
    return report


def saved_source_audit():
    source=ROOT/"assets/v3/blender/small-carton.blend"
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    root=bpy.data.objects[ASSET]
    meshes=[o for o in root.children_recursive if o.type=="MESH"]
    bevels=sum(any(m.type=="BEVEL" for m in o.modifiers) for o in meshes)
    assert len(meshes)==19 and bevels==17
    assert root["units_per_handling_unit"]==24 and not any(o.name.startswith("unit_") for o in meshes)
    material_factors=material_audit(root)
    assert before==hashlib.sha256(source.read_bytes()).hexdigest()
    report={"asset_id":ASSET,"mode":"read_only_saved_blend","source_sha256":before,
            "editable_meshes":len(meshes),"editable_box_bevels":bevels,"unbevelled_thin_ink_arrows":2,
            "source_not_modified":True,"baked_contents_instances":0,"materials_matching_glb":len(material_factors),
            "actual_material_factors":material_factors}
    (ITERATION/"saved-source-checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("M06_1_SAVED_SOURCE_CHECKS "+json.dumps({"editable_meshes":len(meshes),"bevels":bevels,"materials":len(material_factors),"source_unchanged":True}))


if __name__=="__main__":
    if not bpy.app.background:raise RuntimeError("Task background Blender only")
    if "--audit-source" in sys.argv:
        saved_source_audit()
        sys.exit(0)
    reset();root=build();report=verify(root)
    ITERATION.mkdir(parents=True,exist_ok=True);SPEC.parent.mkdir(parents=True,exist_ok=True)
    SPEC.write_text(json.dumps(specification(),indent=2)+"\n",encoding="utf-8")
    finish(ASSET,root)
    report["source_glb_material_factors_equal"]=material_audit(root)
    (ITERATION/"mesh-checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    for path in (ROOT/"assets/v3/blender/small-carton.blend",ROOT/"assets/v3/blender/small-carton.stats.json",ROOT/"frontend/public/models/v3/small-carton.glb",SPEC,Path(__file__)):
        shutil.copy2(path,ITERATION/path.name)
    print("M06_1_MESH_CHECKS "+json.dumps({k:report[k] for k in ("positive_closed_consistently_outward_parts","actual_part_contact_edges","unchanged_C02_unit_AABBs_clear","empty_hollow_interior","actual_solid_volume_m3")}))
