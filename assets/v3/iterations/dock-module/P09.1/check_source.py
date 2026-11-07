"""Actual evaluated dock solids/aperture/support, CPU only, no source save."""
from collections import Counter
from pathlib import Path
import json
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import runtime_xyz

OUT = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "assets/v3/blender/dock-module.blend"))
graph = bpy.context.evaluated_depsgraph_get()
shapes = {}
for obj in bpy.data.objects["dock_module_root"].children_recursive:
    if obj.type != "MESH":
        continue
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    vertices = [Vector(runtime_xyz(evaluated.matrix_world @ v.co)) for v in mesh.vertices]
    mesh.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    edges = Counter(tuple(sorted((p.vertices[i], p.vertices[(i + 1) % len(p.vertices)])))
                    for p in mesh.polygons for i in range(len(p.vertices)))
    assert all(count == 2 for count in edges.values()), obj.name
    shapes[obj.name] = {"vertices": vertices, "triangles": triangles,
                        "bvh": BVHTree.FromPolygons(vertices, triangles, all_triangles=True)}
    evaluated.to_mesh_clear()


def clips_open_aperture(points):
    # Sutherland-Hodgman triangle clipping to a shrunken OPEN aperture box.
    # Finds an intruding face even when all original vertices lie outside it.
    result = points
    for axis, low, high in ((0, -2 + 1e-6, 2 - 1e-6), (1, 1e-6, 4.5 - 1e-6), (2, 1e-6, .25 - 1e-6)):
        for bound, sense in ((low, 1), (high, -1)):
            current, result = result, []
            if not current:
                return False
            for a, b in zip(current, current[1:] + current[:1]):
                da, db = sense * (a[axis] - bound), sense * (b[axis] - bound)
                if da >= 0:
                    result.append(a)
                if (da >= 0) != (db >= 0):
                    result.append(a + (b - a) * (da / (da - db)))
    return bool(result)


intrusions = []
for name, shape in shapes.items():
    for point in shape["vertices"]:
        assert -2.250001 <= point.x <= 2.250001 and -1e-6 <= point.y <= 4.750001 and -1e-6 <= point.z <= .250001
    for tri in shape["triangles"]:
        if clips_open_aperture([shape["vertices"][i] for i in tri]):
            intrusions.append(name)
assert not intrusions, intrusions
ray_count = 0
for x in [-1.99 + i * 3.98 / 20 for i in range(21)]:
    for y in [.01 + i * 4.48 / 24 for i in range(25)]:
        for name, shape in shapes.items():
            assert shape["bvh"].ray_cast(Vector((x, y, -.1)), Vector((0, 0, 1)), .45)[0] is None, name
        ray_count += 1


def inside_margin(shape, point):
    votes = []
    for direction in ((1, .337, .171), (.213, 1, .451), (.319, .127, 1)):
        direction = Vector(direction).normalized()
        current, count = point.copy(), 0
        for _ in range(30):
            hit = shape["bvh"].ray_cast(current, direction, 20)[0]
            if hit is None:
                break
            count += 1
            current = hit + direction * 1e-5
        votes.append(count % 2)
    assert sum(votes) >= 2
    return shape["bvh"].find_nearest(point)[3]


contacts = []
def contact(a, b, point):
    margins = [inside_margin(shapes[name], Vector(point)) for name in (a, b)]
    assert min(margins) > .0005, (a, b, margins)
    contacts.append({"parts": [a, b], "world_runtime_point": point, "actual_surface_margins_m": margins})
for sign, side in ((-1, "L"), (1, "R")):
    contact("structural_U", "stepped_tan_reveal_U", (sign * 2.08, 2, .125))
    contact("structural_U", "ground_foot_" + side, (sign * 2.15, .08, .125))
    for face, z in (("outside", .045), ("inside", .205)):
        pad = "bumper_" + side + "_" + face
        contact("structural_U", pad, (sign * 2.14, .62, z))
        for number, y in enumerate((.34, .87)):
            contact(pad, "safety_band_" + side + "_" + face + "_" + str(number),
                    (sign * 2.14, y, .014 if face == "outside" else .236))
contact("structural_U", "stepped_tan_reveal_U", (0, 4.58, .125))
contact("structural_U", "header_cover_outside", (0, 4.685, .026))
contact("structural_U", "header_cover_inside", (0, 4.685, .224))
feet = {side: min(p.y for p in shapes["ground_foot_" + side]["vertices"]) for side in ("L", "R")}
assert max(abs(v) for v in feet.values()) < 1e-6
report = {"closed_source_meshes": len(shapes), "actual_triangle_aperture_intrusions": 0,
          "through_aperture_clear_rays": ray_count, "ground_foot_min_y_m": feet,
          "actual_positive_volume_contacts": contacts,
          "method": "evaluated actual beveled vertices/closed mesh edges; triangle/open-box clipping + full-depth rays; BVH inside and nearest-surface support witnesses",
          "collision_union": "All vertices inside exact4.5x4.75x.25 outer bounds and no faces inside open4x4.5 aperture; all solids remain in accepted jamb/header union."}
(OUT / "iteration-01.actual-source-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("DOCK_SOURCE_VERIFIED " + json.dumps({"closed_meshes": len(shapes), "contact_witnesses": len(contacts),
      "aperture_intrusions": 0, "full_depth_clear_rays": ray_count, "foot_min_y": feet}))
