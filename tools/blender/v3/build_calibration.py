"""Build and independently decode one numeric V3 GLB (no render/browser).

Expected values live in calibration.expected.json, declared before geometry.
The decoder reads actual glTF Y-up POSITION bytes/TRS; it does not call xyz or
trust exported accessor AABBs. This accepts pipeline coordinates, not final art.
"""
from pathlib import Path
import json
import math
import struct

from mathutils import Matrix, Quaternion, Vector
from v3_common import ROOT, reset, finish, group, box, anchor, pivot, material

EXPECTED = ROOT / "assets/v3/blender/calibration.expected.json"


def build():
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    root = group(expected["root_name"])
    root["role"] = "numeric_calibration_not_final_art"
    root["preserve_articulation"] = True
    root["expected_file"] = "assets/v3/blender/calibration.expected.json"
    root["declared_dimensions_m"] = expected["dimensions_m"]
    root["origin_description"] = "Runtime floor origin, unrotated and unscaled"
    red = material("V3_Calibration_X", "#BC554B")
    green = material("V3_Calibration_Y", "#52896C")
    blue = material("V3_Calibration_Z", "#527DA0")
    tan = material("V3_Calibration_Asymmetric", "#C99A60")
    for name, colour in (("axis_X_1m", red), ("axis_Y_2m", green),
                         ("axis_Z_3m", blue), ("asymmetric_box", tan)):
        spec = expected["parts"][name]
        box(name, spec["centre"], spec["size"], colour, root, bevel=spec.get("bevel_m", 0))
    a = pivot("joint__calibration_A", (.45, .3, 1.7), root, axis="Y")
    b = pivot("joint__calibration_B", (.25, .1, .2), a, axis="X")
    for name, parent in (("joint_A_part_1", a), ("joint_A_part_2", a),
                         ("joint_B_part", b)):
        spec = expected["parts"][name]
        obj = box(name, spec["local_centre"], spec["size"], tan, parent, bevel=0)
        # Blender Z is runtime Y; the retained rotated mesh frame exercises the
        # precise-vertex bounds path after its sibling is joined into this mesh.
        obj.rotation_euler.z = spec.get("local_yaw_radians", 0)
    for name, point in expected["anchors"].items():
        if name != "anchor_nested":
            anchor(name, point, root)
    anchor("anchor_nested", (.05, .3, .15), b)
    return root


def _near(actual, expected, tolerance, label):
    if len(actual) != len(expected) or any(abs(a - b) > tolerance for a, b in zip(actual, expected)):
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def _read_glb(path):
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", raw)
    if (magic, version, length) != (b"glTF", 2, len(raw)):
        raise AssertionError("GLB magic/version/length mismatch")
    document, binary = None, None
    offset = 12
    while offset < len(raw):
        size, kind = struct.unpack_from("<I4s", raw, offset)
        offset += 8
        chunk = raw[offset:offset + size]
        if len(chunk) != size:
            raise AssertionError("Truncated GLB chunk")
        if kind == b"JSON":
            document = json.loads(chunk.decode("utf-8").rstrip("\x00 "))
        elif kind == b"BIN\x00":
            binary = chunk
        offset += size
    if document is None or binary is None or offset != len(raw):
        raise AssertionError("Missing or malformed GLB chunks")
    return document, binary


def _positions(document, binary, accessor_id):
    accessor = document["accessors"][accessor_id]
    if accessor["componentType"] != 5126 or accessor["type"] != "VEC3" or "sparse" in accessor:
        raise AssertionError("Calibration expects dense float VEC3 attributes")
    view = document["bufferViews"][accessor["bufferView"]]
    if view.get("buffer", 0) != 0:
        raise AssertionError("Unexpected external calibration buffer")
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = view.get("byteStride", 12)
    values = [struct.unpack_from("<3f", binary, start + i * stride)
              for i in range(accessor["count"])]
    if not all(math.isfinite(c) for value in values for c in value):
        raise AssertionError("Non-finite exported vertex attribute")
    return values


def _node_matrix(node):
    if "matrix" in node:
        values = node["matrix"]
        return Matrix([[values[column * 4 + row] for column in range(4)] for row in range(4)])
    tx, ty, tz = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = node.get("scale", [1, 1, 1])
    return (Matrix.Translation((tx, ty, tz)) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
            @ Matrix.Diagonal((sx, sy, sz, 1)))


def verify_export(report):
    """Verify actual binary independently of authoring conversion and stats."""
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    tolerance = expected["tolerance_m"]
    document, binary = _read_glb(Path(report["glb"]))
    nodes = document["nodes"]
    by_name = {node.get("name"): i for i, node in enumerate(nodes)}
    world, parents = {}, {}

    def visit(index, parent_matrix, parent_index=None):
        if index in world:
            raise AssertionError("Repeated/cyclic scene node")
        world[index] = parent_matrix @ _node_matrix(nodes[index])
        parents[index] = parent_index
        for child in nodes[index].get("children", []):
            visit(child, world[index], index)

    for index in document["scenes"][document.get("scene", 0)]["nodes"]:
        visit(index, Matrix.Identity(4))
    root_index = by_name[expected["root_name"]]
    root = nodes[root_index]
    for key in ("asset_id", "namespace", "units", "up_axis", "forward_axis", "layout_version"):
        if root.get("extras", {}).get(key) != expected[key]:
            raise AssertionError(f"Missing/incorrect root extra {key}")
    for row in range(4):
        _near(list(world[root_index][row]), list(Matrix.Identity(4)[row]), tolerance, "root identity")
    points, normal_count, mesh_nodes, per_node_points = [], 0, [], {}
    for index, matrix in world.items():
        node = nodes[index]
        if "mesh" not in node:
            continue
        mesh_nodes.append(index)
        per_node_points[index] = []
        for primitive in document["meshes"][node["mesh"]]["primitives"]:
            for value in _positions(document, binary, primitive["attributes"]["POSITION"]):
                point = matrix @ Vector((*value, 1))
                points.append(list(point[:3]))
                per_node_points[index].append(list(point[:3]))
            normals = _positions(document, binary, primitive["attributes"]["NORMAL"])
            if any(abs(sum(c * c for c in value) - 1) > 0.0001 for value in normals):
                raise AssertionError("Non-unit exported normal")
            normal_count += len(normals)
    bounds = {"min": [min(p[i] for p in points) for i in range(3)],
              "max": [max(p[i] for p in points) for i in range(3)]}
    for edge in ("min", "max"):
        _near(bounds[edge], expected["bounds_runtime"][edge], tolerance, "GLB bounds " + edge)
        _near(bounds[edge], report["bounds_runtime"][edge], tolerance, "stats/GLB " + edge)
    dimensions = [bounds["max"][i] - bounds["min"][i] for i in range(3)]
    _near(dimensions, expected["dimensions_m"], tolerance, "GLB dimensions")
    anchors = {}
    for name, target in expected["anchors"].items():
        anchors[name] = list(world[by_name[name]].translation)
        _near(anchors[name], target, tolerance, name)
        _near(anchors[name], report["anchors"][name], tolerance, "stats/GLB " + name)
    for name, spec in expected["pivots"].items():
        index = by_name[name]
        _near(list(world[index].translation), spec["position_runtime"], tolerance, name)
        parent_name = nodes[parents[index]]["name"] if parents[index] is not None else None
        if parent_name != spec["parent"]:
            raise AssertionError("Joint hierarchy lost: " + name)
    if parents[by_name["anchor_nested"]] != by_name[expected["nested_anchor_parent"]]:
        raise AssertionError("Nested anchor lost its joint parent")
    if len(mesh_nodes) != expected["runtime_mesh_count"] or report["source_meshes"] != expected["source_mesh_count"]:
        raise AssertionError("Unexpected calibration material batching")
    for name in expected["pivots"]:
        child_meshes = [i for i in mesh_nodes if parents[i] == by_name[name]]
        if len(child_meshes) != 1:
            raise AssertionError("Cross-joint merge or unbatched A components: " + name)
        if name == "joint__calibration_A":
            values = per_node_points[child_meshes[0]]
            actual_batch = {"min": [min(p[i] for p in values) for i in range(3)],
                            "max": [max(p[i] for p in values) for i in range(3)]}
            stats_batch = next(component["bounds_runtime"] for component in report["runtime_components"]
                               if component["parent"] == name)
            for edge in ("min", "max"):
                _near(actual_batch[edge], expected["joint_A_batch_bounds_runtime"][edge], tolerance, "rotated A batch " + edge)
                _near(stats_batch[edge], actual_batch[edge], tolerance, "stats precise-vertex A batch " + edge)
    for mat in document.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        values = pbr.get("baseColorFactor", [1, 1, 1, 1]) + [pbr.get("roughnessFactor", 1), pbr.get("metallicFactor", 1)]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise AssertionError("Invalid material factors")
    return {"status": "verified_numerically", "method": "actual GLB float POSITION/NORMAL bytes + node TRS, independent of xyz",
            "bounds_runtime": bounds, "dimensions_m": dimensions, "anchors": anchors,
            "runtime_meshes": len(mesh_nodes), "finite_positions": len(points),
            "finite_unit_normals": normal_count, "named_pivots_preserved": list(expected["pivots"]),
            "root_identity": True, "parent_material_batching": True,
            "rotated_joined_mesh_bounds": "verified against independent hand-declared A-batch bounds",
            "khronos_validation": "pending root I09.3", "browser_views": "not run; root I09.3"}


if __name__ == "__main__":
    # Read the independent declared target before reset or geometry creation.
    json.loads(EXPECTED.read_text(encoding="utf-8"))
    reset()
    report = finish("calibration", build())
    report["glb_numeric_verification"] = verify_export(report)
    path = EXPECTED.with_name("calibration.stats.json")
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("V3_CALIBRATION_VERIFIED " + json.dumps(report["glb_numeric_verification"]))
