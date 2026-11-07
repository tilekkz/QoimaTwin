"""Source-only fixture: accepted station and two frozen straight modules."""
from pathlib import Path
import hashlib
import json
import math
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from v3_common import reset, group, box, material, xyz, runtime_xyz

STATION = ROOT / "assets/v3/blender/packing-station.blend"
STRAIGHT = ROOT / "assets/v3/blender/conveyor-straight.blend"
frozen_sha = hashlib.sha256(STRAIGHT.read_bytes()).hexdigest()
reset()
fixture = group("P08_4__PAIR_FIXTURE")
fixture["asset_id"] = "packing-station-pair"
fixture["role"] = "engineering_pair_fixture_not_product_inventory"
fixture["qa_only"] = True


def append_asset(path, asset_id, prefix, position):
    with bpy.data.libraries.load(str(path), link=False) as (available, loaded):
        loaded.collections = ["V3_ASSET"]
    collection = loaded.collections[0]
    bpy.context.scene.collection.children.link(collection)
    roots = [o for o in collection.all_objects if o.get("asset_id") == asset_id]
    assert len(roots) == 1
    root = roots[0]
    root.parent = fixture
    root.location = xyz(position)
    for obj in [root] + list(root.children_recursive):
        obj["fixture_component"] = prefix
        obj["frozen_source_name"] = obj.name
        obj.name = prefix + "::" + obj.name
    return root


station = append_asset(STATION, "packing-station", "STATION", (0, 0, 0))
first = append_asset(STRAIGHT, "conveyor-straight", "SPUR_A", (0, 0, -1.2))
originals = [first] + list(first.children_recursive)
mapping = {}
for obj in originals:
    copy = obj.copy()
    bpy.context.collection.objects.link(copy)
    copy.name = "SPUR_B::" + obj["frozen_source_name"]
    copy["fixture_component"] = "SPUR_B"
    mapping[obj] = copy
for old, copy in mapping.items():
    copy.parent = mapping.get(old.parent, fixture)
second = mapping[first]
second.location = xyz((0, 0, -.2))
bpy.context.view_layer.update()


def geometry(root):
    verts, tris, owners, parts = [], [], [], []
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        try:
            points = [Vector(runtime_xyz(evaluated.matrix_world @ v.co)) for v in mesh.vertices]
            offset = len(verts)
            verts.extend(points)
            for tri in mesh.loop_triangles:
                tris.append(tuple(offset + i for i in tri.vertices))
                owners.append(obj.name)
            parts.append({"name": obj.name, "bounds": {
                "min": [min(p[k] for p in points) for k in range(3)],
                "max": [max(p[k] for p in points) for k in range(3)]},
                "source_name": obj.get("frozen_source_name", obj.name)})
        finally:
            evaluated.to_mesh_clear()
    return {"vertices": verts, "triangles": tris, "owners": owners,
            "parts": parts, "bvh": BVHTree.FromPolygons(verts, tris, all_triangles=True)}


table = geometry(station)
modules = [geometry(first), geometry(second)]
checks = []


def check(name, condition, actual=None):
    checks.append({"check": name, "pass": bool(condition), "actual": actual})
    if not condition:
        raise AssertionError(name + ": " + str(actual))


def overlap(a, b):
    return math.prod(max(0, min(a["max"][k], b["max"][k]) -
                         max(a["min"][k], b["min"][k])) for k in range(3))


def penetrates(a, b):
    # Intended .92m support contact can differ by tens of nanometres after
    # Blender float32 transforms. Require actual depth, not tiny raw volume.
    return all(min(a["max"][k], b["max"][k]) -
               max(a["min"][k], b["min"][k]) > 1e-6 for k in range(3))


def cube_bvh(bounds):
    lo, hi = bounds["min"], bounds["max"]
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return BVHTree.FromPolygons(v, faces, all_triangles=False)


for i, module in enumerate(modules):
    intersections = table["bvh"].overlap(module["bvh"])
    check("station_vs_module_%s_actual_triangle_no_intersections" % i, not intersections, len(intersections))
    check("station_vs_module_%s_component_boxes_disjoint" % i,
          all(overlap(t["bounds"], m["bounds"]) < 1e-10 for t in table["parts"] for m in module["parts"]))
check("source_instances_unit_scale", all(abs(v - 1) < 1e-8 for o in (station, first, second) for v in o.scale))
table_left = next(p["bounds"] for p in table["parts"] if p["source_name"] == "worktop_L")
table_right = next(p["bounds"] for p in table["parts"] if p["source_name"] == "worktop_R")
opening = table_right["min"][0] - table_left["max"][0]
outer_width = max(p[0] for p in modules[0]["vertices"]) - min(p[0] for p in modules[0]["vertices"])
belt_parts = [p for p in modules[0]["parts"] if "belt_panel_" in p["source_name"]]
usable_width = max(p["bounds"]["max"][0] for p in belt_parts) - min(p["bounds"]["min"][0] for p in belt_parts)
minimum_box_separation = min(math.sqrt(sum(max(0, a["bounds"]["min"][k] - b["bounds"]["max"][k],
    b["bounds"]["min"][k] - a["bounds"]["max"][k]) ** 2 for k in range(3)))
    for a in table["parts"] for m in modules for b in m["parts"])
check("actual_spur_side_gap_50mm", (opening - outer_width) / 2 >= .04999,
      {"opening_m": opening, "module_outer_width_m": outer_width})
check("actual_QA_usable_side_gap_110mm", (usable_width - .6) / 2 >= .10999, usable_width)
ports = {}
for label, root in [("SPUR_A", first), ("SPUR_B", second)]:
    ports[label] = {o["anchor_id"]: runtime_xyz(o.matrix_world.translation)
                    for o in root.children_recursive if o.get("anchor_id")}
check("actual_module_join_minus_.7", math.dist(ports["SPUR_A"]["anchor_port_plus"], ports["SPUR_B"]["anchor_port_minus"]) < 1e-6)
check("actual_upstream_terminal_ports", math.dist(ports["SPUR_A"]["anchor_port_minus"], [0, .92, -1.7]) < 1e-6 and
      math.dist(ports["SPUR_B"]["anchor_port_plus"], [0, .92, .3]) < 1e-6)
stationsurface = table["bvh"]
all_module_parts = modules[0]["parts"] + modules[1]["parts"]
nonbelt = [p for p in all_module_parts if "belt_panel_" not in p["source_name"]]
for index in range(17):
    centre_z = -1.5 + index * .1
    bounds = {"min": [-.3, .92, centre_z - .2], "max": [.3, 1.32, centre_z + .2]}
    check("QA_%02d_station_no_volume_overlap" % index,
          not any(penetrates(bounds, p["bounds"]) for p in table["parts"]))
    check("QA_%02d_nonbelt_no_volume_overlap" % index,
          not any(penetrates(bounds, p["bounds"]) for p in nonbelt),
          [{"name": p["name"], "bounds": p["bounds"], "overlap_m3": overlap(bounds, p["bounds"])}
           for p in nonbelt if penetrates(bounds, p["bounds"])])
    check("QA_%02d_station_no_triangle_collision" % index, not stationsurface.overlap(cube_bvh(bounds)))
support_hits = []
for ix in range(13):
    for iz in range(9):
        x, z = -.3 + ix * .05, -.1 + iz * .05
        hits = [m["bvh"].ray_cast(Vector((x, 1.6, z)), Vector((0, -1, 0)), 1.) for m in modules]
        hits = [h for h in hits if h[0] is not None]
        hit = min(hits, key=lambda h: h[3]) if hits else None
        check("work_base_support_%02d_%02d" % (ix, iz), hit is not None and abs(hit[0].y - .92) < 1e-5)
        support_hits.append(list(hit[0]))
for index in range(81):
    z = -1.7 + index * .025
    for x in (-.3, 0, .3):
        hits = [m["bvh"].ray_cast(Vector((x, 1.6, z)), Vector((0, -1, 0)), 1.) for m in modules]
        hits = [h for h in hits if h[0] is not None]
        hit = min(hits, key=lambda h: h[3]) if hits else None
        check("paired_deck_support_%02d_%s" % (index, x), hit is not None and abs(hit[0].y - .92) < 1e-5)
actual_guides = {o["anchor_id"]: runtime_xyz(o.matrix_world.translation)
                 for o in station.children_recursive if o.get("anchor_id")}
manifest_path = ROOT / "assets/v3/blender/packing-station.anchors.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for a in manifest["anchors"]:
    check(a["anchor_id"] + ":actual_saved_anchor_matches", math.dist(actual_guides[a["anchor_id"]], a["local_xyz_m"]) < 1e-6)
    if a.get("physical_part"):
        point = Vector(a["local_xyz_m"])
        found = stationsurface.find_nearest(point)
        actual_owner = table["owners"][found[2]] if found[0] is not None else "none"
        check(a["anchor_id"] + ":actual_physical_surface", found[3] < 1e-5 and a["physical_part"] in actual_owner,
              {"owner": actual_owner, "distance_m": found[3], "normal": list(found[1])})
for aid in ("anchor_transfer_south_in", "anchor_transfer_south_out", "anchor_spur_terminal", "anchor_processing_base"):
    position = actual_guides[aid]
    hits = [m["bvh"].ray_cast(Vector((position[0], 1.6, position[2])), Vector((0, -1, 0)), 1.) for m in modules]
    hits = [h for h in hits if h[0] is not None]
    hit = min(hits, key=lambda h: h[3]) if hits else None
    check(aid + ":actual_paired_deck_section", hit is not None and math.dist(hit[0], Vector(position)) < 1e-5)
    record = next(a for a in manifest["anchors"] if a["anchor_id"] == aid)
    record["authority"] = "actual_paired_source_deck_section"
    record["normal_runtime"] = [0, 1, 0]
    record["pair_surface_hit"] = list(hit[0])
oversize = {"min": [-.45, .92, -.1], "max": [.45, 1.32, .3]}
check("negative_oversize_.9m_width_rejected_by_guards", any(penetrates(oversize, p["bounds"]) for p in nonbelt))

# Wire proxy is an exact-size QA fixture, not baked cargo or a product model.
outline = group("QA_ONLY__MAX_ENVELOPE", parent=fixture)
outline["role"] = "synthetic_admission_bound_not_typed_cargo"
outline["dimensions_xyz_m"] = [.6, .4, .4]
outline["base_centre_runtime"] = [0, .92, .1]
qa_mat = material("QA only | maximum envelope", "#9279A8", roughness=.9)
for x in (-.298, .298):
    for z in (-.098, .298):
        box("QA_vertical", (x, 1.12, z), (.004, .396, .004), qa_mat, outline, bevel=.0003)
for y in (.922, 1.318):
    for z in (-.098, .298):
        box("QA_width", (0, y, z), (.596, .004, .004), qa_mat, outline, bevel=.0003)
    for x in (-.298, .298):
        box("QA_depth", (x, y, .1), (.004, .004, .396), qa_mat, outline, bevel=.0003)
bpy.context.view_layer.update()
qa_geometry = geometry(outline)
qa_low = [min(p[k] for p in qa_geometry["vertices"]) for k in range(3)]
qa_high = [max(p[k] for p in qa_geometry["vertices"]) for k in range(3)]
check("actual_QA_geometry_undeformed_.6_.4_.4", all(abs(qa_high[k] - qa_low[k] - v) < 1e-5 for k, v in enumerate([.6, .4, .4])), {"min": qa_low, "max": qa_high})
check("frozen_conveyor_source_unchanged", hashlib.sha256(STRAIGHT.read_bytes()).hexdigest() == frozen_sha)
bpy.context.preferences.filepaths.save_version = 0
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "pair.blend"))
pair_reports = {
    "ports": ports, "surface_y_m": .92, "physical_deck_local_z": [-1.7, .3],
    "table_cross_section_local_z": -.45, "work_payload_base_centre": [0, .92, .1],
    "QA_envelope_dimensions_xyz_m": [.6, .4, .4], "work_QA_bounds": {"min": [-.3, .92, -.1], "max": [.3, 1.32, .3]},
    "sweep_positions": 17, "base_support_rays": len(support_hits), "paired_deck_support_rays": 243,
    "penetration_depth_tolerance_m": 1e-6,
    "actual_QA_outline_bounds": {"min": qa_low, "max": qa_high},
    "measured_clearance_m": {"table_opening": opening, "module_outer_width": outer_width,
        "table_to_module_each_side": (opening - outer_width) / 2,
        "belt_usable_width": usable_width, "QA_to_usable_each_side": (usable_width - .6) / 2,
        "minimum_table_module_component_box_separation": minimum_box_separation,
        "QA_front_support_margin_nominal": 0.0},
    "checks": checks, "failures": sum(not c["pass"] for c in checks),
    "station_part_count": len(table["parts"]), "module_parts_per_instance": [len(m["parts"]) for m in modules],
    "source_fingerprints": {"station": hashlib.sha256(STATION.read_bytes()).hexdigest(), "frozen_straight": frozen_sha},
    "limits": ["Wire QA envelope is the synthetic L08 maximum bound, not adopted M07/C02 typed cargo or inventory.",
               "No human pose/operation timing is accepted; device measurement overrides need P04 stance/rig validation."]}
(OUT / "pair-checks.json").write_text(json.dumps(pair_reports, indent=2) + "\n", encoding="utf-8")
manifest["pair_measurement"] = {k: pair_reports[k] for k in ["ports", "surface_y_m", "physical_deck_local_z", "table_cross_section_local_z", "work_payload_base_centre", "QA_envelope_dimensions_xyz_m", "work_QA_bounds", "sweep_positions", "base_support_rays", "paired_deck_support_rays", "source_fingerprints"]}
manifest["ports_semantics"] = "Table south in/out at-.45 is an internal cross-section of the spur, not the physical upstream port. Actual pair upstream-1.7/join-.7/terminal+.3 derived from frozen source anchors; one bidirectional path, no new cells/timestamps."
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("P08_4_PAIR_CHECKS " + json.dumps({"checks": len(checks), "failures": pair_reports["failures"], "base_rays": len(support_hits), "deck_rays": 243}))
