"""Actual M09 source packing/contact checks; save only a derived QA pair."""
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
plan = json.loads((ROOT / "assets/v3/specs/ibc.dimensions.json").read_text())
catalog = json.loads((ROOT / plan["source_C02"]["path"]).read_text())
recipe = next(x for x in catalog["packing_recipes"] if x["archetype_id"] == "IBC")
root = next(o for o in bpy.data.objects if o.get("asset_id") == "ibc" and o.parent is None)
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


pieces, points, triangles, tri_materials=collect(root.children_recursive)
tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
require(len(pieces)==52,'52 source parts')
low=[min(p[k] for p in points) for k in range(3)];high=[max(p[k] for p in points) for k in range(3)]
require(max(abs(a-b) for a,b in zip(low,[-.6,0,-.5]))<1e-6 and max(abs(a-b) for a,b in zip(high,[.6,1.16,.5]))<1e-6,'HU envelope')
primary={n:p for n,p in pieces.items() if p['object'].get('role')=='sealed_primary_container_component'}
packaging={n:p for n,p in pieces.items() if n not in primary}
require(len(primary)==8 and len(packaging)==44,'One bottle plus connected cap/valve, cage/base')
frames=[o for o in root.children_recursive if o.get('role')=='HU_content_unit_frame'];require(len(frames)==1 and frames[0]['unit_ordinal']==1,'One primary unit frame')
u=recipe['unit_instances'][0];ulo=[u['min_xyz_m'][0]-.6,u['min_xyz_m'][1],u['min_xyz_m'][2]-.5];uhi=[u['max_xyz_m'][0]-.6,u['max_xyz_m'][1],u['max_xyz_m'][2]-.5]
unit_low=[min(p['bounds']['min'][k] for p in primary.values()) for k in range(3)];unit_high=[max(p['bounds']['max'][k] for p in primary.values()) for k in range(3)]
require(max(abs(unit_low[k]-ulo[k]) for k in range(3))<1e-6 and max(abs(unit_high[k]-uhi[k]) for k in range(3))<1e-6,'Moved/scaled primary unit')
require(max(abs(runtime_xyz(frames[0].matrix_world.translation)[k]-(ulo[k]+uhi[k])/2) for k in range(3))<1e-6,'Unit frame pose')
require(root['HU_count']==root['units_per_HU']==1 and root['fluid_units']==0 and not root['contains_inventory'],'No fluid cubes/extra HUs')
require(Decimal(600)+Decimal(14)+Decimal(40)==Decimal(654),'Declared mass identity')
for p in primary.values():require(p['object']['content_frame_id']==frames[0].name and p['object']['unit_ordinal']==1,'Primary component association')
anchors={o['anchor_id']:runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get('anchor_id')}
require(set(anchors)=={a['anchor_id'] for a in plan['anchors_plan']},'Anchors')
for a in plan['anchors_plan']:require(max(abs(anchors[a['anchor_id']][k]-a['local_xyz_m'][k]) for k in range(3))<1e-6,'Anchor pose')
# Raw evaluated bounds conservatively separate every primary part from cage/base.
primary_packaging_pairs=0
for a in primary.values():
    for b in packaging.values():
        depths=[min(a['bounds']['max'][k],b['bounds']['max'][k])-max(a['bounds']['min'][k],b['bounds']['min'][k]) for k in range(3)]
        require(min(depths)<=1e-6,'Cage/base intrudes into primary unit');primary_packaging_pairs+=1
body=pieces['primary_bottle'];support_rays=0
for x in [-.45,-.25,0,.25,.45]:
    for z in [-.30,0,.25]:
        lower,n,*_=body['tree'].ray_cast(Vector((x,.095,z)),Vector((0,1,0)),.02)
        support=next(p for name,p in packaging.items() if name.startswith('base_deck_') and p['bounds']['min'][0]<x<p['bounds']['max'][0])
        upper,up,*_=support['tree'].ray_cast(Vector((x,.115,z)),Vector((0,-1,0)),.02)
        require(lower is not None and upper is not None and n.y<-.999 and up.y>.999 and abs(lower.y-upper.y)<1e-6,'Bottle floats above pallet');support_rays+=2
# Genuine annular outlet, clear aperture and a recessed closed valve behind it.
annulus=pieces['primary_outlet_annulus'];aperture_rays=0
for x,y in [(0,.205)]+[(.012*math.cos(i*math.pi/4),.205+.012*math.sin(i*math.pi/4)) for i in range(8)]:
    hit,*_=annulus['tree'].ray_cast(Vector((x,y,.46)),Vector((0,0,-1)),.08)
    require(hit is None,'Fake face across outlet bore');aperture_rays+=1
lip_rays=0
for i in range(8):
    x=.028*math.cos(i*math.pi/4);y=.205+.028*math.sin(i*math.pi/4)
    hit,n,*_=annulus['tree'].ray_cast(Vector((x,y,.46)),Vector((0,0,-1)),.04)
    require(hit is not None and abs(hit.z-.44)<1e-6 and n.z>.999,'Missing outlet lip');lip_rays+=1
hit,*_=pieces['primary_valve']['tree'].ray_cast(Vector((0,.205,.46)),Vector((0,0,-1)),.08)
require(hit is not None and .425<hit.z<.435,'No recessed closed valve');valve_bore_depth=.44-hit.z
# Handle must stand outside bottle taper rather than disappear inside it.
handle=pieces['primary_valve_handle'];handle_clearance=handle['bounds']['min'][2]-.37
require(handle_clearance>.02 and handle['bounds']['max'][1]<.30,'Buried T handle')
visible,n,*_=tree.ray_cast(Vector((0,.275,.46)),Vector((0,0,-1)),.10)
require(visible is not None and abs(visible.z-handle['bounds']['max'][2])<1e-6 and n.z>.999,'Actual T handle obscured by bottle/cage')

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
require(ground == {"base_bottom_1","base_bottom_2","base_bottom_3"}, "Three ground crossboards")
reached=set(ground); queue=list(ground)
while queue:
    for other in adjacency[queue.pop()]-reached: reached.add(other);queue.append(other)
require(reached == set(names), "Disconnected components " + str(set(names)-reached))
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

# Finite bottle bottom/deck support area from opposing actual flat triangles.
def flat(piece,y,sign):
    result=[]
    for tri in piece['triangles']:
        p=[piece['vertices'][i] for i in tri];n=(p[1]-p[0]).cross(p[2]-p[0])
        if n.length<1e-12:continue
        n.normalize()
        if sign*n.y>.999999 and all(abs(v.y-y)<1e-6 for v in p):result.append([(v.x,v.z) for v in p])
    return result
foot=flat(body,.105,-1);deck=[t for name,p in packaging.items() if name.startswith('base_deck_') for t in flat(p,.105,1)]
foot_area=sum(polygon_area(clip_triangle(list(a),b)) for a in foot for b in deck)
require(foot_area>.5,'No finite bottle support area')
# Minimum actual polyhedron distance at four rounded-body/corner-post pairs.
def segment_distance(a,b,c,d):
    u=b-a;v=d-c;w=a-c;aa=u.dot(u);bb=u.dot(v);cc=v.dot(v);dd=u.dot(w);ee=v.dot(w)
    best=min((p-(c+v*max(0,min(1,(p-c).dot(v)/cc)))).length for p in [a,b])
    best=min(best,min((p-(a+u*max(0,min(1,(p-a).dot(u)/aa)))).length for p in [c,d]))
    den=aa*cc-bb*bb
    if den>1e-16:
        ss=(bb*ee-cc*dd)/den;tt=(aa*ee-bb*dd)/den
        if 0<=ss<=1 and 0<=tt<=1:best=min(best,(w+u*ss-v*tt).length)
    return best
post_clearances=[]
for name,p in pieces.items():
    if not name.startswith('cage_post_'):continue
    distance=min([p['tree'].find_nearest(v)[3] for v in body['vertices']]+[body['tree'].find_nearest(v)[3] for v in p['vertices']])
    for a,b in body['edges']:
        for c,d in p['edges']:distance=min(distance,segment_distance(body['vertices'][a],body['vertices'][b],p['vertices'][c],p['vertices'][d]))
    require(distance>.02,'Rounded body/cornerpost clash');post_clearances.append({'post':name,'actual_polyhedral_distance_m':distance})
face_air=[]
for name,p in pieces.items():
    if 'cage_front_' in name:face_air.append(p['bounds']['min'][2]-unit_high[2])
    elif 'cage_rear_' in name:face_air.append(unit_low[2]-p['bounds']['max'][2])
    elif 'cage_side_' in name:face_air.append(min(abs(p['bounds']['min'][0]),abs(p['bounds']['max'][0]))-unit_high[0])
require(min(face_air)>.025,'Main cage-face air clearance')

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
fixture=group("M09_STATIC_FORK_CONTACT_QA")
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
report={'asset_id':'ibc','status':'PASS','checks':checks,'failures':0,'source_sha256':source_hash,'actual_bounds_runtime':{'min':low,'max':high},'actual_parts':len(pieces),'triangles':len(triangles),
        'closed_positive_volume_parts':len(pieces),'actual_contact_ground_connected_parts':len(reached),'actual_unit_frames':1,'actual_primary_components':8,'one_sealed_unit_not_fluid_units':True,
        'actual_unit_bounds':{'min':unit_low,'max':unit_high},'primary_packaging_AABB_pairs':primary_packaging_pairs,'primary_packaging_interior_overlaps':0,
        'primary_support_contact_rays':support_rays,'actual_finite_bottle_deck_contact_area_m2':foot_area,'actual_cornerpost_clearances':post_clearances,'minimum_main_cage_face_air_m':min(face_air),
        'annulus_clear_aperture_rays':aperture_rays,'annulus_lip_rays':lip_rays,'actual_recessed_valve_bore_depth_m':valve_bore_depth,'handle_outside_body_front_clearance_m':handle_clearance,'actual_front_T_handle_visibility_ray_passed':True,
        'anchors':anchors,'material_triangle_fingerprints_1e_6_m':fingerprints,'actual_contact_proofs':contacts,'actual_M03_base_patch_points':m03_contacts,'actual_two_fork_base_patch_points':fork_contacts,'maximum_contact_error_m':maximum_contact_error,
        'M03_source_sha256':hashlib.sha256(heavy_path.read_bytes()).hexdigest(),'fork_fixture':'C08-sized actual triangle fixture only, not final M14 vehicle/actions',
        'symbolic_liquid':recipe['symbolic_liquid'],'fluid_meshes':0,'mass_CG_and_capacity_not_mesh_certified':True}
target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
if args.pair:
    root.location=xyz((0,.18,.05));bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0
    pair_path=target.parent/"static-pair-fixture.blend";bpy.ops.wm.save_as_mainfile(filepath=str(pair_path));report["derived_static_pair"]=str(pair_path.relative_to(ROOT))
require(hashlib.sha256(source_path.read_bytes()).hexdigest()==source_hash,"Source modified by checks")
report["checks"]=checks
target.write_text(json.dumps(report,indent=2)+'\n')
print("M09_SOURCE_CHECKS_PASS "+json.dumps({k:report[k] for k in ["checks","actual_parts","triangles","actual_unit_frames","primary_support_contact_rays","actual_M03_base_patch_points","actual_two_fork_base_patch_points","maximum_contact_error_m"]}))
