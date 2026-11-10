"""Actual evaluated-mesh contact/support checks; no render or GLB export.

Run with fresh factory-startup Blender, two threads. Pose snapshots include
teal40mm hand gauges marked QA-only; the canonical neutral source stays clean.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import sys

import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import box, material, xyz, runtime_xyz

SOURCE = ROOT / "assets/v3/blender/worker-base.blend"
SPEC = ROOT / "assets/v3/specs/worker-base.dimensions.json"
OUT = Path(__file__).resolve().parent
M = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
POSES = {
    "neutral": {},
    "bent-arm": {"upper_arm_L": [-.65, 0, -.1], "upper_arm_R": [-.65, 0, .1],
                 "forearm_L": [-.95, 0, 0], "forearm_R": [-.95, 0, 0],
                 "hand_L": [.15, 0, 0], "hand_R": [.15, 0, 0]},
    "bent-knee": {"thigh_L": [-.45, 0, 0], "thigh_R": [-.45, 0, 0],
                  "shin_L": [.9, 0, 0], "shin_R": [.9, 0, 0],
                  "foot_L": [-.45, 0, 0], "foot_R": [-.45, 0, 0]},
    "waist-bend": {"torso": [.45, 0, 0], "head": [-.15, 0, 0],
                   "upper_arm_L": [-.25, 0, 0], "upper_arm_R": [-.25, 0, 0]},
}


def tree(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    faces = [list(t.vertices) for t in mesh.loop_triangles]
    edges = Counter(tuple(sorted((polygon.vertices[i], polygon.vertices[(i + 1) % len(polygon.vertices)])))
                    for polygon in mesh.polygons for i in range(len(polygon.vertices)))
    closed = bool(edges) and all(count == 2 for count in edges.values())
    result = BVHTree.FromPolygons(vertices, faces, all_triangles=True)
    evaluated.to_mesh_clear()
    return {"bvh": result, "vertices": vertices, "closed": closed}


def inside(shape, point):
    if not shape["closed"]:
        raise AssertionError("Open mesh cannot prove interior contact")
    votes = []
    for raw in ((1, .337, .171), (.213, 1, .451), (.319, .127, 1)):
        direction = Vector(raw).normalized()
        origin, count = point.copy(), 0
        for _ in range(30):
            hit, _, _, _ = shape["bvh"].ray_cast(origin, direction, 10)
            if hit is None:
                break
            count += 1
            origin = hit + direction * .00001
        votes.append(count % 2 == 1)
    return sum(votes) >= 2


def margin(shape, point):
    if not inside(shape, point):
        return -1
    return shape["bvh"].find_nearest(point)[3]


def check_pose(name, rotations, spec):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    root = bpy.data.objects[spec["root_name"]]
    for joint, values in rotations.items():
        obj = bpy.data.objects["joint__" + joint]
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = (M @ Euler(values, "XYZ").to_matrix() @ M.transposed()).to_quaternion()
    bpy.context.view_layer.update()
    pelvis_shift = 0
    if name == "bent-knee":
        pelvis_shift = -runtime_xyz(bpy.data.objects["anchor_foot_floor_R"].matrix_world.translation)[1]
        bpy.data.objects["joint__pelvis"].location += xyz((0, pelvis_shift, 0))
        bpy.context.view_layer.update()
    shapes = {obj.name: tree(obj) for obj in root.children_recursive if obj.type == "MESH"}
    contacts = []
    for link in spec["declared_connections"]:
        a, b = link["parts"]
        if b.startswith("mitten_"):
            b += "_spine"
        point = bpy.data.objects[link["joint"]].matrix_world.translation
        ma, mb = margin(shapes[a], point), margin(shapes[b], point)
        assert min(ma, mb) > .005, (name, link["joint"], ma, mb)
        contacts.append({"joint": link["joint"], "actual_meshes": [a, b],
                         "inside_both_closed_meshes": True, "measured_surface_margins_m": [ma, mb]})
    floor = {}
    hand = {}
    for suffix in ("L", "R"):
        boot = shapes["boot_" + suffix]
        minimum = min(runtime_xyz(point)[1] for point in boot["vertices"])
        assert abs(minimum) < .00002, (name, suffix, minimum)
        foot = bpy.data.objects["anchor_foot_floor_" + suffix]
        heights = []
        for x in (-.07, 0, .07):
            for z in (-.075, 0, .075):
                point = foot.matrix_world @ xyz((x, 0, z))
                hit, _, _, _ = boot["bvh"].ray_cast(point + xyz((0, .05, 0)), xyz((0, -1, 0)), .1)
                assert hit is not None
                heights.append(runtime_xyz(hit)[1])
        assert max(abs(h) for h in heights) < .00002
        floor[suffix] = {"actual_boot_min_y_m": minimum, "flat_sole_ray_hits": 9,
                         "maximum_contact_plane_error_m": max(abs(h) for h in heights)}
        # Test actual pad/spine/thumb intersections, not just their joint names.
        anchors = bpy.data.objects["anchor_hand_grip_" + suffix]
        parts = {key: shapes["mitten_" + suffix + "_" + key]
                 for key in ("spine", "upper_pad", "lower_pad", "thumb")}
        parent = bpy.data.objects["joint__hand_" + suffix]
        bind = Vector(spec["joints"]["joint__hand_" + suffix]["bind_world_runtime"])
        sign = -1 if suffix == "L" else 1
        witnesses = (("spine", "upper_pad", (sign * .315, .71125, .0485)),
                     ("spine", "lower_pad", (sign * .315, .61375, .0485)),
                     ("upper_pad", "thumb", (sign * .2755, .709, .05)))
        overlap = []
        for a, b, bind_point in witnesses:
            point = parent.matrix_world @ xyz(Vector(bind_point) - bind)
            distances = [margin(parts[a], point), margin(parts[b], point)]
            assert min(distances) > .001, (name, suffix, a, b, distances)
            overlap.append({"parts": [a, b], "actual_surface_margins_m": distances})
        gauge = box("QA_ONLY__grip_gauge_" + suffix, (0, 0, 0), (.20, .040, .040),
                    material("QA_ONLY__Gauge", "#2E7376"), anchors, bevel=0)
        gauge["qa_only"] = True
        bpy.context.view_layer.update()
        gauge_shape = tree(gauge)
        assert not any(gauge_shape["bvh"].overlap(part["bvh"]) for part in parts.values())
        clearance = []
        for x in (-.04, 0, .04):
            for y in (-.02, 0, .02):
                for z in (-.02, 0, .02):
                    point = anchors.matrix_world @ xyz((x, y, z))
                    assert not any(inside(part, point) for part in parts.values())
                    clearance.append(min(part["bvh"].find_nearest(point)[3] for part in parts.values()))
        assert min(clearance) >= .0024, (name, suffix, min(clearance))
        hand[suffix] = {"solid_components_closed": True, "overlap_witnesses": overlap,
                        "gauge_cross_section_m": [.04, .04], "gauge_skin_triangle_intersections": 0,
                        "sampled_clearance_min_m": min(clearance), "sample_count": len(clearance)}
    root["qa_pose"] = name
    root["qa_gauges_not_for_export"] = True
    bpy.context.preferences.filepaths.save_version = 0
    target = OUT / (name + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    return {"pose": name, "runtime_euler_xyz": rotations, "pelvis_y_shift_m": pelvis_shift,
            "actual_joint_volume_contacts": contacts, "soles": floor, "mittens": hand,
            "snapshot": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == "__main__":
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    canonical_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    results = [check_pose(name, rotations, spec) for name, rotations in POSES.items()]
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == canonical_hash
    report = {"method": "Evaluated beveled mesh BVH closedness/inside+nearest-surface distances, actual sole rays and gauge triangle intersection/clearance samples",
              "canonical_neutral_source_sha256": canonical_hash, "poses": results,
              "scope": "Source FK/contact checks, not runtime/export or external cart/equipment grip acceptance"}
    (OUT / "actual-mesh-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("P013_MESH_VERIFIED " + json.dumps({"poses": len(results), "joint_contacts": sum(len(r["actual_joint_volume_contacts"]) for r in results),
          "sole_ray_hits": len(results) * 2 * 9, "gauge_skin_intersections": 0,
          "minimum_gauge_clearance_m": min(hand["sampled_clearance_min_m"] for result in results for hand in result["mittens"].values())}))
