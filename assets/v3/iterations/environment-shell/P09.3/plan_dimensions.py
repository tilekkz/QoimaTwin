"""P09.3 root-approved dimension/placement plan, declared before any mesh."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[5]
def read(p): return json.loads((ROOT / p).read_text())
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()

dock = read("assets/v3/specs/dock-module.dimensions.json")
zones = read("docs/v3/contract-proposals/layout-v3.zones.json")
approaches = {a["port_id_context"]: a["keep_clear_overlay_xz_m"] for a in zones["port_approach_context"]}
ports = read("docs/v3/contract-proposals/ports-v3.inbound.json")["ports"] + read("docs/v3/contract-proposals/ports-v3.outbound.json")["ports"]
walls, columns, windows, gates = [], [], [], []

def bounds(side, a, b, y0, y1, d0=0, d1=.25):
    if side == "W": return {"min": [d0, y0, a], "max": [d1, y1, b]}
    if side == "E": return {"min": [144-d1, y0, a], "max": [144-d0, y1, b]}
    if side == "S": return {"min": [a, y0, d0], "max": [b, y1, d1]}
    return {"min": [a, y0, 72-d1], "max": [b, y1, 72-d0]}

sideport = {s: [] for s in ("W", "E", "S", "N")}
for p in ports:
    n = p["inward_facing"]
    side = "W" if n[0] == 1 else "E" if n[0] == -1 else "S" if n[2] == 1 else "N"
    pos, w, h = p["world_pos"], p["clear_width_m"], p["clear_height_m"]
    axis, half = (pos[2] if side in ("W", "E") else pos[0]), w/2
    sideport[side].append((axis-(w+.5)/2, axis+(w+.5)/2, h+.25, p["port_id"]))
    c = {k: copy.deepcopy(dock[k]) for k in ("steel_U", "tan_reveal_U", "foot_each", "bumper_each", "safety_band_each", "header_panel_each")}
    c["steel_U"].update(outer_half_width=half+.24, inner_half_width=half+.07, outer_top=h+.25, inner_top=h+.07)
    c["tan_reveal_U"].update(outer_half_width=half+.09, inner_half_width=half, outer_top=h+.09, inner_top=h)
    for k, offset in (("foot_each", .1325), ("bumper_each", .14), ("safety_band_each", .14)):
        c[k]["centre_abs_x"] = half+offset
    c["header_panel_each"].update(width=w+.32, y=[h+.15, h+.22])
    yaw = math.pi/2 if side == "W" else -math.pi/2 if side == "E" else 0 if side == "S" else math.pi
    gates.append({"port_id": p["port_id"], "side": side, "position": pos, "yaw_rad": yaw,
                  "clear_width_m": w, "clear_height_m": h, "construction": c,
                  "outer_span": [axis-(w+.5)/2, axis+(w+.5)/2], "outer_height_m": h+.25,
                  "local_bounds": {"min": [-half-.25, 0, 0], "max": [half+.25, h+.25, .25]},
                  "approach_keep_clear_xz_m": approaches[p["port_id"]]})
for side in ("W", "E", "S", "N"):
    height = 8 if side in ("S", "W") else 2.4
    lo, hi = (0, 72) if side in ("W", "E") else (.25, 143.75)
    cursor = lo
    for a, b, top, port in sorted(sideport[side]):
        if a > cursor: walls.append({"name": f"WALL__{side}__{len(walls):02d}", "side": side, "bounds": bounds(side, cursor, a, 0, height)})
        if height > top: walls.append({"name": "WALL_OVER__"+port, "side": side, "bounds": bounds(side, a, b, top, height)})
        cursor = b
    if cursor < hi: walls.append({"name": f"WALL__{side}__{len(walls):02d}", "side": side, "bounds": bounds(side, cursor, hi, 0, height)})
centres = []
for z, side, skip in ((.32, "S", 48), (71.68, "N", 72)):
    for x in [.32] + list(range(12, 144, 12)) + [143.68]:
        if x != skip: centres.append((x, z, 8 if side == "S" or x == .32 else 2.4, side))
for x, side, height in ((.32, "W", 8), (143.68, "E", 2.4)):
    for z in (12, 24, 36, 48, 60): centres.append((x, z, height, side))
assert len(centres) == 34
for i, (x, z, height, side) in enumerate(centres):
    pieces = []
    for suffix, width, y0, y1 in (("foot", .64, 0, .18), ("shaft", .44, .12, height-.08), ("cap", .52, height-.16, height)):
        pieces.append({"name": f"COLUMN__{i:02d}__{suffix}", "bounds": {"min": [x-width/2, y0, z-width/2], "max": [x+width/2, y1, z+width/2]}})
    columns.append({"column_id": f"COL_{i:02d}", "side": side, "centre_xz": [x, z], "height_m": height, "pieces": pieces})
for side in ("S", "W", "N", "E"):
    height = 8 if side in ("S", "W") else 2.4
    y, length = (6.2 if height == 8 else 1.5), (72 if side in ("W", "E") else 144)
    for centre in range(6, length, 12):
        a, b = centre-2.4, centre+2.4
        if any(min(b, q[1]) > max(a, q[0]) and y-.45 < q[2] for q in sideport[side]): continue
        panes, width = [], (4.55-.12)/3
        for i in range(3):
            c = centre+(i-1)*(width+.06)
            panes.append({"name": f"WINDOW__{side}_{centre:03d}__pane{i}", "bounds": bounds(side, c-width/2, c+width/2, y-.325, y+.325, .28, .30)})
        windows.append({"window_id": f"WIN_{side}_{centre:03d}", "side": side, "role": "opaque architectural panel, not see-through",
                        "backing": {"name": f"WINDOW__{side}_{centre:03d}__backing", "bounds": bounds(side, a, b, y-.45, y+.45, .23, .29)}, "panes": panes})
inputs = ["layout-v3.envelope.json", "ports-v3.inbound.json", "ports-v3.outbound.json", "large-gate-v3.json", "layout-links-v3.json", "pedestrian-graph-v3.json", "vehicle-graph-v3.json", "storage-layout-v3.json", "layout-conflicts-v3.json"]
inputs = ["docs/v3/contract-proposals/"+p for p in inputs] + ["tools/blender/v3/build_dock_module.py", "tools/blender/v3/build_large_gate.py", "frontend/public/models/v3/dock-module.glb", "frontend/public/models/v3/large-gate.glb", "frontend/public/models/v3/large-gate-b2b.glb"]
plan = {"schema": "qoima-environment-shell-dimensions-v1", "declared_at": datetime.now(timezone.utc).isoformat(), "root_design_approved": True,
        "asset_id": "environment-shell", "root_name": "environment_shell_root", "units": "m", "up_axis": "Y", "forward_axis": "+Z", "origin": "operational floor minimum corner(0,0,0)",
        "operational_floor_bounds": {"min": [0, 0, 0], "max": [144, 0, 72]}, "ceiling_limit_y_m": 8,
        "overall_bounds_including_display_plinth": {"min": [-.6, -.55, -.6], "max": [144.6, 8, 72.6]},
        "floor_slab": {"name": "FLOOR__operational_support", "bounds": {"min": [0, -.28, 0], "max": [144, 0, 72]}, "role": "floor support; topY0, not raised obstacle"},
        "display_plinth": {"name": "DISPLAY_ONLY__plinth", "bounds": {"min": [-.6, -.55, -.6], "max": [144.6, -.28, 72.6]}, "bevel_m": .10, "role": "display-only below floor; not operational obstacle"},
        "cutaway": {"open_roof": True, "S_height_m": 8, "W_height_m": 8, "N_height_m": 2.4, "E_height_m": 2.4, "overview_camera_direction": "+X,+Z(NE)", "near_gate_frames_may_rise_above_cut_wall": True, "interior_columns": 0},
        "wall_thickness_m": .25, "wall_material_bands": {"base_petrol_y": [0, .9], "warm_grey": "above.9 except cap", "charcoal_cap": "last.12m"},
        "walls": walls, "columns": columns, "windows": windows, "gates": gates,
        "materials": {"floor": "#D8D8CF", "plinth": "#AFB4AE", "wall": "#C7C8BD", "petrol": "#2E7376", "charcoal": "#293D46", "opaque_pane": "#EFF1E8", "gate_tan": "#C99A60", "safety": "#E3B85B"},
        "architectural_approach_exception": "Root-approved own perimeter boundary pieces may intersect approach rectangles outside clear apertures; list intersections, do not claim whole approach rectangle empty. All actualL12capsules/vehicle profiles/6port crossings must clear actual source envelopes.",
        "geometry_not_started_at_declaration": True, "operational_admission": False,
        "contents_excluded": ["stock", "racks", "people", "vehicles", "inventory", "roof", "interior columns"],
        "readonly_sha256": {p: sha(p) for p in inputs},
        "reference_sha256": {p: sha(p) for p in ("assets/references/v3/r07-ports-zones.png", "assets/references/v3/r08-composition.png")}}
(ROOT / "assets/v3/specs/environment-shell.dimensions.json").write_text(json.dumps(plan, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"walls": len(walls), "columns": len(columns), "windows": len(windows), "gates": len(gates), "declared_before_geometry": True}))
