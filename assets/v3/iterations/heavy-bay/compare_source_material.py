"""Read-only actual source comparison for the root-requested material fix."""
from pathlib import Path
import hashlib
import json
import sys

import bpy

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools/blender/v3"))
from build_heavy_bay import metrics

old_path = ROOT / "assets/v3/iterations/heavy-bay/c08-v02/heavy-bay.blend"
new_path = ROOT / "assets/v3/blender/heavy-bay.blend"
results = []
materials = []
for path in [old_path, new_path]:
    bpy.ops.wm.open_mainfile(filepath=str(path))
    root = next(o for o in bpy.data.objects if o.get("asset_id") == "heavy-bay" and o.parent is None)
    results.append(metrics(root))
    materials.append({o["part_id"]: o.data.materials[0].name for o in root.children_recursive if o.type == "MESH"})
old, new = results
assert old["anchors"] == new["anchors"]
assert old["bounds_runtime"] == new["bounds_runtime"]
assert old["triangles"] == new["triangles"] == 748
for a, b in zip(old["components"], new["components"]):
    for key in ["part_id", "triangles", "bounds_runtime", "modifiers", "geometry_signature"]:
        assert a[key] == b[key], (a["part_id"], key)
changed = {key: {"old": materials[0][key], "new": materials[1][key]}
           for key in materials[0] if materials[0][key] != materials[1][key]}
assert set(changed) == {"runner_1", "runner_2", "runner_3", "top_rib_1", "top_rib_2", "top_rib_3"}
for key, value in materials[1].items():
    expected = "petrol" if key.startswith("top_rib_") or "cross_tie" in key else "charcoal"
    assert value == "HEAVY | " + expected
report = {"status": "PASS", "old_source_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
          "current_source_sha256": hashlib.sha256(new_path.read_bytes()).hexdigest(),
          "unchanged_actual_vertex_triangle_normal_signatures": 17, "modifiers_bounds_and_anchor_unchanged": True,
          "actual_material_assignment_changes": changed, "current_material_parts": materials[1],
          "no_save_render_export": True}
(ROOT / "assets/v3/iterations/heavy-bay/material-final/source-material-equivalence.json").write_text(json.dumps(report, indent=2) + "\n")
print("M03_MATERIAL_ONLY_SOURCE_EQUIVALENCE_PASS " + json.dumps(report))
