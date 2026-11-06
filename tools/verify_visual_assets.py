"""Verify generated local visual GLBs with Python stdlib; no Blender or network.

This is project-specific structural/metric verification, not a replacement for
the Khronos glTF validator. Bounds are computed from actual POSITION vertices
and node world transforms, never transformed local AABB corners.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "frontend" / "public" / "models"
TOLERANCE = 1e-5
ASSETS = ("rack-bay", "crate", "picker-cart", "packing-station",
          "buffer-pallet", "forklift", "ibc-tote", "environment")
COMPONENTS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
              5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4,
          "MAT2": 4, "MAT3": 9, "MAT4": 16}
IDENTITY = [[float(i == j) for j in range(4)] for i in range(4)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_json(value, path="json"):
    if isinstance(value, float):
        require(math.isfinite(value), f"Nonfinite number at {path}")
    elif isinstance(value, dict):
        for key, item in value.items():
            finite_json(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite_json(item, f"{path}[{index}]")


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4))
             for j in range(4)] for i in range(4)]


def node_matrix(node):
    if "matrix" in node:
        require(len(node["matrix"]) == 16, "Node matrix must have 16 values")
        return [[node["matrix"][j * 4 + i] for j in range(4)] for i in range(4)]
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    require(abs(x*x+y*y+z*z+w*w-1) < 1e-4, "Nonunit node quaternion")
    sx, sy, sz = node.get("scale", [1, 1, 1])
    tx, ty, tz = node.get("translation", [0, 0, 0])
    rotation = [
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ]
    scales = (sx, sy, sz)
    return [[rotation[i][j]*scales[j] for j in range(3)] + [[tx, ty, tz][i]]
            for i in range(3)] + [[0, 0, 0, 1]]


def determinant3(m):
    return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
            - m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
            + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))


def transform(matrix, row):
    return tuple(sum(matrix[i][j]*row[j] for j in range(3)) + matrix[i][3]
                 for i in range(3))


def close(actual, expected, label, tolerance=TOLERANCE):
    require(abs(actual-expected) <= tolerance,
            f"{label}: {actual:.9g}, expected {expected:.9g} +/- {tolerance:g}")


def parse_glb(path):
    blob = path.read_bytes()
    require(len(blob) >= 20, "GLB is too short")
    magic, version, declared_length = struct.unpack_from("<4sII", blob)
    require(magic == b"glTF" and version == 2, "Expected GLB version 2")
    require(declared_length == len(blob), "GLB header byte length mismatch")
    chunks = []
    offset = 12
    while offset < len(blob):
        require(offset+8 <= len(blob), "Truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", blob, offset)
        offset += 8
        require(length % 4 == 0, "Chunk is not four-byte aligned")
        require(offset+length <= len(blob), "Truncated GLB chunk body")
        chunks.append((kind, blob[offset:offset+length]))
        offset += length
    require(chunks and chunks[0][0] == 0x4E4F534A, "First chunk must be JSON")
    require(len(chunks) == 2 and chunks[1][0] == 0x004E4942,
            "Expected exactly embedded JSON and BIN chunks")
    document = json.loads(chunks[0][1].decode("utf-8").rstrip(" \0\t\r\n"))
    finite_json(document)
    require(document.get("asset", {}).get("version") == "2.0", "Not glTF 2.0")
    buffers = document.get("buffers", [])
    require(len(buffers) == 1 and "uri" not in buffers[0],
            "Expected one embedded buffer and no external buffer URI")
    binary = chunks[1][1]
    require(0 <= len(binary)-buffers[0]["byteLength"] <= 3,
            "Embedded buffer length or padding mismatch")
    require(not document.get("extensionsRequired"), "Required extensions are unsupported")
    for image in document.get("images", []):
        require("uri" not in image and "bufferView" in image, "External image URI")
    for view in document.get("bufferViews", []):
        require(view.get("buffer", 0) == 0, "External bufferView")
        require(view.get("byteOffset", 0) >= 0 and view["byteLength"] >= 0,
                "Negative bufferView bounds")
        require(view.get("byteOffset", 0)+view["byteLength"] <= buffers[0]["byteLength"],
                "bufferView exceeds embedded buffer")
    return document, binary, len(blob)


def inspect(asset_id):
    path = MODELS / (asset_id+".glb")
    document, binary, byte_count = parse_glb(path)
    require(byte_count < 5_000_000, "Asset exceeds 5 MB budget")
    accessors = document.get("accessors", [])
    views = document.get("bufferViews", [])
    decoded = {}
    for index, accessor in enumerate(accessors):
        require("sparse" not in accessor, "Sparse accessor outside this verifier's scope")
        require("bufferView" in accessor, "Accessor missing embedded bufferView")
        require(accessor["componentType"] in COMPONENTS, "Unknown accessor component type")
        require(accessor["type"] in WIDTHS, "Unknown accessor shape")
        component, size = COMPONENTS[accessor["componentType"]]
        count = accessor["count"]
        require(isinstance(count, int) and count >= 0, "Invalid accessor count")
        width = WIDTHS[accessor["type"]]
        view = views[accessor["bufferView"]]
        stride = view.get("byteStride", width*size)
        relative = accessor.get("byteOffset", 0)
        require(relative >= 0 and stride >= width*size and stride % size == 0,
                "Invalid accessor offset/stride")
        used = relative + (count-1)*stride + width*size if count else relative
        require(used <= view["byteLength"], "Accessor exceeds bufferView")
        offset = view.get("byteOffset", 0)+relative
        unpack = struct.Struct("<"+component*width).unpack_from
        rows = [unpack(binary, offset+row*stride) for row in range(count)]
        if accessor["componentType"] == 5126:
            require(all(math.isfinite(v) for row in rows for v in row),
                    f"Nonfinite float in accessor {index}")
        decoded[index] = rows
        for bound_key in ("min", "max"):
            if bound_key in accessor and rows:
                require(len(accessor[bound_key]) == width, "Accessor bound shape mismatch")
                for axis in range(width):
                    measured = (min if bound_key == "min" else max)(r[axis] for r in rows)
                    close(measured, accessor[bound_key][axis],
                          f"Accessor {index} {bound_key}[{axis}]")
    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    require(nodes and meshes, "Missing nodes or meshes")
    scene = document.get("scenes", [])[document.get("scene", 0)]
    scene_roots = scene.get("nodes", [])
    require(scene_roots, "Scene has no roots")
    minimum = [math.inf]*3
    maximum = [-math.inf]*3
    triangle_count = 0
    primitive_count = 0
    vertex_instances = 0
    seen = set()

    def visit(index, parent_world, ancestors):
        nonlocal triangle_count, primitive_count, vertex_instances
        require(index not in ancestors, "Node graph contains a cycle")
        require(index not in seen, "Node has multiple parents in selected scene")
        seen.add(index)
        node = nodes[index]
        world = multiply(parent_world, node_matrix(node))
        if "mesh" in node:
            for primitive in meshes[node["mesh"]]["primitives"]:
                require(primitive.get("mode", 4) == 4, "Expected triangle primitives")
                position_id = primitive["attributes"]["POSITION"]
                require(accessors[position_id]["type"] == "VEC3"
                        and accessors[position_id]["componentType"] == 5126,
                        "POSITION must be float VEC3")
                positions = decoded[position_id]
                require(positions, "Empty POSITION accessor")
                if "indices" in primitive:
                    index_id = primitive["indices"]
                    require(accessors[index_id]["type"] == "SCALAR", "Indices must be scalar")
                    indices = [row[0] for row in decoded[index_id]]
                    require(all(isinstance(i, int) and 0 <= i < len(positions) for i in indices),
                            "Index outside POSITION accessor")
                    element_count = len(indices)
                else:
                    element_count = len(positions)
                require(element_count % 3 == 0, "Triangle primitive count not divisible by three")
                triangle_count += element_count//3
                primitive_count += 1
                vertex_instances += len(positions)
                for row in positions:
                    point = transform(world, row)
                    require(all(math.isfinite(v) for v in point), "Nonfinite world position")
                    for axis in range(3):
                        minimum[axis] = min(minimum[axis], point[axis])
                        maximum[axis] = max(maximum[axis], point[axis])
        for child in node.get("children", []):
            visit(child, world, ancestors | {index})

    root_names = []
    for index in scene_roots:
        matrix = node_matrix(nodes[index])
        root_names.append(nodes[index].get("name", str(index)))
        close(determinant3(matrix), 1, "Root positive unit determinant")
        for axis in range(3):
            close(math.sqrt(sum(matrix[row][axis]**2 for row in range(3))),
                  1, "Root unit scale")
            close(matrix[axis][3], 0, "Root origin translation")
        visit(index, IDENTITY, set())
    require(triangle_count > 0, "No visible triangles")
    size = [maximum[i]-minimum[i] for i in range(3)]
    checks = ["embedded_glb_v2", "finite_json_and_binary_floats",
              "valid_accessor_and_index_ranges", "no_external_resources",
              "no_required_extensions", "positive_unit_scale_roots_at_origin",
              "world_position_bounds", "triangles_present", "under_5MB"]
    stats_path = ROOT / "assets" / "blender" / (asset_id+".stats.json")
    stats = None
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        finite_json(stats, "stats")
        require(stats["asset_id"] == asset_id, "Stats asset ID mismatch")
        require(stats["glb_bytes"] == byte_count, "Stats byte count mismatch")
        require(stats["triangles"] == triangle_count, "Stats triangle count mismatch")
        blender_min = stats["bounds_blender"]["min"]
        blender_max = stats["bounds_blender"]["max"]
        expected_min = [blender_min[0], blender_min[2], -blender_max[1]]
        expected_max = [blender_max[0], blender_max[2], -blender_min[1]]
        for axis in range(3):
            close(minimum[axis], expected_min[axis], f"Stats minimum axis {axis}")
            close(maximum[axis], expected_max[axis], f"Stats maximum axis {axis}")
            close(size[axis], stats["runtime_size"][axis], f"Stats size axis {axis}")
        checks.append("stats_match_actual_glb_vertices")
    if asset_id == "crate":
        for axis in range(3):
            close((minimum[axis]+maximum[axis])/2, 0, "Crate centred origin")
        checks.append("crate_centred_origin")
    elif asset_id in ("environment", "warehouse"):
        require(-.20 <= minimum[1] < 0, "Expected shallow environment floor below Y=0")
        checks.append("environment_floor_below_zero")
    else:
        close(minimum[1], 0, "Ground contact")
        checks.append("floor_origin")
    fixed = {"rack-bay": (.9, 2.6, 1.5), "crate": (.55, .45, .65),
             "buffer-pallet": (1.4, .075, 1), "ibc-tote": (1.1, 1.2, 1)}
    if asset_id in fixed:
        for axis, expected in enumerate(fixed[asset_id]):
            close(size[axis], expected, f"Fixed dimension axis {axis}")
        checks.append("fixed_dimensions_1e-5m")
    if asset_id == "packing-station":
        close(size[0], 2.2, "Packing station width")
        close(size[2], 1, "Packing station depth")
        checks.append("packing_fixed_footprint_1e-5m")
    if asset_id == "picker-cart":
        close(size[1], 1.7, "Picker height")
        require(size[0] <= .8+TOLERANCE, "Picker/cart exceeds .8m aisle width")
        checks.append("picker_height_and_width")
    if asset_id == "environment":
        close(size[0], 20, "Environment width")
        close(size[2], 18, "Environment depth")
        checks.append("environment_fixed_footprint_1e-5m")
    if asset_id == "forklift":
        for axis, expected in enumerate((1.11, 2.15, 2.62)):
            close(size[axis], expected, f"Forklift nominal dimension axis {axis}", .01)
        checks.append("forklift_nominal_dimensions_0.01m")
    return {"asset_id": asset_id, "path": path.relative_to(ROOT).as_posix(),
            "status": "passed", "bytes": byte_count, "triangles": triangle_count,
            "mesh_definitions": len(meshes), "draw_primitives": primitive_count,
            "vertex_instances": vertex_instances, "nodes": len(nodes),
            "scene_roots": root_names, "bounds_runtime": {"min": minimum, "max": maximum},
            "size_m": size, "checks": checks,
            "stats_source": stats_path.relative_to(ROOT).as_posix() if stats else None}


def main():
    asset_ids = list(ASSETS)
    if (MODELS / "warehouse.glb").exists():
        asset_ids.append("warehouse")
    results = []
    for asset_id in asset_ids:
        try:
            result = inspect(asset_id)
        except (ValueError, KeyError, IndexError, TypeError, OSError, struct.error) as error:
            result = {"asset_id": asset_id, "status": "failed", "error": str(error)}
        results.append(result)
        print(f"{asset_id}: {result['status']}" +
              (f" | {result['error']}" if "error" in result else
               f" | {result['triangles']} triangles | {result['bytes']} bytes"))
    passed = all(result["status"] == "passed" for result in results)
    report = {"schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
              "status": "passed" if passed else "failed", "asset_count": len(results),
              "fixed_dimension_tolerance_m": TOLERANCE,
              "forklift_nominal_dimension_tolerance_m": .01,
              "method": "stdlib GLB JSON/BIN parse; actual POSITION vertices with node world transforms",
              "limitations": ["Project-specific checks; Khronos glTF validator is separate.",
                              "Rejects sparse accessors and non-triangle primitives."],
              "assets": results}
    output = ROOT / "assets" / "visual-asset-checks.json"
    output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Report: {output}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
