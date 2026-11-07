"""P09.3 new architecture vs actual compiled L12 routes, CPU/read-only inputs.

Plan mode runs before geometry. --actual substitutes measured source mesh bounds
for walls/columns/windows; gate U meshes retain their proven collision unions.
"""
from pathlib import Path
from collections import Counter
import hashlib
import importlib.util
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
def read(p): return json.loads((ROOT / p).read_text())
spec = read("assets/v3/specs/environment-shell.dimensions.json")
links = read("docs/v3/contract-proposals/layout-links-v3.json")
module = importlib.util.spec_from_file_location("readonly_L11_geometry", ROOT / "tools/visual/v3/audit_layout_spatial.py")
audit = importlib.util.module_from_spec(module)
module.loader.exec_module(audit)
glb_mode = "--glb" in sys.argv
actual = "--actual" in sys.argv or glb_mode
measured_path = "glb-geometry-components.json" if glb_mode else "source-geometry.json"
measurement = read("assets/v3/iterations/environment-shell/P09.3/"+measured_path) if actual else {}
measured = measurement.get("components", {})
# Source float32 placement and export/join rounding are separate measured
# stages. Keep each20um bound; compose their error budgets for plan-vs-GLB.
glb_source_error = measurement.get("maximumSourceGLBVertexDistanceM", 0) if glb_mode else 0
assert glb_source_error <= 2e-5
bound_tolerance = 2e-5+glb_source_error
maximum_bound_error = 0
solids, architectural = [], []
def add(name, b, category):
    global maximum_bound_error
    if actual and name in measured:
        got = measured[name]["bounds_runtime"]
        error = max(abs(got[k][i]-b[k][i]) for k in ("min", "max") for i in range(3))
        maximum_bound_error = max(maximum_bound_error, error)
        assert error < bound_tolerance, name
        b = got
    s = audit.solid(name, category, audit.box_poly(b), b["min"][1], b["max"][1])
    solids.append(s)
    if category != "gate_frame": architectural.append(s)
for wall in spec["walls"]: add(wall["name"], wall["bounds"], "wall")
for col in spec["columns"]:
    for piece in col["pieces"]: add(piece["name"], piece["bounds"], "column")
for window in spec["windows"]:
    for piece in [window["backing"]]+window["panes"]: add(piece["name"], piece["bounds"], "opaque_window")
for gate in spec["gates"]:
    x, _, z = gate["position"]; h, half = gate["clear_height_m"], gate["clear_width_m"]/2
    yaw = gate["yaw_rad"]
    for suffix, lo, hi in (("L", [-half-.25, 0, 0], [-half, h, .25]),
                           ("R", [half, 0, 0], [half+.25, h, .25]),
                           ("header", [-half-.25, h, 0], [half+.25, h+.25, .25])):
        points = [(x+a*math.cos(yaw)+c*math.sin(yaw), z-a*math.sin(yaw)+c*math.cos(yaw)) for a in (lo[0], hi[0]) for c in (lo[2], hi[2])]
        b = {"min": [min(p[0] for p in points), lo[1], min(p[1] for p in points)], "max": [max(p[0] for p in points), hi[1], max(p[1] for p in points)]}
        add("GATE_UNION__"+gate["port_id"]+"__"+suffix, b, "gate_frame")
index = audit.Index(solids)
findings, counts = [], Counter()
walk = links["walk_graph"]
nodes = {n["node_id"]: n["world_pos"][::2] for n in walk["nodes"]}
radii = {m["mode_id"]: m["clearance_radius_m"] for m in read("docs/v3/contract-proposals/pedestrian-graph-v3.json")["modes"]}
first_human = None
for arc in walk["arcs"]:
    a, b = nodes[arc["from_node_id"]], nodes[arc["to_node_id"]]
    radius = max(radii[m] for m in arc["allowed_modes"])
    if first_human is None and math.dist(a, b) > .1: first_human = (arc["arc_id"], a, b, radius)
    counts["walking_arcs"] += 1
    counts["walking_allowed_mode_pairs_covered"] += len(arc["allowed_modes"])
    for obstacle in index.query(audit.capsule_bounds(a, b, radius)):
        if obstacle["y_min"] < 1.7 and audit.capsule_hit(a, b, radius, obstacle["poly"]):
            findings.append({"kind": "walking_capsule_architecture_collision", "arc_id": arc["arc_id"], "blocker": obstacle["id"]})
profiles = {p["profile_id"]: p for p in read("docs/v3/contract-proposals/vehicle-graph-v3.json")["profiles"]}
local = read("docs/v3/contract-proposals/storage-layout-v3.json")["access_profiles"]
profiles["nonlong_forklift"] = {**local["nonlong_forklift"], "clearance_padding_m": local["nonlong_forklift"]["padding_m"], "top_padding_m": .25}
def covers(big, small):
    return all(any(all(b["min"][i] <= s["min"][i]+1e-8 and b["max"][i] >= s["max"][i]-1e-8 for i in range(3)) for b in big["component_bounds_local_m"]) for s in small["component_bounds_local_m"])
cache = set(); first_vehicle = None
for arc in links["vehicle_graph"]["arcs"]:
    allowed = arc["allowed_geometry_profile_ids"]
    selected = next(p for p in ("loaded_max", "nonlong_forklift", "empty_cradle", "unloaded_bare") if p in allowed)
    p = profiles[selected]
    assert all(covers(p, profiles[q]) and p["clearance_padding_m"] >= profiles[q]["clearance_padding_m"] and p["top_padding_m"] >= profiles[q]["top_padding_m"] for q in allowed)
    route = {"components": p["component_bounds_local_m"], "padding": p["clearance_padding_m"], "top_padding": p["top_padding_m"]}
    counts["vehicle_arcs"] += 1
    counts["vehicle_allowed_profile_pairs_covered"] += len(allowed)
    if first_vehicle is None: first_vehicle = (arc["arc_id"], route, arc["geometry"])
    key = json.dumps([arc["geometry"], selected], sort_keys=True)
    if key in cache: continue
    cache.add(key)
    for component, box, polygons, hull, inflation in audit.swept_shapes(route, arc["geometry"]):
        counts["continuous_component_sweeps"] += 1
        counts["inflated_oriented_polygons"] += len(polygons)
        candidates = [s for s in index.query(audit.aabb(hull)) if min(box["max"][1]+route["top_padding"], s["y_max"])-max(box["min"][1], s["y_min"]) > 1e-8]
        if not candidates: continue
        for polygon in polygons:
            for obstacle in candidates:
                if audit.poly_hit(polygon, obstacle["poly"]):
                    findings.append({"kind": "vehicle_component_architecture_collision", "arc_id": arc["arc_id"], "component": component, "blocker": obstacle["id"], "continuous_arc_inflation_m": inflation})
assert not findings, findings[:20]
apertures, boundary_exceptions, crossings = [], [], []
for gate in spec["gates"]:
    x, _, z = gate["position"]; half, h, yaw = gate["clear_width_m"]/2, gate["clear_height_m"], gate["yaw_rad"]
    corners = [(x+a*math.cos(yaw)+c*math.sin(yaw), z-a*math.sin(yaw)+c*math.cos(yaw)) for a in (-half, half) for c in (0, .25)]
    poly = audit.hull(corners)
    assert not any(s["y_min"] < h-1e-6 and s["y_max"] > 1e-6 and audit.poly_hit(poly, s["poly"]) for s in solids), gate["port_id"]
    apertures.append({"port_id": gate["port_id"], "clear_width_m": 2*half, "clear_height_m": h, "new_obstacles_in_aperture": 0})
    ap = gate["approach_keep_clear_xz_m"]
    for s in architectural:
        if audit.poly_hit(audit.rect(ap["min"], ap["max"]), s["poly"]): boundary_exceptions.append({"port_id": gate["port_id"], "boundary_piece": s["id"], "class": s["category"], "explicit_exception": "own perimeter architecture outside clear aperture; whole approach rectangle is not empty"})
    # Centred continuous straight crossing: bulky L05 atW/E, nonlong atN/retail,
    # manual assembly atparcel/express. Geometry witness, not handler admission.
    width = 4.7 if gate["port_id"] in ("IN_W_BULK", "OUT_E_B2B") else 1.7 if gate["port_id"] in ("IN_N_STANDARD", "OUT_W_RETAIL") else 1.9
    height = 2.35 if width != 1.9 else 1.7
    cp = audit.hull([(x+a*math.cos(yaw)+c*math.sin(yaw), z-a*math.sin(yaw)+c*math.cos(yaw)) for a in (-width/2, width/2) for c in (-2, 2)])
    assert not any(s["y_min"] < height-1e-6 and s["y_max"] > 1e-6 and audit.poly_hit(cp, s["poly"]) for s in solids), gate["port_id"]
    crossings.append({"port_id": gate["port_id"], "probe_width_m": width, "probe_height_m": height, "straight_crossing_hits": 0, "operational_admission": False})
hid, a, b, radius = first_human
centre = [(a[i]+b[i])/2 for i in range(2)]
injected = audit.rect([centre[0]-.32, centre[1]-.32], [centre[0]+.32, centre[1]+.32])
assert audit.capsule_hit(a, b, radius, injected)
vid, route, geometry = first_vehicle
centre, _ = audit.pose(geometry, .5)
vpoly = audit.rect([centre[0]-.32, centre[1]-.32], [centre[0]+.32, centre[1]+.32])
assert any(audit.poly_hit(p, vpoly) for _, _, polys, _, _ in audit.swept_shapes(route, geometry) for p in polys)
report = {"mode": "actual_GLB_vertex_cloud_envelopes" if glb_mode else "actual_source_envelopes" if actual else "declared_plan_preflight", "counts": dict(counts),
          "coordinate_error_budget": {"source_vs_plan_tolerance_m": 2e-5, "actual_GLB_vs_source_max_distance_m": glb_source_error,
                                      "composed_plan_comparison_tolerance_m": bound_tolerance, "maximum_measured_plan_bound_error_m": maximum_bound_error,
                                      "route_collision_predicates_unchanged": True},
          "new_architectural_solids": len(architectural), "conservative_gate_parts": 18, "blocking_route_findings": findings,
          "actual_L12_graph_hash": hashlib.sha256((ROOT / "docs/v3/contract-proposals/layout-links-v3.json").read_bytes()).hexdigest(),
          "method": "All actual compiled walking arcs, max admitted mode capsule; all admitted vehicle profile pairs covered by asserted component containment, exact straight hulls and<=0.5deg arc sampling with continuous displacement inflation from read-only L11 geometry functions.",
          "apertures": apertures, "straight_port_crossings": crossings, "disclosed_architectural_approach_boundary_exceptions": boundary_exceptions,
          "negative_cases": [{"case": "injected_column_on_actual_walking_arc", "arc_id": hid, "detected": True}, {"case": "injected_column_on_actual_vehicle_root", "arc_id": vid, "detected": True}],
          "scope": "New perimeter architecture only, no source route/scheduling/admission changes; floor support/display plinth belowY0 are not raised obstacles."}
(OUT / ("glb-route-checks.json" if glb_mode else "actual-route-checks.json" if actual else "plan-route-preflight.json")).write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"mode": report["mode"], "counts": dict(counts), "blocking_findings": len(findings), "approach_boundary_exceptions": len(boundary_exceptions), "clear_apertures": 6, "port_crossings": 6, "negative_cases": 2}))
