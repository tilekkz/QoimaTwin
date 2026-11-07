"""Read-only evaluated-mesh checks for the saved P08.2 source."""
from pathlib import Path
import json
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
plan = json.loads((ROOT / "assets/v3/specs/packing-station.dimensions.json").read_text(encoding="utf-8"))
frame = {p["part_id"]: p for p in plan["parts"] if p["group"] == "frame"}
roots = [o for o in bpy.context.scene.objects if o.get("asset_id") == "packing-station"]
assert len(roots) == 1
objects = [o for o in roots[0].children_recursive if o.type == "MESH"]
checks = []


def check(name, value, actual=None):
    checks.append({"check": name, "pass": bool(value), "actual": actual})
    if not value:
        raise AssertionError(name + ": " + str(actual))


def runtime(point):
    return Vector((point.x, point.z, -point.y))


def overlap(a, b):
    return math.prod(max(0, min(a["max"][k], b["max"][k]) -
                         max(a["min"][k], b["min"][k])) for k in range(3))


graph = bpy.context.evaluated_depsgraph_get()
all_vertices, triangles, components = [], [], []
for obj in objects:
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [runtime(evaluated.matrix_world @ v.co) for v in mesh.vertices]
        mesh.calc_loop_triangles()
        offset = len(all_vertices)
        all_vertices.extend(vertices)
        triangles.extend(tuple(offset + i for i in tri.vertices) for tri in mesh.loop_triangles)
        bounds = {"min": [min(p[k] for p in vertices) for k in range(3)],
                  "max": [max(p[k] for p in vertices) for k in range(3)]}
        pid = obj["part_id"]
        expected = frame[pid]["bounds_local_xyz_m"]
        check(pid + ":inside_approved_envelope", all(
            expected["min"][k] - 1e-5 <= bounds["min"][k] and
            bounds["max"][k] <= expected["max"][k] + 1e-5 for k in range(3)))
        check(pid + ":finite_vertices", all(math.isfinite(c) for p in vertices for c in p))
        check(pid + ":no_spur_volume_overlap", overlap(bounds, plan["reserved_spur_volume_local_xyz_m"]) < 1e-9)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        volume = bm.calc_volume(signed=True)
        check(pid + ":closed_manifold", all(edge.is_manifold for edge in bm.edges))
        check(pid + ":positive_volume", volume > 1e-8, volume)
        bm.free()
        if pid.startswith("foot_"):
            check(pid + ":ground_Y0", abs(bounds["min"][1]) < 1e-6)
        components.append({"part_id": pid, "bounds_runtime": bounds,
                           "signed_volume_m3": volume,
                           "triangles": len(mesh.loop_triangles)})
    finally:
        evaluated.to_mesh_clear()

check("exact_17_frame_parts_no_devices", len(objects) == 17 and {c["part_id"] for c in components} == set(frame))
check("no_saved_studio_meshes", not any(o.type == "MESH" and o not in objects for o in bpy.context.scene.objects))
bounds = {"min": [min(p[k] for p in all_vertices) for k in range(3)],
          "max": [max(p[k] for p in all_vertices) for k in range(3)]}
size = [bounds["max"][k] - bounds["min"][k] for k in range(3)]
check("actual_bbox_1.80_.92_.90", all(abs(a-b) < 1e-5 for a, b in zip(size, [1.8, .92, .90])), size)
check("actual_world_maxZ_5.65", abs(bounds["max"][2] + 5.2 - 5.65) < 1e-6)
lookup = {c["part_id"]: c for c in components}
gap = lookup["worktop_R"]["bounds_runtime"]["min"][0] - lookup["worktop_L"]["bounds_runtime"]["max"][0]
check("actual_worktop_gap_1m", abs(gap - 1) < 1e-6, gap)
bvh = BVHTree.FromPolygons(all_vertices, triangles, all_triangles=True)
clear_rays = 0
for ix in range(21):
    x = -.49 + ix * .98 / 20
    for iz in range(17):
        z = -.44 + iz * .88 / 16
        hit = bvh.ray_cast(Vector((x, 1.05, z)), Vector((0, -1, 0)), .82)
        check("channel_ray_%02d_%02d" % (ix, iz), hit[0] is None)
        clear_rays += 1
for x in [-.7, .7]:
    hit = bvh.ray_cast(Vector((x, 1.05, 0)), Vector((0, -1, 0)), .2)
    check("worktop_surface_" + str(x), hit[0] is not None and abs(hit[0].y - .92) < 1e-5)
    hit = bvh.ray_cast(Vector((x, .4, 0)), Vector((0, -1, 0)), .2)
    check("lower_shelf_surface_" + str(x), hit[0] is not None and abs(hit[0].y - .28) < 1e-5)
report = {"stage": "P08.2", "method": "Saved source evaluated meshes, manifold/volume and runtime BVH rays; no source mutation/export",
          "checks": checks, "failures": sum(not c["pass"] for c in checks),
          "mesh_parts": len(objects), "triangles": len(triangles),
          "bounds_runtime": bounds, "dimensions_m": size,
          "actual_worktop_gap_m": gap, "central_open_rays": clear_rays,
          "components": components}
(OUT / "geometry-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("P08_2_GEOMETRY_CHECKS " + json.dumps({"checks": len(checks), "failures": report["failures"], "rays": clear_rays}))
