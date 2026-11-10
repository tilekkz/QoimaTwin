"""Actual closed solids, support and six apertures; no rendering/source save."""
from collections import Counter
from pathlib import Path
import json
import math
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import runtime_xyz

spec = json.loads((ROOT / "assets/v3/specs/environment-shell.dimensions.json").read_text())
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "assets/v3/blender/environment-shell.blend"))
graph = bpy.context.evaluated_depsgraph_get()
shapes, clouds, all_points, all_triangles = {}, {}, [], []
for obj in bpy.data.objects["environment_shell_root"].children_recursive:
    if obj.type != "MESH": continue
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    vertices = [Vector(runtime_xyz(evaluated.matrix_world@v.co)) for v in mesh.vertices]
    mesh.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    edges = Counter(tuple(sorted((p.vertices[i], p.vertices[(i+1)%len(p.vertices)]))) for p in mesh.polygons for i in range(len(p.vertices)))
    assert all(count == 2 for count in edges.values()), obj.name
    centre = sum(vertices, Vector())/len(vertices)
    volume = sum((vertices[a]-centre).dot((vertices[b]-centre).cross(vertices[c]-centre))/6 for a, b, c in triangles)
    assert volume > 1e-9, (obj.name, volume)
    shapes[obj.name] = {"bvh": BVHTree.FromPolygons(vertices, triangles, all_triangles=True), "vertices": vertices, "volume": volume}
    clouds[obj.name] = {"vertices_runtime": [list(v) for v in vertices], "category": obj.get("shell_component_class"), "parent": obj.parent.name}
    offset = len(all_points); all_points.extend(vertices); all_triangles.extend(tuple(i+offset for i in t) for t in triangles)
    evaluated.to_mesh_clear()
tree = BVHTree.FromPolygons(all_points, all_triangles, all_triangles=True)


def inside_margin(name, point):
    bvh = shapes[name]["bvh"]; votes = []
    for raw in ((1, .337, .171), (.213, 1, .451), (.319, .127, 1)):
        direction = Vector(raw).normalized(); current, count = point.copy(), 0
        for _ in range(50):
            hit = bvh.ray_cast(current, direction, 400)[0]
            if hit is None: break
            # At worldX~144 Blender float32 ULP exceeds10um; advance100um
            # to avoid recounting the same face. Witness margins stay>=0.5mm.
            count += 1; current = hit+direction*1e-4
        votes.append(count%2)
    assert sum(votes) >= 2, name
    return bvh.find_nearest(point)[3]


contacts = []
def contact(a, b, point):
    margins = [inside_margin(name, Vector(point)) for name in (a, b)]
    assert min(margins) > .0005, (a, b, margins)
    contacts.append({"parts": [a, b], "actual_surface_margins_m": margins})
foot_y = {}
for col in spec["columns"]:
    x, z = col["centre_xz"]; height = col["height_m"]
    foot, shaft, cap = [p["name"] for p in col["pieces"]]
    contact(foot, shaft, (x, .15, z)); contact(shaft, cap, (x, height-.12, z))
    foot_y[col["column_id"]] = min(v.y for v in shapes[foot]["vertices"])
assert max(abs(v) for v in foot_y.values()) < 2e-5
for window in spec["windows"]:
    back = window["backing"]; b = back["bounds"]
    centre = [(b["min"][i]+b["max"][i])/2 for i in range(3)]
    axis = 0 if window["side"] in ("W", "E") else 2
    boundary, inward = (144, -1) if window["side"] == "E" else (72, -1) if window["side"] == "N" else (0, 1)
    point = centre.copy(); point[axis] = boundary+inward*.24
    wall = next(w["name"] for w in spec["walls"] if all(w["bounds"]["min"][i]+1e-4 < point[i] < w["bounds"]["max"][i]-1e-4 for i in range(3)))
    contact(back["name"], wall, point)
    for pane in window["panes"]:
        b = pane["bounds"]; point = [(b["min"][i]+b["max"][i])/2 for i in range(3)]; point[axis] = boundary+inward*.285
        contact(back["name"], pane["name"], point)
apertures = []
for gate in spec["gates"]:
    pid, yaw = gate["port_id"], gate["yaw_rad"]
    x0, _, z0 = gate["position"]; half, h = gate["clear_width_m"]/2, gate["clear_height_m"]
    def world(p):
        x, y, z = p
        return Vector((x0+x*math.cos(yaw)+z*math.sin(yaw), y, z0-x*math.sin(yaw)+z*math.cos(yaw)))
    forward = world((0, 0, 1))-world((0, 0, 0))
    count = 0
    for xi in range(21):
        for yi in range(25):
            origin = world((-half+.01+xi*(2*half-.02)/20, .01+yi*(h-.02)/24, -.1))
            assert tree.ray_cast(origin, forward, .45)[0] is None, pid
            count += 1
    left = tree.ray_cast(world((0, h/2, .125)), world((-1, 0, 0))-world((0, 0, 0)), gate["clear_width_m"]+1)[0]
    right = tree.ray_cast(world((0, h/2, .125)), world((1, 0, 0))-world((0, 0, 0)), gate["clear_width_m"]+1)[0]
    top = tree.ray_cast(world((0, 1, .125)), Vector((0, 1, 0)), h+1)[0]
    assert left is not None and right is not None and top is not None
    width = (right-left).length
    assert abs(width-2*half) < 2e-5 and abs(top.y-h) < 2e-5, (pid, width, top.y)
    prefix = pid+"__"
    for sign, side in ((-1, "L"), (1, "R")):
        contact(prefix+"structural_U", prefix+"tan_reveal_U", world((sign*(half+.08), 2, .125)))
        contact(prefix+"structural_U", prefix+"foot_"+side, world((sign*(half+.15), .08, .125)))
        for face, z in (("outside", .045), ("inside", .205)):
            pad = prefix+"bumper_"+side+"_"+face
            contact(prefix+"structural_U", pad, world((sign*(half+.14), .62, z)))
            for number, y in enumerate((.34, .87)):
                contact(pad, prefix+"safety_"+side+"_"+face+str(number), world((sign*(half+.14), y, .014 if face == "outside" else .236)))
    contact(prefix+"structural_U", prefix+"tan_reveal_U", world((0, h+.08, .125)))
    contact(prefix+"structural_U", prefix+"header_cover_outside", world((0, h+.185, .026)))
    contact(prefix+"structural_U", prefix+"header_cover_inside", world((0, h+.185, .224)))
    apertures.append({"port_id": pid, "actual_clear_width_m": width, "actual_clear_height_m": float(top.y), "clear_depth_rays": count})
floor = shapes["FLOOR__operational_support"]["vertices"]
assert abs(max(v.y for v in floor)) < 1e-6
assert max(v.x for v in floor)-min(v.x for v in floor) == 144
assert max(v.z for v in floor)-min(v.z for v in floor) == 72
assert abs(max(v.y for v in all_points)-8) < 1e-6
report = {"closed_positive_volume_meshes": len(shapes), "source_triangles": len(all_triangles), "positive_volume_support_contacts": contacts,
          "grounded_column_foot_y": foot_y, "actual_six_apertures": apertures, "floor_top_y": 0, "floor_size_m": [144, 72], "ceiling_max_y": 8,
          "display_plinth_actual_bounds": {"min": [min(v[i] for v in shapes["DISPLAY_ONLY__plinth"]["vertices"]) for i in range(3)], "max": [max(v[i] for v in shapes["DISPLAY_ONLY__plinth"]["vertices"]) for i in range(3)]}}
(OUT/"actual-source-checks.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
(OUT/"source-mesh-qa.json").write_text(json.dumps({"components": clouds}, separators=(",", ":"))+"\n", encoding="utf-8")
print(json.dumps({"closed_positive_meshes": len(shapes), "support_contacts": len(contacts), "apertures": apertures, "floor": [144, 72], "floor_top": 0, "ceiling": 8}))
