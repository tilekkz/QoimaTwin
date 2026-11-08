"""Isolated metre/Y-up V3 authoring and export API; old helpers stay read-only.

Geometry locations are parent-local runtime XYZ. xyz maps them once to Blender
(x,-z,y); glTF's Y-up export maps them back. Never rotate the root a second time.
Named anchor/pivot locations use the same parent-local convention.

finish saves editable source first, then applies modifiers and optionally joins
only meshes sharing BOTH their immediate parent and material tuple. Rigid joint
empties/anchors therefore survive even when preserve_articulation is true.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
import struct
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
import asset_common as _legacy

VERSION = "qoima-144x72-v3"
NAMESPACE = "v3"
ASSET_COLLECTION = "V3_ASSET"
STUDIO_COLLECTION = "V3_STUDIO"
PALETTE = {"charcoal": "#293D46", "petrol": "#2E7376", "tan": "#C99A60",
           "offwhite": "#E8E3D9", "picker": "#3478F6", "packer": "#F28C28",
           "receiver": "#9B59D0", "shipper": "#2AA56A", "driver": "#F4C542"}


def xyz(point):
    """Parent-local runtime metres -> Blender metres, exactly once."""
    if len(point) != 3 or not all(math.isfinite(float(v)) for v in point):
        raise ValueError("Expected three finite coordinates")
    return _legacy.xyz(point)


def runtime_xyz(point):
    return [float(point[0]), float(point[2]), -float(point[1])]


def _layer(collection, layer):
    if layer.collection == collection:
        return layer
    return next((found for child in layer.children
                 if (found := _layer(collection, child)) is not None), None)


def reset():
    """Fresh task-background scene only; never call in live Blender."""
    _legacy.reset()
    for name in (ASSET_COLLECTION, STUDIO_COLLECTION):
        collection = bpy.data.collections.get(name)
        if collection is None:
            collection = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.active_layer_collection = _layer(
        bpy.data.collections[ASSET_COLLECTION], bpy.context.view_layer.layer_collection)


def material(name, color, roughness=.85, metallic=0):
    return _legacy.material(name, color, roughness, metallic)


def group(name, parent=None, loc=(0, 0, 0)):
    obj = _legacy.group(name)
    obj.parent = parent
    obj.location = xyz(loc)
    obj["namespace"] = NAMESPACE
    obj["layout_version"] = VERSION
    obj["units"] = "m"
    obj["up_axis"] = "Y"
    obj["forward_axis"] = "+Z"
    return obj


def anchor(name, loc=(0, 0, 0), parent=None, role="attachment_anchor"):
    obj = group(name, parent, loc)
    obj["anchor_id"] = name
    obj["role"] = role
    obj["bind_local_runtime"] = list(loc)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = .06
    return obj


def pivot(name, loc=(0, 0, 0), parent=None, axis="Y"):
    if axis not in {"X", "Y", "Z"}:
        raise ValueError("Pivot axis must be runtime X, Y or Z")
    obj = group(name, parent, loc)
    obj["pivot_id"] = name
    obj["role"] = "rigid_joint_pivot"
    obj["rotation_axis_runtime"] = axis
    obj["bind_local_runtime"] = list(loc)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = .08
    return obj


def box(name, loc, size, mat, parent=None, bevel=.008):
    if any(float(value) <= 0 for value in size):
        raise ValueError("Box dimensions must be positive")
    return _legacy.box(name, loc, size, mat, parent, bevel)


def cylinder(name, loc, radius, depth, mat, parent=None, axis="Y", vertices=8):
    return _legacy.cylinder(name, loc, radius, depth, mat, parent, axis, vertices)


def beam(name, start, end, width, mat, parent=None):
    return _legacy.beam(name, start, end, width, mat, parent)


def _meshes(root):
    return ([root] if root.type == "MESH" else []) + [
        obj for obj in root.children_recursive if obj.type == "MESH"]


def _bounds(objects):
    points = [runtime_xyz(obj.matrix_world @ vertex.co)
              for obj in objects for vertex in obj.data.vertices]
    if not points or not all(math.isfinite(c) for point in points for c in point):
        raise ValueError("Asset has empty or non-finite geometry")
    low = [min(point[axis] for point in points) for axis in range(3)]
    high = [max(point[axis] for point in points) for axis in range(3)]
    return {"min": low, "max": high}


def finish(asset_id, root, batch_runtime=True, preserve_shape_keys=False):
    """Export selected root hierarchy only; return actual Y-up vertex stats.

    batch_runtime=False preserves individual mesh names. True batches within
    each immediate parent/material group, never across any joint or anchor.
    preserve_shape_keys=True retains modifier-free keyed meshes separately;
    the default conversion/batching path remains unchanged for existing assets.
    preserve_articulation is recorded, and named parents survive in both modes.
    """
    if not bpy.app.background:
        raise RuntimeError("Export only from a task-background Blender process")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", asset_id):
        raise ValueError("Invalid V3 asset_id")
    source = ROOT / "assets/v3/blender" / (asset_id + ".blend")
    output = ROOT / "frontend/public/models/v3" / (asset_id + ".glb")
    source.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    for key, value in {"namespace": NAMESPACE, "asset_id": asset_id,
                       "layout_version": VERSION, "units": "m",
                       "up_axis": "Y", "forward_axis": "+Z"}.items():
        root[key] = value
    if "role" not in root:
        root["role"] = "visual_asset"
    bpy.context.view_layer.update()
    meshes = _meshes(root)
    if not meshes:
        raise ValueError("Cannot export an asset without meshes")
    # Source is saved with editable bevels and separate components intact.
    # Versioned snapshots belong to task checkpoints, not implicit .blend1 files.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    bpy.ops.object.select_all(action="DESELECT")
    convertible = [obj for obj in meshes if not (preserve_shape_keys and obj.data.shape_keys)]
    keyed = [obj for obj in meshes if preserve_shape_keys and obj.data.shape_keys]
    if any(obj.modifiers for obj in keyed):
        raise ValueError("Morph-preserving export requires already evaluated modifier-free keyed meshes")
    for obj in convertible:
        obj.select_set(True)
    if convertible:
        bpy.context.view_layer.objects.active = convertible[0]
        bpy.ops.object.convert(target="MESH")
    meshes = _meshes(root)
    bpy.context.view_layer.update()
    components = [{"name": obj.name, "parent": obj.parent.name if obj.parent else None,
                   "bounds_runtime": _bounds([obj]), "vertices": len(obj.data.vertices)}
                  for obj in meshes]
    if batch_runtime:
        batches = {}
        for obj in meshes:
            key = (obj.parent, tuple(mat.name if mat else None for mat in obj.data.materials),
                   obj if preserve_shape_keys and obj.data.shape_keys else None)
            batches.setdefault(key, []).append(obj)
        for index, ((parent, _, _), parts) in enumerate(batches.items()):
            names = [obj.name for obj in parts]
            bpy.ops.object.select_all(action="DESELECT")
            for obj in parts:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = parts[0]
            if len(parts) > 1:
                bpy.ops.object.join()
            obj = bpy.context.view_layer.objects.active
            obj.name = f"{asset_id}__batch_{index:02d}"
            obj["source_parts_json"] = json.dumps(names)
            obj["batch_parent"] = parent.name if parent else ""
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for obj in root.children_recursive:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB",
                             export_yup=True, export_extras=True, use_selection=True,
                             export_texcoords=False, export_cameras=False, export_lights=False)
    bpy.context.view_layer.update()
    meshes = _meshes(root)
    bounds = _bounds(meshes)
    triangles = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
    nodes = [root] + list(root.children_recursive)
    anchors = {obj.name: runtime_xyz(obj.matrix_world.translation)
               for obj in nodes if obj.get("anchor_id")}
    pivots = {obj.name: {"position_runtime": runtime_xyz(obj.matrix_world.translation),
                         "local_runtime": runtime_xyz(obj.location),
                         "parent": obj.parent.name if obj.parent else None,
                         "axis": obj.get("rotation_axis_runtime")}
              for obj in nodes if obj.get("pivot_id")}
    content = output.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", content)
    if (magic, version, length) != (b"glTF", 2, len(content)):
        raise ValueError("Invalid exported GLB header")
    report = {"asset_id": asset_id, "namespace": NAMESPACE, "layout_version": VERSION,
              "units": "m", "up_axis": "Y", "forward_axis": "+Z",
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "blender_version": bpy.app.version_string,
              "source": str(source), "glb": str(output), "glb_bytes": len(content),
              "sha256": hashlib.sha256(content).hexdigest(),
              "source_meshes": len(components), "runtime_meshes": len(meshes),
              "triangles": triangles, "bounds_runtime": bounds,
              "dimensions_m": [bounds["max"][i] - bounds["min"][i] for i in range(3)],
              "runtime_size": [bounds["max"][i] - bounds["min"][i] for i in range(3)],
              "anchors": anchors, "pivots": pivots, "components": components,
              "runtime_components": [{"name": obj.name,
                                      "parent": obj.parent.name if obj.parent else None,
                                      "bounds_runtime": _bounds([obj])} for obj in meshes],
              "batching": "immediate_parent_and_material" if batch_runtime else "none",
              "preserve_articulation": bool(root.get("preserve_articulation", False)),
              "root_matrix_blender": [list(row) for row in root.matrix_world],
              "glb_header": {"magic": "glTF", "version": version, "declared_bytes": length}}
    if preserve_shape_keys:
        report['morph_targets_preserved'] = {obj.name: [key.name for key in obj.data.shape_keys.key_blocks][1:]
                                            for obj in meshes if obj.data.shape_keys}
    (source.parent / (asset_id + ".stats.json")).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("V3_ASSET_EXPORTED " + json.dumps(report))
    return report
