"""M02 STANDARD rack, metres / floor-centre / front +Z.

Run in background Blender, never in the user's live scene. R13.2 supplies the
construction language; accepted C04 bounds and C08 direct fork contact control
the actual ground-rib adaptation. No cargo, stock or operational admission.
"""
from pathlib import Path
import hashlib
import json
import math
import shutil
import struct
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v3_common import ROOT, PALETTE, anchor, beam, box, finish, group, material, reset, runtime_xyz, xyz

ASSET = "rack-standard"
ITERATION_ID = "M02-02"
ITERATION = ROOT / "assets/v3/iterations/rack-standard" / ITERATION_ID
SPEC = ROOT / "assets/v3/specs/rack-standard.dimensions.json"
SOURCE_PATHS = [
    "assets/references/v3/r13-2-rack-standard.png",
    "assets/references/v3/r13-2-rack-standard.targets.json",
    "assets/references/v3/provenance/r13-2.json",
    "docs/v3/contract-proposals/storage-layout-v3.json",
    "docs/v3/contract-proposals/storage-slots-v3.json",
    "docs/v3/contract-proposals/vehicle-handling-v3.json",
]
EPS = 2e-6
BAYS = (-.7, .7)
LEVELS = (.2, 1.4, 2.6)
LANES = (-1.1, -.3, .3, 1.1)


def bounds_box(name, low, high, mat, parent, bevel=.003):
    return box(name, tuple((a+b)/2 for a, b in zip(low, high)),
               tuple(b-a for a, b in zip(low, high)), mat, parent, bevel)


def source_bindings():
    return [{"path": p, "sha256": hashlib.sha256((ROOT/p).read_bytes()).hexdigest()}
            for p in SOURCE_PATHS]


def declared_slots():
    source = json.loads((ROOT / SOURCE_PATHS[4]).read_text(encoding="utf-8"))
    slots = [s for s in source["slots"] if s["module_id"] == "v3:module:STANDARD_W:001"]
    assert len(slots) == 6
    return [{"bay": s["bay"], "level": s["level"],
             "anchor_name": f"anchor_bin_L{s['level']}_B{s['bay']}",
             "position_runtime": s["bin_anchor_module_local"],
             "usable_bounds": s["usable_bounds_module_local"],
             "usable_dimensions_m": s["usable_dimensions_xyz_m"],
             "source_slot_id": s["slot_id"],
             "upper_retrieval_admission": False} for s in slots]


def build():
    root = group(ASSET)
    root["role"] = "storage_module"
    root["storage_type"] = "STANDARD"
    root["operational_admission"] = False
    root["reference_id"] = "R13.2"
    root["reference_adaptation"] = "Ground deck has open-top fork lanes; C04 support .20 and six usable bounds unchanged."
    root["source_bindings_json"] = json.dumps(source_bindings(), sort_keys=True)
    charcoal = material("V3_STANDARD_charcoal", PALETTE["charcoal"])
    petrol = material("V3_STANDARD_petrol", PALETTE["petrol"])
    tan = material("V3_STANDARD_warm_tan", PALETTE["tan"])

    # Six stepped columns: collar/boot width NEVER exceeds the accepted .07.
    # Consecutive solids share planar faces; no floating collar or wide footpad.
    segments = [(0, .08, .07, petrol, "boot"),
                (.08, .23, .07, petrol, "ground_joint"),
                (.23, 1.30, .05, charcoal, "lower_shaft"),
                (1.30, 1.43, .07, petrol, "middle_joint"),
                (1.43, 2.50, .05, charcoal, "middle_shaft"),
                (2.50, 2.63, .07, petrol, "upper_joint"),
                (2.63, 3.72, .05, charcoal, "upper_shaft"),
                (3.72, 3.82, .07, petrol, "header_joint"),
                (3.82, 3.85, .07, charcoal, "cap")]
    for ix, x in enumerate((-1.365, 0, 1.365)):
        for iz, z in enumerate((-.65, .65)):
            for low, high, width, mat, suffix in segments:
                bounds_box(f"post_{ix}_{iz}_{suffix}",
                           (x-width/2, low, z-width/2),
                           (x+width/2, high, z+width/2), mat, root, .002)

    for bay, (left, right) in enumerate(((-1.33, -.035), (.035, 1.33)), 1):
        # Bottom .02 web and three substantial ribs per bay. The .12-wide
        # channels are open at the front, at the top, and through the back.
        bounds_box(f"B{bay}_ground_web", (left, .10, -.615),
                   (right, .12, .615), tan, root, .0015)
        lane_centres = [x for x in LANES if left < x < right]
        starts = [left] + [x+.06 for x in lane_centres]
        ends = [x-.06 for x in lane_centres] + [right]
        for rib, (start, end) in enumerate(zip(starts, ends), 1):
            bounds_box(f"B{bay}_ground_rib_{rib}", (start, .12, -.65),
                       (end, .20, .65), tan, root, .003)
        for side, lo_z, hi_z in (("front", .615, .70), ("rear", -.70, -.615)):
            bounds_box(f"B{bay}_ground_{side}_low_beam", (left, .06, lo_z),
                       (right, .12, hi_z), petrol, root, .002)
        # Closed upper decks remain storage supports, not active high lifts.
        for level, top in enumerate(LEVELS[1:], 2):
            bounds_box(f"B{bay}_L{level}_deck", (left, top-.10, -.615),
                       (right, top, .615), tan, root, .003)
            for side, lo_z, hi_z in (("front", .615, .70), ("rear", -.70, -.615)):
                bounds_box(f"B{bay}_L{level}_{side}_beam",
                           (left, top-.10, lo_z), (right, top-.02, hi_z),
                           tan, root, .002)
                # Thin face cap is part of the supported deck, not a raised lip.
                a, b = (.615, .65) if side == "front" else (-.65, -.615)
                bounds_box(f"B{bay}_L{level}_{side}_deck_edge",
                           (left, top-.02, a), (right, top, b), tan, root, .0015)
        # Top is an open frame tie, never a seventh/eighth storage address.
        for side, lo_z, hi_z in (("front", .615, .70), ("rear", -.70, -.615)):
            bounds_box(f"B{bay}_header_{side}", (left, 3.72, lo_z),
                       (right, 3.82, hi_z), tan, root, .003)

    # Three depth rails at each structural elevation connect front/rear posts.
    for ix, x in enumerate((-1.365, 0, 1.365)):
        for tag, low, high in (("ground", .06, .10), ("middle", 1.30, 1.38),
                               ("upper", 2.50, 2.58), ("header", 3.72, 3.80)):
            bounds_box(f"depth_tie_{ix}_{tag}", (x-.025, low, -.615),
                       (x+.025, high, .615), petrol if tag == "ground" else tan, root, .002)

    # Six visible rear diagonals, matching the approved front/rear topology.
    # Their whole depth is behind usable minZ=-.45 and within outer -.70.
    for bay, x0 in enumerate((-1.365, 0), 1):
        for level, (low, high) in enumerate(((.24, 1.34), (1.44, 2.54), (2.64, 3.76)), 1):
            beam(f"B{bay}_L{level}_rear_diagonal", (x0, low, -.65),
                 (x0+1.365, high, -.65), .045, charcoal, root)

    for slot in declared_slots():
        obj = anchor(slot["anchor_name"], slot["position_runtime"], root, "storage_support")
        obj["usable_bounds_json"] = json.dumps(slot["usable_bounds"], sort_keys=True)
        obj["max_payload_kg"] = 250
        obj["operational_admission"] = False
        obj["support_bottom_gap_m"] = 0.
    return root


def triangle_box_overlap(tri, low, high):
    """Triangle / open AABB SAT, excluding boundary contact by caller inset."""
    centre = Vector([(a+b)/2 for a,b in zip(low,high)])
    half = [(b-a)/2 for a,b in zip(low,high)]
    points = [Vector(p)-centre for p in tri]
    edges = [points[1]-points[0], points[2]-points[1], points[0]-points[2]]
    axes = [Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1)), edges[0].cross(edges[1])]
    axes.extend(e.cross(a) for e in edges for a in axes[:3])
    for axis in axes:
        if axis.length_squared < 1e-20:
            continue
        values = [axis.dot(p) for p in points]
        radius = sum(abs(axis[i])*half[i] for i in range(3))
        if min(values) > radius+1e-10 or max(values) < -radius-1e-10:
            return False
    return True


def evaluate(root):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    parts = []
    all_vertices, all_tris = [], []
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        verts_b = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        verts = [runtime_xyz(v) for v in verts_b]
        tris = [tuple(t.vertices) for t in mesh.loop_triangles]
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        volume = bm.calc_volume(signed=True)
        assert volume > 1e-10, (obj.name, "nonpositive volume", volume)
        assert all(len(e.link_faces) == 2 for e in bm.edges), (obj.name, "open/nonmanifold solid")
        centre = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        assert all(f.calc_area() > 1e-12 and f.normal.dot(f.calc_center_median()-centre) > 1e-10
                   for f in bm.faces), (obj.name, "degenerate/inward face")
        bm.free()
        low = [min(v[i] for v in verts) for i in range(3)]
        high = [max(v[i] for v in verts) for i in range(3)]
        bvh = BVHTree.FromPolygons(verts_b, tris, all_triangles=True, epsilon=1e-7)
        samples = verts_b + [sum((verts_b[i] for i in t), Vector())/3 for t in tris]
        parts.append({"name":obj.name,"verts":verts,"tris":tris,"low":low,"high":high,
                      "bvh":bvh,"samples":samples,"volume":volume})
        offset = len(all_vertices)
        all_vertices.extend(verts_b)
        all_tris.extend(tuple(offset+i for i in t) for t in tris)
        evaluated.to_mesh_clear()
    return parts, BVHTree.FromPolygons(all_vertices, all_tris, all_triangles=True, epsilon=1e-7)


def check_empty(parts, low, high, tag):
    lo, hi = [x+EPS for x in low], [x-EPS for x in high]
    intersections = []
    for p in parts:
        if any(p["high"][i] <= lo[i] or p["low"][i] >= hi[i] for i in range(3)):
            continue
        if any(triangle_box_overlap([p["verts"][i] for i in t], lo, hi) for t in p["tris"]):
            intersections.append(p["name"])
        # Every authoring component is convex and outward-checked. Detect an
        # empty test box enclosed by a solid as well as crossing triangles.
        centre = xyz([(a+b)/2 for a,b in zip(lo,hi)])
        loc, normal, _, _ = p["bvh"].find_nearest(centre)
        if loc is not None and normal.dot(centre-loc) < -EPS:
            intersections.append(p["name"] + ":contains-centre")
    assert not intersections, (tag, intersections)
    return {"id":tag,"min":low,"max":high,"intersecting_triangles":0,"enclosing_solids":0}


def verify(root):
    parts, union = evaluate(root)
    low = [min(p["low"][i] for p in parts) for i in range(3)]
    high = [max(p["high"][i] for p in parts) for i in range(3)]
    for actual, expected in zip(low+high, [-1.4,0,-.7,1.4,3.85,.7]):
        assert abs(actual-expected) < EPS, ("outer bounds", actual, expected)
    assert all(abs(root.scale[i]-1) < EPS for i in range(3))
    cavities = [check_empty(parts, s["usable_bounds"]["min"], s["usable_bounds"]["max"], s["anchor_name"])
                for s in declared_slots()]
    lanes = []
    ray_count = 0
    for x in LANES:
        lanes.append(check_empty(parts, [x-.04,.13,-.70], [x+.04,.20,.90], f"blade_{x}"))
        for xx in (x-.039,x,x+.039):
            for yy in (.1305,.165,.1995):
                hit = union.ray_cast(xyz((xx,yy,.90)), xyz((0,0,-1)), 1.60)
                assert hit[0] is None, ("fork insertion ray blocked",x,xx,yy,hit)
                ray_count += 1
    # Real upward-facing top hits at 15 FRAGILE bottom points per bay. Points
    # deliberately span both outside ribs and the centre rib, not the channels.
    support = []
    for centre in BAYS:
        points=[]
        for x in (centre-.50,centre-.20,centre,centre+.20,centre+.50):
            for z in (-.20,.10,.55):
                origin=xyz((x,.205,z))
                hit, normal, _, distance = union.ray_cast(origin, xyz((0,-1,0)), .03)
                assert hit is not None, ("missing support",x,z)
                point=runtime_xyz(hit)
                assert abs(point[1]-.20) < EPS and normal.dot(xyz((0,1,0))) > .999, ("wrong support",point)
                points.append(point)
        # Actual contact convex hull spans the HU CoG and both lateral margins.
        assert min(p[0] for p in points) < centre < max(p[0] for p in points)
        assert min(p[2] for p in points) < .175 < max(p[2] for p in points)
        support.append({"bay_centre_x":centre,"hu_bottom_y":.20,
                        "hu_footprint":{"min":[centre-.55,-.25],"max":[centre+.55,.60]},
                        "actual_upward_contacts":points,
                        "cog_xz":[centre,.175],"cog_inside_contact_hull":True,
                        "interpretation":"Rigid unchanged HU bridges open lanes; no payload/stability certification."})
    # Contact connectivity uses actual evaluated BVHs/surface samples, not only
    # a hierarchy or broadphase AABB. All components must reach a floor boot.
    links=[]
    adjacency={p["name"]:set() for p in parts}
    for i,a in enumerate(parts):
        for b in parts[i+1:]:
            if any(a["high"][j] < b["low"][j]-EPS or b["high"][j] < a["low"][j]-EPS for j in range(3)):
                continue
            touching = bool(a["bvh"].overlap(b["bvh"]))
            if not touching:
                for samples, target in ((a["samples"],b["bvh"]),(b["samples"],a["bvh"])):
                    for sample in samples:
                        near=target.find_nearest(sample)
                        if near[3] is not None and near[3] < EPS:
                            touching=True
                            break
                    if touching:
                        break
            if touching:
                adjacency[a["name"]].add(b["name"])
                adjacency[b["name"]].add(a["name"])
                links.append([a["name"],b["name"]])
    reached={p["name"] for p in parts if abs(p["low"][1])<EPS}
    frontier=list(reached)
    while frontier:
        for nxt in adjacency[frontier.pop()]-reached:
            reached.add(nxt);frontier.append(nxt)
    missing=sorted(set(adjacency)-reached)
    assert not missing, ("floating/disconnected parts",missing)
    return {"asset_id":ASSET,"iteration":ITERATION_ID,"method":"evaluated bevel mesh; triangle/AABB SAT, BVH rays/contact graph; closed convex solid normals",
            "bounds_runtime":{"min":low,"max":high},"positive_closed_outward_parts":len(parts),
            "part_contact_edges":len(links),"all_parts_connected_to_floor":True,
            "cavities":cavities,"fork_entry_prisms":lanes,"unblocked_insertion_rays":ray_count,
            "fragile_ground_support":support,"shared_sources":source_bindings(),
            "operational_admission":False,"root_browser_and_khronos":"pending"}


def dimensions():
    return {"asset_id":ASSET,"namespace":"v3","units":"m","up_axis":"Y","front_axis":"+Z",
            "origin":"floor centre","outer_dimensions_xyz_m":[2.8,3.85,1.4],
            "source_bindings":source_bindings(),"bin_anchors":declared_slots(),
            "construction":{"posts":6,"bays":2,"storage_decks":3,"deck_nominal_thickness_m":.10,
                            "support_y_m":list(LEVELS),"post_shaft_width_m":.05,"post_collar_width_m":.07,
                            "rear_diagonals":6,"upper_decks":"closed; blocked upper retrieval unchanged",
                            "ground_web_y":[.10,.12],"ground_ribs_y":[.12,.20],
                            "ground_low_beam_top_y":.12,"fork_lane_centres_x":list(LANES),
                            "fork_lane_width_m":.12,"blade_dimensions_width_height_m":[.08,.07],
                            "blade_y":[.13,.20],"blade_side_clearance_m":.02,"blade_bottom_clearance_m":.01},
            "reference_adaptation":"R13.2 closed-looking lower deck becomes open-top fork lanes/ribs for C08. Exact bounds, C04 HU support height and all six cavities retained.",
            "operational_admission":False,"payload_certification":False}


def audit_saved_source():
    """Read-only CPU check of both saved iterations and final exported factors."""
    source = ROOT / "assets/v3/blender/rack-standard.blend"
    initial = ITERATION.parent / "M02-01/rack-standard.blend"
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    signatures = []
    assignments = []
    for path in (initial, source):
        bpy.ops.wm.open_mainfile(filepath=str(path))
        root = bpy.data.objects[ASSET]
        parts, union = evaluate(root)
        triangles = []
        for part in parts:
            for tri in part["tris"]:
                triangles.append(sorted(tuple(round(c, 7) for c in part["verts"][i]) for i in tri))
        signatures.append(hashlib.sha256(json.dumps(sorted(triangles),separators=(",",":")).encode()).hexdigest())
        assignments.append({o.name: [m.name for m in o.data.materials] for o in root.children_recursive if o.type=="MESH"})
    assert signatures[0] == signatures[1], "Material refresh changed actual source triangles"
    editable = [o for o in root.children_recursive if o.type == "MESH"]
    assert len(editable) == 108 and all(any(m.type=="BEVEL" for m in o.modifiers) for o in editable)
    raw = (ROOT/"frontend/public/models/v3/rack-standard.glb").read_bytes()
    json_length = struct.unpack_from("<I",raw,12)[0]
    gltf = json.loads(raw[20:20+json_length])
    material_report = []
    used = {m for o in editable for m in o.data.materials}
    assert {m.name for m in used} == {m["name"] for m in gltf["materials"]}
    for mat in sorted(used,key=lambda m:m.name):
        node = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        actual = {"baseColorFactor":list(node.inputs["Base Color"].default_value),
                  "metallicFactor":node.inputs["Metallic"].default_value,
                  "roughnessFactor":node.inputs["Roughness"].default_value}
        exported = next(m["pbrMetallicRoughness"] for m in gltf["materials"] if m["name"] == mat.name)
        assert max(abs(a-b) for a,b in zip(actual["baseColorFactor"],exported["baseColorFactor"])) < 1e-6
        assert all(abs(actual[k]-exported[k]) < 1e-6 for k in ("metallicFactor","roughnessFactor"))
        material_report.append({"name":mat.name,"source_principled":actual,"glb_pbr":exported,"equal_within":1e-6})
    supports = []
    for slot in declared_slots():
        x,y,_ = slot["position_runtime"]
        points=[]
        for xx in (x-.2,x,x+.2):
            for z in (-.2,.1,.55):
                point,normal,_,_=union.ray_cast(xyz((xx,y+.005,z)),xyz((0,-1,0)),.03)
                assert point is not None and abs(runtime_xyz(point)[1]-y)<EPS
                assert normal.dot(xyz((0,1,0)))>.999
                points.append(runtime_xyz(point))
        supports.append({"anchor":slot["anchor_name"],"actual_top_contacts":points,
                         "retrieval_admission":False})
    assert source_sha == hashlib.sha256(source.read_bytes()).hexdigest(), "Audit modified saved source"
    report = {"asset_id":ASSET,"iteration":ITERATION_ID,"mode":"read_only_saved_source",
              "source_sha256":source_sha,"initial_and_final_geometry_sha256":signatures,
              "geometry_unchanged":True,"editable_meshes_with_bevel":len(editable),
              "material_assignment_changes":[name for name in assignments[0] if assignments[0][name]!=assignments[1][name]],
              "materials":material_report,"six_supports":supports,"actual_support_rays":sum(len(s["actual_top_contacts"]) for s in supports),
              "root_browser_and_khronos":"pending"}
    (ITERATION/"source-export-checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("M02_SOURCE_EXPORT_CHECKS " + json.dumps({"materials":len(material_report),"editable_meshes":len(editable),"geometry_unchanged":True,"support_rays":report["actual_support_rays"]}))


if __name__ == "__main__":
    if not bpy.app.background:
        raise RuntimeError("Use background Blender")
    if "--audit-source" in sys.argv:
        audit_saved_source()
        sys.exit(0)
    reset()
    root=build()
    report=verify(root)
    ITERATION.mkdir(parents=True,exist_ok=True)
    SPEC.parent.mkdir(parents=True,exist_ok=True)
    SPEC.write_text(json.dumps(dimensions(),indent=2)+"\n",encoding="utf-8")
    (ITERATION/"mesh-checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    finish(ASSET,root)
    for path in (ROOT/"assets/v3/blender/rack-standard.blend",
                 ROOT/"assets/v3/blender/rack-standard.stats.json",
                 ROOT/"frontend/public/models/v3/rack-standard.glb",SPEC,Path(__file__)):
        shutil.copy2(path,ITERATION/path.name)
    print("M02_MESH_CHECKS " + json.dumps({k:report[k] for k in ("asset_id","positive_closed_outward_parts","part_contact_edges","all_parts_connected_to_floor","unblocked_insertion_rays")}))
