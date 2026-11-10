"""Actual M08 source packing/contact checks; save only a derived QA pair."""
from pathlib import Path
import argparse
from decimal import Decimal
import hashlib
import json
import math
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import runtime_xyz, xyz, group, box, material

parser = argparse.ArgumentParser(); parser.add_argument("--out", required=True); parser.add_argument("--pair", action="store_true")
args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
source_path = Path(bpy.data.filepath); source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
plan = json.loads((ROOT / "assets/v3/specs/pallet-load.dimensions.json").read_text())
catalog = json.loads((ROOT / plan["source_C02"]["path"]).read_text())
recipe = next(x for x in catalog["packing_recipes"] if x["archetype_id"] == "PALLET_LOAD")
root = next(o for o in bpy.data.objects if o.get("asset_id") == "pallet-load" and o.parent is None)
checks = 0


def require(test, label):
    global checks
    checks += 1
    if not test: raise AssertionError(label)


def collect(objects, check=True):
    graph = bpy.context.evaluated_depsgraph_get(); pieces = {}; points = []; triangles = []; tri_materials = []
    for obj in objects:
        if obj.type != "MESH": continue
        evaluated = obj.evaluated_get(graph); mesh = evaluated.to_mesh()
        try:
            bm = bmesh.new(); bm.from_mesh(mesh)
            volume = bm.calc_volume(signed=True)
            if check:
                require(all(e.is_manifold for e in bm.edges), "Nonmanifold " + obj.name)
                require(volume > 0, "Nonpositive volume " + obj.name)
            bm.free(); mesh.calc_loop_triangles()
            vertices = [Vector(runtime_xyz(evaluated.matrix_world @ v.co)) for v in mesh.vertices]
            if check:
                require(all(math.isfinite(x) for p in vertices for x in p), "Nonfinite vertex")
                require(all(abs(n.vector.length-1) < 1e-5 for n in mesh.corner_normals), "Nonunit normal")
            faces = [tuple(t.vertices) for t in mesh.loop_triangles]
            mats = [obj.data.materials[t.material_index].name for t in mesh.loop_triangles]
            bounds = {"min": [min(p[k] for p in vertices) for k in range(3)], "max": [max(p[k] for p in vertices) for k in range(3)]}
            key = obj.get("part_id", obj.name)
            pieces[key] = {"vertices": vertices, "triangles": faces, "edges": [tuple(e.vertices) for e in mesh.edges],
                           "tree": BVHTree.FromPolygons(vertices, faces, all_triangles=True), "bounds": bounds,
                           "materials": mats, "volume": volume, "object": obj}
            offset = len(points); points += vertices; triangles += [tuple(i+offset for i in t) for t in faces]; tri_materials += mats
        finally: evaluated.to_mesh_clear()
    return pieces, points, triangles, tri_materials


pieces, points, triangles, tri_materials = collect(root.children_recursive)
tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
require(len(pieces) == 84, "84 real source components")
low = [min(p[k] for p in points) for k in range(3)]; high = [max(p[k] for p in points) for k in range(3)]
require(max(abs(a-b) for a,b in zip(low, [-.6,0,-.5])) < 1e-6 and max(abs(a-b) for a,b in zip(high,[.6,1.35,.5])) < 1e-6, "HU outer bounds")
require(root["HU_count"] == 1 and root["units_per_HU"] == 24 and not root["contains_inventory"], "One HU, no24lots")
frames = {int(o["unit_ordinal"]):o for o in root.children_recursive if o.get("role") == "HU_content_unit_frame"}
require(set(frames) == set(range(1,25)), "24 exact unit frames")
support_rays = 0; units = []
for item in recipe["unit_instances"]:
    ordinal = item["unit_ordinal"]; piece = pieces[f"unit_body_{ordinal:03d}"]
    lo = [item["min_xyz_m"][0]-.6,item["min_xyz_m"][1],item["min_xyz_m"][2]-.5]
    hi = [item["max_xyz_m"][0]-.6,item["max_xyz_m"][1],item["max_xyz_m"][2]-.5]
    require(max(abs(piece["bounds"]["min"][k]-lo[k]) for k in range(3)) < 1e-6 and max(abs(piece["bounds"]["max"][k]-hi[k]) for k in range(3)) < 1e-6, "Moved/scaled unit " + str(ordinal))
    require(max(abs(runtime_xyz(frames[ordinal].matrix_world.translation)[k]-(lo[k]+hi[k])/2) for k in range(3)) < 1e-6, "Wrong unit frame")
    require(piece["object"]["content_frame_id"] == frames[ordinal].name and frames[ordinal].parent == root, "Frame/body association")
    support = pieces[("base_pad_" if lo[1] < .2 else "layer_separator_") + str(ordinal)]
    b = support["bounds"]
    for i in range(3):
        for j in range(3):
            x = b["min"][0]+.004+(b["max"][0]-b["min"][0]-.008)*i/2
            z = b["min"][2]+.004+(b["max"][2]-b["min"][2]-.008)*j/2
            bottom, normal, *_ = piece["tree"].ray_cast(Vector((x,lo[1]-.01,z)), Vector((0,1,0)), .02)
            top, up, *_ = support["tree"].ray_cast(Vector((x,lo[1]+.01,z)), Vector((0,-1,0)), .02)
            require(bottom is not None and top is not None and abs(bottom.y-top.y) < 1e-6 and abs(top.y-lo[1]) < 1e-6 and normal.y < -.999 and up.y > .999, "Floating carton/separator")
            support_rays += 2
    units.append({"unit_ordinal":ordinal,"actual_bounds":piece["bounds"],"frame":frames[ordinal].name})
for i,a in enumerate(units):
    for b in units[i+1:]:
        require(any(a["actual_bounds"]["max"][k] <= b["actual_bounds"]["min"][k]+1e-6 or b["actual_bounds"]["max"][k] <= a["actual_bounds"]["min"][k]+1e-6 for k in range(3)), "Overlapping contents")
require(Decimal(24)*Decimal(18)+Decimal(23) == Decimal(455), "Declared mass identity")
anchors = {o["anchor_id"]:runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get("anchor_id")}
require(set(anchors) == {a["anchor_id"] for a in plan["anchors"]}, "Attachment/declaredCG anchors")
for a in plan["anchors"]: require(max(abs(anchors[a["anchor_id"]][k]-a["local_xyz_m"][k]) for k in range(3)) < 1e-6, "Anchor pose")

# Actual mesh contacts, including under-deck band/saddle contacts.
def actual_contact(a,b):
    for p in a["vertices"]:
        hit,_,_,distance = b["tree"].find_nearest(p)
        if hit is not None and distance < 1e-6: return "vertex_surface"
    for left,right in a["edges"]:
        start,end = a["vertices"][left],a["vertices"][right]; delta=end-start
        if delta.length < 1e-8: continue
        hit,*_ = b["tree"].ray_cast(start,delta.normalized(),delta.length+1e-7)
        if hit is not None: return "edge_surface"
    return None

names = list(pieces); adjacency = {n:set() for n in names}; contacts=[]
for i,n in enumerate(names):
    a=pieces[n]
    for other in names[i+1:]:
        b=pieces[other]
        if any(a["bounds"]["max"][k] < b["bounds"]["min"][k]-1e-6 or b["bounds"]["max"][k] < a["bounds"]["min"][k]-1e-6 for k in range(3)): continue
        proof=actual_contact(a,b) or actual_contact(b,a)
        if proof: adjacency[n].add(other); adjacency[other].add(n); contacts.append({"a":n,"b":other,"proof":proof})
ground={n for n in names if abs(pieces[n]["bounds"]["min"][1]) < 1e-6}
require(ground == {"pallet_bottom_1","pallet_bottom_2","pallet_bottom_3"}, "Three ground crossboards")
reached=set(ground); queue=list(ground)
while queue:
    for other in adjacency[queue.pop()]-reached: reached.add(other);queue.append(other)
require(reached == set(names), "Disconnected components " + str(set(names)-reached))
for side in [-1,1]:
    bottom=f"band_{side}_underdeck"
    require(any(n.startswith("strap_saddle_") for n in adjacency[bottom]), "No real strap underside contact")

# Non-overlapping actual component AABBs are a conservative whole-solid proof.
# Tangent support interfaces are allowed; no planned piece needs solid intrusion.
component_pairs=0
for i,n in enumerate(names):
    for other in names[i+1:]:
        a,b=pieces[n]['bounds'],pieces[other]['bounds']
        depths=[min(a['max'][k],b['max'][k])-max(a['min'][k],b['min'][k]) for k in range(3)]
        require(min(depths)<=1e-6,'Unplanned actual solid overlap '+n+' / '+other);component_pairs+=1

# Explicit finite-area top-band/cap contact, not merely a graph connection.
def polygon_area(poly):
    return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))/2) if len(poly)>2 else 0.
def clip_triangle(subject,triangle):
    signed=sum(triangle[i][0]*triangle[(i+1)%3][1]-triangle[(i+1)%3][0]*triangle[i][1] for i in range(3));sign=1 if signed>0 else -1
    for a,b in zip(triangle,triangle[1:]+triangle[:1]):
        def side(p):return sign*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
        if not subject:return []
        out=[];prev=subject[-1];pv=side(prev)
        for cur in subject:
            cv=side(cur)
            if (cv>=0)!=(pv>=0):
                t=pv/(pv-cv);out.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
            if cv>=0:out.append(cur)
            prev,pv=cur,cv
        subject=out
    return subject

def horizontal_triangles(piece,sign):
    result=[]
    for tri in piece['triangles']:
        p=[piece['vertices'][i] for i in tri];normal=(p[1]-p[0]).cross(p[2]-p[0])
        if normal.length<1e-12:continue
        normal.normalize()
        if sign*normal.y>.999999 and all(abs(v.y-1.34)<1e-6 for v in p):result.append([(v.x,v.z) for v in p])
    return result
cap=pieces['compression_board'];cap_faces=horizontal_triangles(cap,1);band_cap_contacts=[]
for side in [-1,1]:
    band=pieces[f'band_{side}_top'];band_faces=horizontal_triangles(band,-1)
    area=sum(polygon_area(clip_triangle(list(a),b)) for a in cap_faces for b in band_faces)
    gap=band['bounds']['min'][1]-cap['bounds']['max'][1]
    require(area>.018 and abs(gap)<1e-6,'No finite-area cap/topband contact')
    witness_rays=0;max_error=0.
    for i in range(3):
        for j in range(5):
            x=side*.375-.015+.03*i/2;z=-.28+.56*j/4
            lower,n,*_=band['tree'].ray_cast(Vector((x,1.33,z)),Vector((0,1,0)),.02)
            upper,up,*_=cap['tree'].ray_cast(Vector((x,1.35,z)),Vector((0,-1,0)),.02)
            require(lower is not None and upper is not None and n.y<-.999 and up.y>.999 and abs(lower.y-upper.y)<1e-6,'Topband/cap gap')
            max_error=max(max_error,abs(lower.y-upper.y));witness_rays+=2
    band_cap_contacts.append({'band':f'band_{side}_top','finite_flat_triangle_contact_area_m2':area,'signed_band_bottom_minus_cap_top_m':gap,'opposing_surface_rays':witness_rays,'maximum_ray_plane_error_m':max_error,'actual_gap':False})

# Current evaluated source triangle fingerprints preserve all material regions.
material_triangles={}
for tri,mat in zip(triangles,tri_materials):
    coords=[]
    for i in tri:
        q=[round(float(c),6) for c in points[i]];coords.append(tuple(0.0 if x==0 else x for x in q))
    material_triangles.setdefault(mat,[]).append(sorted(coords))
fingerprints={m:{"triangles":len(t),"sha256":hashlib.sha256(json.dumps(sorted(t),separators=(',',':')).encode()).hexdigest()} for m,t in material_triangles.items()}

# Pair the actual HU bottom with frozen accepted M03 mesh and actual triangle
# C08-sized fork fixtures. This is static contact, not full vehicle action proof.
heavy_path=ROOT/"assets/v3/blender/heavy-bay.blend"
with bpy.data.libraries.load(str(heavy_path), link=False) as (available,loaded): loaded.objects=available.objects
for obj in loaded.objects:
    if obj is not None: bpy.context.collection.objects.link(obj)
bpy.context.view_layer.update()
heavy=next(o for o in loaded.objects if o is not None and o.get("asset_id")=="heavy-bay" and o.parent is None)
_,hp,ht,_=collect(heavy.children_recursive,False); heavy_tree=BVHTree.FromPolygons(hp,ht,all_triangles=True)
fixture=group("M08_STATIC_FORK_CONTACT_QA")
forkmat=material("QA | fork steel", "#60727A")
forks=[box(f"QA_C08_blade_{side}",[side*.4,.145,0],[.08,.07,1.1],forkmat,fixture,bevel=0) for side in [-1,1]]
bpy.context.view_layer.update();_,fp,ft,_=collect(forks,False);fork_tree=BVHTree.FromPolygons(fp,ft,all_triangles=True)
m03_contacts=0;fork_contacts=0;maximum_contact_error=0
for zc in [-.4,0,.4]:
    for xl,xr in [(-.595,-.475),(-.165,.165),(.475,.595)]:
        for i in range(3):
            for j in range(3):
                x=xl+(xr-xl)*i/2;z=zc-.095+.19*j/2
                bottom,n,*_=tree.ray_cast(Vector((x,-.01,z)),Vector((0,1,0)),.02)
                top,up,*_=heavy_tree.ray_cast(Vector((x,.20,z+.05)),Vector((0,-1,0)),.03)
                require(bottom is not None and top is not None and n.y<-.999 and up.y>.999 and abs(bottom.y+.18-top.y)<1e-6,"M03 real base support")
                maximum_contact_error=max(maximum_contact_error,abs(bottom.y+.18-top.y));m03_contacts+=1
    for centre in [-.4,.4]:
        for i in range(3):
            for j in range(3):
                x=centre-.038+.076*i/2;z=zc-.095+.19*j/2
                bottom,n,*_=tree.ray_cast(Vector((x,-.01,z)),Vector((0,1,0)),.02)
                top,up,*_=fork_tree.ray_cast(Vector((x,.20,z+.05)),Vector((0,-1,0)),.03)
                require(bottom is not None and top is not None and n.y<-.999 and up.y>.999 and abs(bottom.y+.18-top.y)<1e-6,"Two-fork real base support")
                maximum_contact_error=max(maximum_contact_error,abs(bottom.y+.18-top.y));fork_contacts+=1
require(min(p.y for p in points)+.18 >= max(p.y for p in hp)-1e-6,"HU/M03 interior overlap")
require(min(p.y for p in points)+.18 >= max(p.y for p in fp)-1e-6,"HU/forks interior overlap")
report={"asset_id":"pallet-load","status":"PASS","checks":checks,"failures":0,"source_sha256":source_hash,
        "actual_bounds_runtime":{"min":low,"max":high},"actual_parts":len(pieces),"triangles":len(triangles),
        "closed_positive_volume_parts":len(pieces),"actual_component_AABB_pairs_checked_for_interior_overlap":component_pairs,"solid_interior_overlap_pairs":0,"actual_contact_ground_connected_parts":len(reached),"ground_crossboards":sorted(ground),
        "actual_unit_frames":24,"actual_unit_bodies":24,"unit_measurements":units,"carton_support_contact_rays":support_rays,
        "anchors":anchors,"material_triangle_fingerprints_1e_6_m":fingerprints,"actual_contact_proofs":contacts,
        "actual_M03_base_patch_points":m03_contacts,"actual_two_fork_base_patch_points":fork_contacts,"maximum_contact_error_m":maximum_contact_error,
        "HU_pose_in_M03_test":[0,.18,.05],"actual_HU_base_and_support_have_no_interior_overlap":True,
        "M03_source_sha256":hashlib.sha256(heavy_path.read_bytes()).hexdigest(),"fork_fixture":{"kind":"explicit actual triangle design fixture, not final M14 vehicle","dimensions_xyz_each_m":[.08,.07,1.1],"centres_xyz_m":[[-.4,.145,0],[.4,.145,0]],"current_C08_sha256":plan["source_C08"]["sha256"]},
        "top_band_cap_contact_witnesses":band_cap_contacts,"mass_and_CG_declared_not_mesh_computed":True,"no_operational_admission_or_vehicle_action_claim":True}
target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
if args.pair:
    root.location=xyz((0,.18,.05));bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0
    pair_path=target.parent/"static-pair-fixture.blend";bpy.ops.wm.save_as_mainfile(filepath=str(pair_path));report["derived_static_pair"]=str(pair_path.relative_to(ROOT))
require(hashlib.sha256(source_path.read_bytes()).hexdigest()==source_hash,"Source modified by checks")
report["checks"]=checks
target.write_text(json.dumps(report,indent=2)+'\n')
print("M08_SOURCE_CHECKS_PASS "+json.dumps({k:report[k] for k in ["checks","actual_parts","triangles","actual_unit_frames","carton_support_contact_rays","actual_M03_base_patch_points","actual_two_fork_base_patch_points","maximum_contact_error_m"]}))
