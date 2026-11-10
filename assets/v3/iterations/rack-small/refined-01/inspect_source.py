"""Read-only M01 evaluated source/cavity/support inspection; no render or save."""
from pathlib import Path
import json
import math
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import runtime_xyz

plan = json.loads((ROOT / "assets/v3/specs/rack-small.dimensions.json").read_text())
root = next(o for o in bpy.data.objects if o.get("asset_id") == "rack-small" and o.parent is None)
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
                                 "bounds": bounds, "tree": tree, "volume": volume}
        offset = len(all_vertices);all_vertices += vertices
        all_triangles += [tuple(offset + i for i in t) for t in triangles]
    finally:
        evaluated.to_mesh_clear()
tree = BVHTree.FromPolygons(all_vertices, all_triangles, all_triangles=True)
require(len(pieces) == len(plan["parts"]) == 59, "Part count")
low = [min(v[k] for v in all_vertices) for k in range(3)];high = [max(v[k] for v in all_vertices) for k in range(3)]
require(all(abs(low[k] - plan["bounds_local_xyz_m"]["min"][k]) < 1e-6 and abs(high[k] - plan["bounds_local_xyz_m"]["max"][k]) < 1e-6 for k in range(3)), "Outer bounds")
anchors = {o["anchor_id"]: runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get("anchor_id")}
require(set(anchors) == {a["anchor_id"] for a in plan["anchors"]}, "Anchor set")
floor_rays = 0;clear_segments = 0;measurements = []
for a in plan["anchors"]:
    p = anchors[a["anchor_id"]];require(max(abs(p[k] - a["local_xyz_m"][k]) for k in range(3)) < 1e-6, "Anchor position")
    b = a["usable_bounds_module_local"];lo,hi = b["min"],b["max"]
    for i in range(9):
        for j in range(9):
            x = lo[0] + 1e-5 + (hi[0]-lo[0]-2e-5)*i/8
            z = lo[2] + 1e-5 + (hi[2]-lo[2]-2e-5)*j/8
            hit,normal,_,_ = tree.ray_cast(Vector((x,p[1]+.2,z)),Vector((0,-1,0)),.21)
            require(hit is not None and abs(hit.y-p[1]) < 1e-6 and normal.y > .999, "Floor support " + a["anchor_id"])
            floor_rays += 1
    for axis in range(3):
        other = [k for k in range(3) if k != axis]
        for i in range(7):
            for j in range(7):
                start=[0,0,0];start[axis]=lo[axis]+1e-5
                for k,t in zip(other,(i,j)):
                    start[k]=lo[k]+1e-5+(hi[k]-lo[k]-2e-5)*t/6
                direction=[0,0,0];direction[axis]=1
                hit,*_=tree.ray_cast(Vector(start),Vector(direction),hi[axis]-lo[axis]-2e-5)
                require(hit is None,"Blocked usable interior " + a["anchor_id"]);clear_segments += 1
    measured=[]
    centre=Vector((p[0],p[1]+.175,p[2]))
    for direction,expected in [((-1,0,0),.21),((1,0,0),.21),((0,0,-1),.21)]:
        hit,_,_,distance=tree.ray_cast(centre,Vector(direction),.3)
        require(hit is not None and abs(distance-expected)<1e-6,"Inner width/back plane")
        measured.append(distance)
    hit,_,_,distance=tree.ray_cast(Vector((p[0],p[1]+.04,p[2])),Vector((0,0,1)),.3)
    require(hit is not None and abs(distance-.21)<1e-6,"Low front lip plane");measured.append(distance)
    hit,*_=tree.ray_cast(centre,Vector((0,0,1)),.3)
    require(hit is None,"Front opening above low lip")
    measurements.append({"anchor_id":a["anchor_id"],"actual_width_m":measured[0]+measured[1],"actual_depth_between_rear_and_low_lip_m":measured[2]+measured[3],"support_y_m":p[1]})

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
ground={n for n in names if n.endswith("_foot") and abs(pieces[n]["bounds"]["min"][1])<1e-6}
require(len(ground)==4,"Grounded feet")
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
top_overlap=[]
for level,y in enumerate([.25,1.0],1):
    surfaces=[]
    for name in [f'L{level}_recessed_wood_deck',f'L{level}_petrol_floor_inlay']:
        obj=pieces[name];surfaces.append([[tuple((obj["vertices"][i].x,obj["vertices"][i].z)) for i in t] for t in obj["triangles"] if all(abs(obj["vertices"][i].y-y)<1e-6 for i in t)])
    overlap=sum(area(clip(a,b)) for a in surfaces[0] for b in surfaces[1]);require(overlap<1e-8,"Wood/petrol visible coplanar top overlap")
    top_overlap.append({"level":level,"wood_petrol_top_overlap_area_m2":overlap})
report={"asset_id":"rack-small","actual_evaluated_parts":len(pieces),"triangles":len(all_triangles),"checks":checks,"failures":0,
        "actual_bounds_runtime":{"min":low,"max":high},"actual_normal_length_range":[min(norm_lengths),max(norm_lengths)],
        "closed_positive_volume_parts":len(pieces),"clear_interior_axis_segments":clear_segments,"exact_support_floor_rays":floor_rays,
        "anchors":anchors,"inner_measurements":measurements,"grounded_feet":sorted(ground),"actual_mesh_contact_connected_parts":len(reached),
        "contact_proofs":contacts,"visible_coplanar_top_checks":top_overlap,"no_save_render_or_export":True}
target=ROOT/'assets/v3/iterations/rack-small/refined-01/geometry-checks.json';target.write_text(json.dumps(report,indent=2)+'\n')
print('M01_SOURCE_GEOMETRY_PASS '+json.dumps({k:report[k] for k in ['checks','failures','closed_positive_volume_parts','clear_interior_axis_segments','exact_support_floor_rays','actual_mesh_contact_connected_parts','visible_coplanar_top_checks']}))
