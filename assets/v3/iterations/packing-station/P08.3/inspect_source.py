"""Read-only saved-source device, aperture and prior-frame verification."""
from pathlib import Path
import hashlib
import json
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
spec = json.loads((ROOT / "assets/v3/specs/packing-station.dimensions.json").read_text(encoding="utf-8"))
planned = {p["part_id"]: p for p in spec["parts"]}
checks = []


def check(name, condition, actual=None):
    checks.append({"check": name, "pass": bool(condition), "actual": actual})
    if not condition:
        raise AssertionError(name + ": " + str(actual))


def runtime(point):
    return Vector((point.x, point.z, -point.y))


def contact(a, b):
    return all(min(a["max"][k], b["max"][k]) >=
               max(a["min"][k], b["min"][k]) - 1e-5 for k in range(3))


def frame_signature():
    result = {}
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.get("role") != "packing_frame_component":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        try:
            data = {"vertices": [[round(v, 8) for v in runtime(evaluated.matrix_world @ p.co)]
                                 for p in mesh.vertices],
                    "triangles": [list(t.vertices) for t in mesh.loop_triangles]}
            result[obj["part_id"]] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        finally:
            evaluated.to_mesh_clear()
    return result


root = next(o for o in bpy.context.scene.objects if o.get("asset_id") == "packing-station")
objects = [o for o in root.children_recursive if o.type == "MESH"]
graph = bpy.context.evaluated_depsgraph_get()
vertices, triangles, rows = [], [], []
for obj in objects:
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    try:
        points = [runtime(evaluated.matrix_world @ v.co) for v in mesh.vertices]
        offset = len(vertices)
        vertices.extend(points)
        triangles.extend(tuple(offset + i for i in t.vertices) for t in mesh.loop_triangles)
        bounds = {"min": [min(v[k] for v in points) for k in range(3)],
                  "max": [max(v[k] for v in points) for k in range(3)]}
        pid = obj["part_id"]
        host = obj.get("planned_part_id", pid)
        box = planned[host]["bounds_local_xyz_m"]
        check(pid + ":within_approved_host", all(box["min"][k] - 1e-5 <= bounds["min"][k] and
              bounds["max"][k] <= box["max"][k] + 1e-5 for k in range(3)))
        check(pid + ":finite", all(math.isfinite(c) for v in points for c in v))
        bm = bmesh.new()
        bm.from_mesh(mesh)
        volume = bm.calc_volume(signed=True)
        euler = len(bm.verts) - len(bm.edges) + len(bm.faces)
        check(pid + ":closed_manifold", all(e.is_manifold for e in bm.edges))
        check(pid + ":positive_volume", volume > 1e-8, volume)
        if pid == "tape_ring":
            check("tape_genus1_annulus", euler == 0, euler)
        bm.free()
        rows.append({"part_id": pid, "host": host, "bounds_runtime": bounds,
                     "triangles": len(mesh.loop_triangles), "volume_m3": volume,
                     "euler_characteristic": euler})
    finally:
        evaluated.to_mesh_clear()

check("49_unique_mesh_parts", len(objects) == len({r["part_id"] for r in rows}) == 49)
bounds = {"min": [min(v[k] for v in vertices) for k in range(3)],
          "max": [max(v[k] for v in vertices) for k in range(3)]}
size = [bounds["max"][k] - bounds["min"][k] for k in range(3)]
check("bbox_1.8_1.4_.9", all(abs(a-b) < 1e-5 for a, b in zip(size, [1.8, 1.4, .9])), size)
check("fixed_max_worldZ_5.65", abs(bounds["max"][2] + 5.2 - 5.65) < 1e-6)
lookup = {r["part_id"]: r for r in rows}
seen = {"foot_LS"}
queue = list(seen)
while queue:
    current = queue.pop()
    for other in lookup:
        if other not in seen and contact(lookup[current]["bounds_runtime"], lookup[other]["bounds_runtime"]):
            seen.add(other)
            queue.append(other)
check("all_parts_support_contact_chain_to_ground", len(seen) == len(rows), sorted(set(lookup) - seen))
bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
hole_rays = 0
for iy in range(-4, 5):
    for iz in range(-4, 5):
        dy, dz = iy * .008, iz * .008
        if dy * dy + dz * dz <= .035 ** 2:
            hit = bvh.ray_cast(Vector((1.1, 1.075 + dy, .26 + dz)), Vector((-1, 0, 0)), .35)
            check("tape_axial_clear_%s_%s" % (iy, iz), hit[0] is None)
            hole_rays += 1
hit = bvh.ray_cast(Vector((1.1, 1.140, .26)), Vector((-1, 0, 0)), .35)
check("tape_annular_material_exists", hit[0] is not None and abs(hit[0].x - .835) < .002)
channel_rays = 0
for ix in range(21):
    for iz in range(17):
        hit = bvh.ray_cast(Vector((-.49 + ix * .98 / 20, 1.45, -.44 + iz * .88 / 16)),
                           Vector((0, -1, 0)), 1.22)
        check("central_channel_%s_%s" % (ix, iz), hit[0] is None)
        channel_rays += 1
for name, x, y, expected in [("screen_recess", -.70, 1.33, -.302),
                            ("screen_bezel", -.865, 1.33, -.285),
                            ("scanner_lens", -.69, 1.16, .391),
                            ("scanner_frame", -.795, 1.16, .40),
                            ("printer_mouth", .61, 1.04, .315),
                            ("printer_front", .53, 1.04, .34),
                            ("printer_paper", .60, 1.027, .40)]:
    hit = bvh.ray_cast(Vector((x, y, .7)), Vector((0, 0, -1)), 1.2)
    check(name + ":measured_front_depth", hit[0] is not None and abs(hit[0].z - expected) < .002,
          list(hit[0]) if hit[0] is not None else None)
guide_ids = {"anchor_scanner_contact", "anchor_label_pick", "anchor_tape_pull", "anchor_screen_face", "anchor_tape_ring"}
expected_guides = {a["anchor_id"]: a["local_xyz_m"] for a in spec["anchors"] if a["anchor_id"] in guide_ids}
guides = {o["anchor_id"]: list(runtime(o.matrix_world.translation)) for o in root.children_recursive if o.get("anchor_id")}
check("five_exact_device_guides", set(guides) == guide_ids and all(
    math.dist(guides[k], expected_guides[k]) < 1e-6 for k in guides))
current_frame = frame_signature()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "assets/v3/iterations/packing-station/P08.2/packing-station.blend"))
previous_frame = frame_signature()
check("P08.2_exact_evaluated_frame_geometry_preserved", len(current_frame) == 17 and current_frame == previous_frame)
report = {"stage": "P08.3", "method": "Read-only evaluated source meshes/BVH and prior saved frame signatures",
          "checks": checks, "failures": sum(not c["pass"] for c in checks),
          "mesh_parts": len(rows), "triangles": len(triangles), "bounds_runtime": bounds,
          "dimensions_m": size, "tape_clear_axial_rays": hole_rays,
          "central_open_rays": channel_rays, "components": rows,
          "device_guides_runtime": guides, "frame_geometry_signatures": current_frame}
(OUT / "geometry-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("P08_3_GEOMETRY_CHECKS " + json.dumps({"checks": len(checks), "failures": report["failures"],
      "tape_rays": hole_rays, "central_rays": channel_rays}))
