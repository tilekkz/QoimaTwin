"""Read-only M03 evaluated source/cavity/support inspection; no render or save."""
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

plan = json.loads((ROOT / "assets/v3/specs/heavy-bay.dimensions.json").read_text())
root = next(o for o in bpy.data.objects if o.get("asset_id") == "heavy-bay" and o.parent is None)
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
require(len(pieces) == len(plan["parts"]) == 17, "Part count")
low = [min(v[k] for v in all_vertices) for k in range(3)];high = [max(v[k] for v in all_vertices) for k in range(3)]
require(all(abs(low[k] - plan["bounds_local_xyz_m"]["min"][k]) < 1e-6 and abs(high[k] - plan["bounds_local_xyz_m"]["max"][k]) < 1e-6 for k in range(3)), "Outer bounds")
anchors = {o["anchor_id"]: runtime_xyz(o.matrix_world.translation) for o in root.children_recursive if o.get("anchor_id")}
require(set(anchors) == {a["anchor_id"] for a in plan["anchors"]}, "Anchor set")
floor_rays = 0;clear_segments = 0;measurements = []
for a in plan["anchors"]:
    p = anchors[a["anchor_id"]];require(max(abs(p[k] - a["local_xyz_m"][k]) for k in range(3)) < 1e-6, "Anchor position")
    b = a["usable_bounds_module_local"];lo,hi = b["min"],b["max"]
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

# Conservative real flat support patches; the channel holes are NOT a floor.
for patch in plan["support_patches"]:
    for i in range(11):
        for j in range(21):
            x=patch["x_range_m"][0]+(patch["x_range_m"][1]-patch["x_range_m"][0])*i/10
            z=patch["z_range_m"][0]+(patch["z_range_m"][1]-patch["z_range_m"][0])*j/20
            hit,normal,_,_=tree.ray_cast(Vector((x,.38,z)),Vector((0,-1,0)),.21)
            require(hit is not None and abs(hit.y-.18)<1e-6 and normal.y>.999,"Flat support patch")
            floor_rays+=1
hole_rays=0;hole_hit_ys=[]
for left,right in plan["open_top_channels"]["x_bands_m"]:
    for i in range(5):
        for j in range(11):
            x=left+.01+(right-left-.02)*i/4;z=-.69+1.38*j/10
            hit,*_=tree.ray_cast(Vector((x,.38,z)),Vector((0,-1,0)),.5)
            require(hit is None or hit.y<.081,"False full-floor coverage in channel")
            if hit is not None:hole_hit_ys.append(float(hit.y))
            hole_rays+=1

def clear_box(lo,hi,samples,label):
    total=0
    for axis in range(3):
        other=[k for k in range(3) if k!=axis]
        for i in range(samples):
            for j in range(samples):
                start=[0,0,0];start[axis]=lo[axis]+1e-5
                for k,t in zip(other,(i,j)):start[k]=lo[k]+1e-5+(hi[k]-lo[k]-2e-5)*t/(samples-1)
                direction=[0,0,0];direction[axis]=1
                hit,*_=tree.ray_cast(Vector(start),Vector(direction),hi[axis]-lo[axis]-2e-5)
                require(hit is None,label);total+=1
    return total
channel_segments=0;blade_segments=0
for left,right in plan["open_top_channels"]["x_bands_m"]:
    channel_segments+=clear_box([left,.08001,-.8],[right,.18001,.8],11,"Blocked full open-top lane")
blade_boxes=[]
for spacing in [.24,.28,.32,.36,.40]:
    for side in [-1,1]:
        lo=[side*spacing-.04,.11,-.8];hi=[side*spacing+.04,.18,.8]
        blade_segments+=clear_box(lo,hi,7,"Blocked actual blade envelope")
        blade_boxes.append({"spacing":spacing,"side":side,"min":lo,"max":hi})

# Exact triangle/AABB clipping proves the CONTINUOUS blade-spacing union clear,
# beyond the finite segment grids. Bounds are used only to skip distant triangles.
def triangle_box_polygon(vertices,lo,hi):
    poly=[list(v) for v in vertices]
    for axis in range(3):
        for boundary,sign in [(lo[axis],1),(hi[axis],-1)]:
            output=[]
            if not poly:return []
            prev=poly[-1];pv=sign*(prev[axis]-boundary)
            for cur in poly:
                cv=sign*(cur[axis]-boundary)
                if (cv>=0)!=(pv>=0):
                    t=pv/(pv-cv);output.append([prev[k]+t*(cur[k]-prev[k]) for k in range(3)])
                if cv>=0:output.append(cur)
                prev,pv=cur,cv
            poly=output
    return poly
triangle_box_tests=0
for side in [-1,1]:
    lo=[-.44,.11,-.8] if side<0 else [.20,.11,-.8]
    hi=[-.20,.18,.8] if side<0 else [.44,.18,.8]
    for tri in all_triangles:
        require(not triangle_box_polygon([all_vertices[i] for i in tri],lo,hi),"Triangle intrudes continuous blade-spacing union")
        triangle_box_tests+=1
flat_top_area=sum((all_vertices[t[1]]-all_vertices[t[0]]).cross(all_vertices[t[2]]-all_vertices[t[0]]).length/2 for t in all_triangles if all(abs(all_vertices[i].y-.18)<1e-6 for i in t))

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
require(len(ground)==3,"Grounded runners")
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
report={"asset_id":"heavy-bay","actual_evaluated_parts":len(pieces),"triangles":len(all_triangles),"checks":checks,"failures":0,
        "source_sha256":hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
        "material_triangle_fingerprints_1e_6_m":fingerprints,
        "actual_bounds_runtime":{"min":low,"max":high},"actual_normal_length_range":[min(norm_lengths),max(norm_lengths)],
        "closed_positive_volume_parts":len(pieces),"clear_interior_axis_segments":clear_segments,"exact_support_floor_rays":floor_rays,
        "anchors":anchors,"inner_measurements":measurements,
        "support_patches":plan["support_patches"],"actual_flat_top_triangle_area_m2":flat_top_area,"full_floor_support":False,
        "negative_hole_floor_rays":hole_rays,"negative_hole_hit_y_range_m":[min(hole_hit_ys),max(hole_hit_ys)] if hole_hit_ys else None,
        "clear_channel_segments":channel_segments,"clear_blade_envelope_segments":blade_segments,"blade_boxes":blade_boxes,
        "continuous_blade_union_triangle_box_tests":triangle_box_tests,"continuous_blade_union_triangle_intersections":0,"grounded_runners":sorted(ground),"actual_mesh_contact_connected_parts":len(reached),
        "contact_proofs":contacts,"visible_coplanar_top_checks":top_overlap,"no_save_render_or_export":True}
parser=argparse.ArgumentParser();parser.add_argument('--out')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
target=Path(args.out) if args.out else ROOT/'assets/v3/iterations/heavy-bay/initial/geometry-checks.json'
target.write_text(json.dumps(report,indent=2)+'\n')
print('M03_SOURCE_GEOMETRY_PASS '+json.dumps({k:report[k] for k in ['checks','failures','closed_positive_volume_parts','clear_interior_axis_segments','exact_support_floor_rays','actual_mesh_contact_connected_parts','visible_coplanar_top_checks']}))
