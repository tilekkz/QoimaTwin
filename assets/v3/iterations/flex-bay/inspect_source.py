"""Read-only M05 evaluated source/cavity/support inspection; no render or save."""
from pathlib import Path
import json
import math
import sys
import hashlib
import argparse

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import runtime_xyz

plan = json.loads((ROOT / "assets/v3/specs/flex-bay.dimensions.json").read_text())
root = next(o for o in bpy.data.objects if o.get("asset_id") == "flex-bay" and o.parent is None)
graph = bpy.context.evaluated_depsgraph_get()
pieces = {};all_vertices = [];all_triangles = [];norm_lengths = [];checks = 0


def require(test, label):
    global checks
    checks += 1
    if not test:
        raise AssertionError(label)


for obj in root.children_recursive:
    if obj.type != "MESH":
        continue
    evaluated = obj.evaluated_get(graph);mesh = evaluated.to_mesh()
    try:
        bm = bmesh.new();bm.from_mesh(mesh)
        require(all(e.is_manifold for e in bm.edges), "Nonmanifold: " + obj.name)
        volume = bm.calc_volume(signed=True);bm.free()
        require(volume > 0, "Nonpositive volume: " + obj.name)
        mesh.calc_loop_triangles()
        vertices = [Vector(runtime_xyz(evaluated.matrix_world @ v.co)) for v in mesh.vertices]
        triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
        edges = [tuple(e.vertices) for e in mesh.edges]
        require(all(math.isfinite(v) for p in vertices for v in p), "Nonfinite vertex")
        normals = [n.vector.length for n in mesh.corner_normals];norm_lengths += normals
        require(all(abs(n - 1) < 1e-5 for n in normals), "Bad normals")
        bounds = {"min": [min(v[k] for v in vertices) for k in range(3)], "max": [max(v[k] for v in vertices) for k in range(3)]}
        tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
        pieces[obj["part_id"]] = {"vertices": vertices, "triangles": triangles, "edges": edges,
                                 "bounds": bounds, "tree": tree, "volume": volume, "material": obj.data.materials[0].name}
        offset = len(all_vertices);all_vertices += vertices
        all_triangles += [tuple(offset + i for i in t) for t in triangles]
    finally:
        evaluated.to_mesh_clear()
tree = BVHTree.FromPolygons(all_vertices, all_triangles, all_triangles=True)
require(len(pieces) == len(plan["parts"]) == 15, "Part count")
low = [min(v[k] for v in all_vertices) for k in range(3)];high = [max(v[k] for v in all_vertices) for k in range(3)]
require(all(abs(low[k] - plan["bounds_local_xyz_m"]["min"][k]) < 1e-6 and abs(high[k] - plan["bounds_local_xyz_m"]["max"][k]) < 1e-6 for k in range(3)), "Outer bounds")
anchors = {o["anchor_id"]: runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get("anchor_id")}
require(set(anchors) == {a["anchor_id"] for a in plan["anchors"]}, "Anchor set")
floor_rays = 0;clear_segments = 0;measurements = []
for a in plan["anchors"]:
    p = anchors[a["anchor_id"]];require(max(abs(p[k] - a["local_xyz_m"][k]) for k in range(3)) < 1e-6, "Anchor position")
    b = a["usable_bounds_module_local"];lo,hi = b["min"],b["max"]
    for i in range(21):
        for j in range(21):
            x = lo[0] + 1e-5 + (hi[0]-lo[0]-2e-5)*i/20
            z = lo[2] + 1e-5 + (hi[2]-lo[2]-2e-5)*j/20
            hit,normal,_,_ = tree.ray_cast(Vector((x,p[1]+.2,z)),Vector((0,-1,0)),.21)
            require(hit is not None and abs(hit.y-p[1]) < 1e-6 and normal.y > .999, "Floor support " + a["anchor_id"])
            floor_rays += 1
    for axis in range(3):
        other = [k for k in range(3) if k != axis]
        for i in range(11):
            for j in range(11):
                start=[0,0,0];start[axis]=lo[axis]+1e-5
                for k,t in zip(other,(i,j)):
                    start[k]=lo[k]+1e-5+(hi[k]-lo[k]-2e-5)*t/10
                direction=[0,0,0];direction[axis]=1
                hit,*_=tree.ray_cast(Vector(start),Vector(direction),hi[axis]-lo[axis]-2e-5)
                require(hit is None,"Blocked usable interior " + a["anchor_id"]);clear_segments += 1
    centre=Vector((p[0],p[1]+.30,p[2]))
    for direction in [(-1,0,0),(1,0,0),(0,0,1),(0,1,0)]:
        hit,*_=tree.ray_cast(centre,Vector(direction),1.0)
        require(hit is None,"Open front/sides/top obstructed")
    measurements.append({"anchor_id":a["anchor_id"],"clear_dimensions_tested_xyz_m":a["usable_dimensions_xyz_m"],"support_y_m":p[1],"open_front_sides_top":True})

# Actual triangle edge/surface or vertex/surface contacts, not only touching AABBs.
names=list(pieces);adj={name:set() for name in names};contacts=[]
def actual_contact(a,b):
    for p in a["vertices"]:
        hit,_,_,distance=b["tree"].find_nearest(p)
        if hit is not None and distance < 1e-6:return "vertex_surface"
    for left,right in a["edges"]:
        start,end=a["vertices"][left],a["vertices"][right];delta=end-start
        if delta.length < 1e-8:continue
        hit,*_=b["tree"].ray_cast(start,delta.normalized(),delta.length+1e-7)
        if hit is not None:return "edge_surface"
    return None
for i,name in enumerate(names):
    a=pieces[name]
    for other in names[i+1:]:
        b=pieces[other]
        if any(a["bounds"]["max"][k] < b["bounds"]["min"][k]-1e-6 or b["bounds"]["max"][k] < a["bounds"]["min"][k]-1e-6 for k in range(3)):continue
        proof=actual_contact(a,b) or actual_contact(b,a)
        if proof:adj[name].add(other);adj[other].add(name);contacts.append({"a":name,"b":other,"proof":proof})
ground={n for n in names if abs(pieces[n]["bounds"]["min"][1])<1e-6}
require(len(ground)==8,"Grounded feet")
reached=set(ground);queue=list(ground)
while queue:
    for other in adj[queue.pop()]-reached:reached.add(other);queue.append(other)
require(reached==set(names),"Unsupported pieces: "+str(set(names)-reached))

# Coplanar top triangles projected to X/Z; zero-area boundary sharing is allowed.
def area(poly):return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))/2) if len(poly)>2 else 0
def clip(subject,tri):
    signed=sum(tri[i][0]*tri[(i+1)%3][1]-tri[(i+1)%3][0]*tri[i][1] for i in range(3));sign=1 if signed>0 else -1
    for a,b in zip(tri,tri[1:]+tri[:1]):
        def side(p):return sign*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
        output=[]
        if not subject:return []
        prev=subject[-1];pv=side(prev)
        for cur in subject:
            cv=side(cur)
            if (cv>=0)!=(pv>=0):
                t=pv/(pv-cv);output.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
            if cv>=0:output.append(cur)
            prev,pv=cur,cv
        subject=output
    return subject
# Compare only same-facing coplanar triangles: opposite-facing hidden
# base/deck and butt-contact interfaces are intentionally valid.
flat=[]
for name,piece in pieces.items():
    for tri in piece["triangles"]:
        p=[piece["vertices"][i] for i in tri];normal=(p[1]-p[0]).cross(p[2]-p[0])
        if normal.length<1e-12:continue
        normal.normalize();axis=max(range(3),key=lambda k:abs(normal[k]))
        if abs(normal[axis])<.999999:continue
        other=[k for k in range(3) if k!=axis]
        flat.append((name,axis,1 if normal[axis]>0 else -1,sum(v[axis] for v in p)/3,[(v[other[0]],v[other[1]]) for v in p]))
maximum_overlap=0;same_plane_pairs=0
for i,a in enumerate(flat):
    for b in flat[i+1:]:
        if a[0]==b[0] or a[1:3]!=b[1:3] or abs(a[3]-b[3])>1e-6:continue
        overlap=area(clip(a[4],b[4]));maximum_overlap=max(maximum_overlap,overlap);same_plane_pairs+=1
require(maximum_overlap<1e-8,"Exposed same-facing coplanar overlap")
top_overlap={"same_facing_coplanar_triangle_pairs_tested":same_plane_pairs,"maximum_overlap_area_m2":maximum_overlap,"numeric_area_tolerance_m2":1e-8,"opposite_hidden_contact_faces_allowed":True}
material_triangles={}
for piece in pieces.values():
    for tri in piece["triangles"]:
        vertices=[]
        for i in tri:
            point=[round(float(c),6) for c in piece["vertices"][i]]
            vertices.append(tuple(0.0 if c==0 else c for c in point))
        material_triangles.setdefault(piece["material"],[]).append(sorted(vertices))
fingerprints={name:{"triangles":len(tris),"sha256":hashlib.sha256(json.dumps(sorted(tris),sort_keys=True,separators=(',',':')).encode()).hexdigest()} for name,tris in material_triangles.items()}
report={"asset_id":"flex-bay","actual_evaluated_parts":len(pieces),"triangles":len(all_triangles),"checks":checks,"failures":0,
        "source_sha256":hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
        "material_triangle_fingerprints_1e_6_m":fingerprints,
        "actual_bounds_runtime":{"min":low,"max":high},"actual_normal_length_range":[min(norm_lengths),max(norm_lengths)],
        "closed_positive_volume_parts":len(pieces),"clear_interior_axis_segments":clear_segments,"exact_support_floor_rays":floor_rays,
        "anchors":anchors,"inner_measurements":measurements,"grounded_feet":sorted(ground),"actual_mesh_contact_connected_parts":len(reached),
        "contact_proofs":contacts,"visible_coplanar_top_checks":top_overlap,"no_save_render_or_export":True}
parser=argparse.ArgumentParser();parser.add_argument('--out')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
target=Path(args.out) if args.out else ROOT/'assets/v3/iterations/flex-bay/initial/geometry-checks.json'
target.write_text(json.dumps(report,indent=2)+'\n')
print('M05_SOURCE_GEOMETRY_PASS '+json.dumps({k:report[k] for k in ['checks','failures','closed_positive_volume_parts','clear_interior_axis_segments','exact_support_floor_rays','actual_mesh_contact_connected_parts','visible_coplanar_top_checks']}))
