"""Independent v2 GLB/scene metric verification, using Python standard library.

Reuses the read-only v1 parser/matrix functions, but verifies current binary
vertices, hierarchy and v2 contracts independently. No Blender or network.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import verify_visual_assets as base

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "frontend/public/models/v2"
VERSION = "qoima-72x48-v2"
REQUIRED = {
    "environment-shell", "rack-high", "rack-low", "dock",
    "standing-worker", "worker-low", "driver", "picking-cart",
    "conveyor-high", "conveyor-low", "conveyor-corner", "conveyor-diverter",
    "order-tote", "tote-low", "sealed-parcel",
    "forklift", "packing-station", "buffer-pallet", "pallet", "crate", "calibration-v2",
}
require, close = base.require, base.close


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class Geometry:
    def __init__(self, path):
        self.path = path
        self.doc, binary, self.bytes = base.parse_glb(path)
        self.nodes = self.doc.get("nodes", [])
        self.meshes = self.doc.get("meshes", [])
        self.materials = self.doc.get("materials", [])
        self.decoded = {}
        accessors = self.doc.get("accessors", [])
        views = self.doc.get("bufferViews", [])
        for index, accessor in enumerate(accessors):
            require("sparse" not in accessor, "Sparse accessor unsupported by project verifier")
            require("bufferView" in accessor, "Accessor is not embedded")
            kind = accessor["componentType"]
            require(kind in base.COMPONENTS, "Unknown accessor component type")
            require(accessor["type"] in base.WIDTHS, "Unknown accessor shape")
            component, size = base.COMPONENTS[kind]
            width = base.WIDTHS[accessor["type"]]
            count = accessor["count"]
            require(isinstance(count, int) and count >= 0, "Invalid accessor count")
            require(0 <= accessor["bufferView"] < len(views), "Invalid bufferView index")
            view = views[accessor["bufferView"]]
            stride = view.get("byteStride", width * size)
            relative = accessor.get("byteOffset", 0)
            require(relative >= 0 and stride >= width * size and stride % size == 0,
                    "Invalid accessor offset or stride")
            used = relative + (count - 1) * stride + width * size if count else relative
            require(used <= view["byteLength"], "Accessor exceeds embedded bufferView")
            offset = view.get("byteOffset", 0) + relative
            unpack = struct.Struct("<" + component * width).unpack_from
            rows = [unpack(binary, offset + row * stride) for row in range(count)]
            require(all(math.isfinite(value) for row in rows for value in row), "Nonfinite binary accessor")
            self.decoded[index] = rows
            for key in ("min", "max"):
                if key in accessor and rows:
                    require(len(accessor[key]) == width, "Accessor bounds shape mismatch")
                    for axis in range(width):
                        measured = (min if key == "min" else max)(row[axis] for row in rows)
                        close(measured, accessor[key][axis], "Binary accessor bound", 1e-4)
        self.primitives = {}
        for mesh_id, mesh in enumerate(self.meshes):
            values = []
            for primitive in mesh["primitives"]:
                require(primitive.get("mode", 4) == 4, "Non-triangle primitive")
                position_id = primitive["attributes"]["POSITION"]
                accessor = accessors[position_id]
                require(accessor["type"] == "VEC3" and accessor["componentType"] == 5126,
                        "POSITION is not float VEC3")
                positions = self.decoded[position_id]
                require(positions, "Empty POSITION buffer")
                if "indices" in primitive:
                    index_id = primitive["indices"]
                    require(accessors[index_id]["type"] == "SCALAR" and
                            accessors[index_id]["componentType"] in (5121, 5123, 5125), "Invalid index type")
                    indices = [row[0] for row in self.decoded[index_id]]
                else:
                    indices = list(range(len(positions)))
                require(len(indices) % 3 == 0, "Index count is not triangular")
                require(all(isinstance(i, int) and 0 <= i < len(positions) for i in indices),
                        "Index outside actual POSITION rows")
                mat_id = primitive.get("material")
                material = self.materials[mat_id].get("name", "") if mat_id is not None else ""
                values.append((positions, indices, material))
            self.primitives[mesh_id] = values
        require(self.nodes and self.meshes, "No nodes or meshes")
        scene = self.doc["scenes"][self.doc.get("scene", 0)]
        self.roots = scene.get("nodes", [])
        require(self.roots, "No selected scene roots")
        self.worlds, self.parents, self.node_points = {}, {}, {}
        self.material_points = defaultdict(list)
        self.triangles = 0
        self.draw_primitives = 0
        self.mesh_nodes = 0
        self.all_points = []

        def visit(index, parent, ancestors, parent_index=None):
            require(isinstance(index, int) and 0 <= index < len(self.nodes), "Invalid node index")
            require(index not in ancestors and index not in self.worlds, "Cycle or multiply-parented node")
            node = self.nodes[index]
            world = base.multiply(parent, base.node_matrix(node))
            self.worlds[index] = world
            self.parents[index] = parent_index
            points = []
            if "mesh" in node:
                require(0 <= node["mesh"] < len(self.meshes), "Invalid mesh reference")
                self.mesh_nodes += 1
                for positions, indices, material in self.primitives[node["mesh"]]:
                    transformed = [base.transform(world, row) for row in positions]
                    require(all(math.isfinite(v) for row in transformed for v in row), "Nonfinite world vertex")
                    points.extend(transformed)
                    self.material_points[material].extend(transformed)
                    self.triangles += len(indices) // 3
                    self.draw_primitives += 1
            self.node_points[index] = points
            self.all_points.extend(points)
            for child in node.get("children", []):
                visit(child, world, ancestors | {index}, index)

        self.root_extras = []
        for index in self.roots:
            matrix = base.node_matrix(self.nodes[index])
            close(base.determinant3(matrix), 1, "Scene root determinant", 1e-4)
            for axis in range(3):
                close(math.sqrt(sum(matrix[row][axis] ** 2 for row in range(3))),
                      1, "Scene root unit scale", 1e-4)
                close(matrix[axis][3], 0, "Scene root origin", 1e-4)
            extras = self.nodes[index].get("extras", {})
            require(extras.get("layout_version") == VERSION, "Scene root namespace is not v2")
            self.root_extras.append(extras)
            visit(index, base.IDENTITY, set())
        require(self.all_points and self.triangles > 0, "No visible geometry")
        self.minimum = [min(row[axis] for row in self.all_points) for axis in range(3)]
        self.maximum = [max(row[axis] for row in self.all_points) for axis in range(3)]
        self.size = [self.maximum[axis] - self.minimum[axis] for axis in range(3)]

    def extras(self, index):
        return self.nodes[index].get("extras", {})

    def position(self, index):
        return [self.worlds[index][axis][3] for axis in range(3)]

    def descendants(self, index):
        result, pending = [], [index]
        while pending:
            current = pending.pop()
            result.append(current)
            pending.extend(self.nodes[current].get("children", []))
        return result

    def visible(self, index):
        return any(self.node_points.get(child) for child in self.descendants(index))

    def bounds(self, index):
        points = [p for child in self.descendants(index) for p in self.node_points.get(child, [])]
        require(points, "Entity has no actual visible mesh geometry")
        return ([min(p[a] for p in points) for a in range(3)],
                [max(p[a] for p in points) for a in range(3)])

    def centre_ray_top(self, x=0., z=0.):
        hits = []
        for index, world in self.worlds.items():
            node = self.nodes[index]
            if "mesh" not in node:
                continue
            for positions, indices, _ in self.primitives[node["mesh"]]:
                points = [base.transform(world, point) for point in positions]
                for offset in range(0, len(indices), 3):
                    a, b, c = [points[i] for i in indices[offset:offset + 3]]
                    denominator = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
                    if abs(denominator) < 1e-12:
                        continue
                    u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / denominator
                    v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / denominator
                    w = 1 - u - v
                    if min(u, v, w) >= -1e-7:
                        hits.append(u * a[1] + v * b[1] + w * c[1])
        require(hits, "No geometry under centre ray")
        return max(hits)

    def footprint_support_top(self, x, z, half_x=.24, half_z=.18):
        # A rigid tote rests on rollers across its footprint, not necessarily on
        # a surface directly below its centre. Clip real triangles to that area.
        if not hasattr(self, "support_triangles"):
            self.support_triangles = []
            for index, world in self.worlds.items():
                node = self.nodes[index]
                if "mesh" not in node:
                    continue
                for positions, indices, _ in self.primitives[node["mesh"]]:
                    points = [base.transform(world, point) for point in positions]
                    self.support_triangles.extend([points[i] for i in indices[offset:offset + 3]]
                                                  for offset in range(0, len(indices), 3))
        highest = -math.inf
        for triangle in self.support_triangles:
            if (max(p[0] for p in triangle) < x - half_x or min(p[0] for p in triangle) > x + half_x or
                    max(p[2] for p in triangle) < z - half_z or min(p[2] for p in triangle) > z + half_z):
                continue
            polygon = triangle
            for axis, boundary, sign in ((0, x - half_x, 1), (0, x + half_x, -1),
                                          (2, z - half_z, 1), (2, z + half_z, -1)):
                clipped = []
                for left, right in zip(polygon, polygon[1:] + polygon[:1]):
                    inside_left = (left[axis] - boundary) * sign >= -1e-7
                    inside_right = (right[axis] - boundary) * sign >= -1e-7
                    if inside_left:
                        clipped.append(left)
                    if inside_left != inside_right:
                        fraction = (boundary - left[axis]) / (right[axis] - left[axis])
                        clipped.append(tuple(left[a] + (right[a] - left[a]) * fraction for a in range(3)))
                polygon = clipped
                if not polygon:
                    break
            if polygon:
                highest = max(highest, max(p[1] for p in polygon))
        require(math.isfinite(highest), "No actual support geometry under cargo footprint")
        return highest


def dimensions(actual, expected, label, tolerance=1e-4):
    for axis in range(3):
        close(actual[axis], expected[axis], label + " axis " + str(axis), tolerance)


def semantic_checks(asset_id, geo):
    checks, measurements = [], {}
    metadata = next((e for e in geo.root_extras if e.get("asset_id") == asset_id), None)
    require(metadata is not None, "Root asset_id does not match filename")
    if asset_id in ("rack-high", "rack-low"):
        dimensions(geo.size, (.9, 5.4, 1.5), "Rack")
        close(geo.minimum[1], 0, "Rack floor")
        anchors = {geo.extras(i).get("level"): geo.position(i) for i in geo.worlds
                   if geo.extras(i).get("role") in ("pickface_anchor", "reserve_anchor")}
        require(set(anchors) == {1, 2, 3}, "Rack needs three actual bin anchor nodes")
        for level, height in enumerate((.45, 2.25, 4.05), 1):
            dimensions(anchors[level], (0, height, 0), "Rack bin anchor")
        birch = [p for name, points in geo.material_points.items() if "birch" in name.lower() for p in points]
        require(birch, "Rack has no real birch deck geometry")
        for top in (.225, 2.025, 3.825):
            edge = [p for p in birch if abs(p[1] - top) < 1e-4]
            require(edge and max(p[0] for p in edge) - min(p[0] for p in edge) > .75
                    and max(p[2] for p in edge) - min(p[2] for p in edge) > 1.30,
                    "Missing actual deck top at Y=" + str(top))
        if asset_id == "rack-low":
            require(geo.triangles <= 300 and len(geo.materials) <= 2, "Far rack exceeds budget")
        checks += ["rack_exact_dimensions", "three_binary_geometry_deck_tops", "three_bin_anchor_world_positions"]
        measurements["bin_anchors"] = anchors
    elif asset_id in ("standing-worker", "worker-low", "picker-worker"):
        close(geo.minimum[1], 0, "Worker ground contact", .002)
        close(geo.size[1], 1.7, "Worker height", .02)
        require(geo.size[0] < .85 and geo.size[2] < .85, "Worker silhouette exceeds aisle space")
        checks += ["worker_1_7m_height", "worker_ground_contact"]
    elif asset_id == "driver":
        require(geo.minimum[1] < -.3, "Seated driver should extend below local seat plane")
        require(metadata.get("origin_description") == "seat contact plane", "Driver seat origin missing")
        dimensions(metadata["vehicle_seat_anchor_runtime"], (0, .99, -.65), "Driver seat binding")
        require(.7 < geo.maximum[1] < 1.05, "Driver seated upper-body height is implausible")
        checks += ["negative_local_y_intentional_for_seated_driver", "driver_seat_binding"]
    elif asset_id in ("order-tote", "tote-low", "sealed-parcel"):
        expected = (.5, .32, .38) if asset_id == "sealed-parcel" else (.52, .3, .42)
        dimensions(geo.size, expected, "Cargo dimensions", .015)
        close(geo.minimum[1], 0, "Cargo support surface", .002)
        centre_top = geo.centre_ray_top()
        measurements["centre_vertical_ray_top_y"] = centre_top
        if asset_id == "sealed-parcel":
            close(centre_top, geo.maximum[1], "Parcel closed centre top", .012)
            require(metadata.get("sealed") is True, "Parcel sealed metadata missing")
            checks.append("parcel_closed_top_from_actual_triangles")
        else:
            require(centre_top < geo.maximum[1] - .12, "Tote is capped or has no interior depth")
            require(metadata.get("hollow") is True, "Open tote metadata missing")
            checks.append("tote_open_interior_from_actual_triangles")
    elif asset_id.startswith("conveyor-"):
        close(metadata["belt_surface_y"], .9, "Conveyor belt contract")
        close(metadata["cell_length_m"], 1, "Conveyor metre unit")
        belt = [p for name, points in geo.material_points.items() if "belt" in name.lower() for p in points]
        require(belt, "No actual belt material geometry")
        close(max(p[1] for p in belt), .9, "Actual belt surface top", .005)
        ports = {geo.extras(i).get("port_name"): geo.position(i) for i in geo.worlds
                 if geo.extras(i).get("role") == "conveyor_port"}
        expected = {"input": (0, .9, -.5), "output": (0, .9, .5)}
        if asset_id == "conveyor-corner":
            expected["output"] = (.5, .9, 0)
        if asset_id == "conveyor-diverter":
            expected["branch"] = (.5, .9, 0)
        require(set(ports) == set(expected), "Wrong conveyor port nodes")
        for name, point in expected.items():
            dimensions(ports[name], point, "Conveyor world port " + name)
        checks += ["actual_belt_top_0_9m", "conveyor_1m_unit", "conveyor_port_world_positions"]
        measurements["ports"] = ports
    elif asset_id == "environment-shell":
        close(geo.minimum[0], 0, "Shell X minimum")
        close(geo.maximum[0], 72, "Shell X maximum")
        close(geo.minimum[2], 0, "Shell Z minimum")
        close(geo.maximum[2], 48, "Shell Z maximum")
        close(geo.maximum[1], 8, "Shell upper structure")
        floor = [p for name, points in geo.material_points.items() if "warm concrete" in name.lower() for p in points]
        require(floor, "No concrete slab geometry")
        close(max(p[1] for p in floor), 0, "Actual slab top")
        checks += ["shell_72x48_footprint", "shell_8m_structure", "actual_floor_top_zero"]
    elif asset_id == "crate":
        dimensions(geo.size, (.55, .45, .65), "Storage crate", .015)
        dimensions([(geo.minimum[a] + geo.maximum[a]) / 2 for a in range(3)],
                   (0, 0, 0), "Storage crate centred origin", .002)
        checks.append("storage_crate_metric_dimensions")
    elif asset_id in ("pallet", "buffer-pallet"):
        close(geo.minimum[1], 0, "Pallet floor contact", .002)
        height = .14 if asset_id == "pallet" else .075
        close(geo.maximum[1], height, "Pallet cargo support top", .005)
        anchors = {geo.nodes[i].get("name"): geo.position(i) for i in geo.worlds
                   if geo.extras(i).get("role") == "attachment"}
        require("anchor_cargo" in anchors, "Pallet cargo attachment absent")
        dimensions(anchors["anchor_cargo"], (0, height, 0), "Pallet actual cargo anchor", .005)
        require(sum("fork_entry" in str(name) for name in anchors) == 4,
                "Pallet lacks four real fork-entry attachment nodes")
        checks += ["pallet_ground_and_support_height", "pallet_four_actual_fork_entries"]
    elif asset_id == "forklift":
        close(geo.minimum[1], 0, "Forklift tyre contact", .005)
        anchors = {geo.nodes[i].get("name"): geo.position(i) for i in geo.worlds
                   if geo.extras(i).get("role") == "attachment"}
        dimensions(anchors["anchor_driver_seat"], (0, .99, -.65), "Actual driver seat", .005)
        require(any(geo.extras(i).get("role") == "functional_pivot" for i in geo.worlds),
                "Forklift articulated pivots absent")
        require(not any(geo.extras(i).get("asset_id") == "driver" for i in geo.worlds),
                "Forklift prototype bakes an extra driver body")
        checks += ["forklift_actual_seat_anchor", "forklift_functional_pivots", "no_baked_extra_driver"]
    elif asset_id == "packing-station":
        close(geo.minimum[1], 0, "Packing station floor", .005)
        anchors = {geo.nodes[i].get("name"): geo.position(i) for i in geo.worlds
                   if geo.extras(i).get("role") == "attachment"}
        for name in ("anchor_input_tote", "anchor_output_parcel", "anchor_work_parcel"):
            require(name in anchors, "Packing cargo attachment missing: " + name)
            close(anchors[name][1], .85, "Packing cargo support plane", .005)
        checks.append("packing_actual_cargo_anchors_0_85m")
        transfers = {geo.nodes[i].get("name"): geo.position(i) for i in geo.worlds
                     if geo.extras(i).get("role") == "passive_transfer_surface"}
        paths = [
            [("input_branch", (0, .9, 1.5)), ("input_cross", (0, .9, 1.25)),
             ("input_turn", (-.72, .9, 1.25)), ("input_table", (-.72, .85, .5))],
            [("output_table", (.72, .85, -.5)), ("output_turn", (.72, .9, -1.2)),
             ("output_cross", (0, .9, -1.2)), ("output_outfeed", (0, .9, -1.5))],
        ]
        gaps = []
        for path in paths:
            for name, point in path:
                require("anchor_transfer_" + name in transfers, "Passive transfer anchor missing")
                dimensions(transfers["anchor_transfer_" + name], point, "Passive transfer world anchor", .005)
            for (_, start), (_, end) in zip(path, path[1:]):
                for sample in range(9):
                    point = [start[a] + (end[a] - start[a]) * sample / 8 for a in range(3)]
                    support = geo.footprint_support_top(point[0], point[2])
                    gap = abs(support - point[1]); gaps.append(gap)
                    require(gap < .015, "Missing or obstructed actual packing transfer support at " + str(point))
        measurements["passive_transfer_centreline_samples"] = len(gaps)
        measurements["support_test_footprint_m"] = [.48, .36]
        measurements["maximum_passive_support_height_error_m"] = max(gaps)
        checks += ["eight_actual_passive_transfer_anchors", "54_binary_geometry_cargo_footprint_support_samples"]
    elif asset_id == "calibration-v2":
        axes = {geo.extras(i).get("axis"): geo.position(i) for i in geo.worlds
                if geo.extras(i).get("role") == "calibration_axis_endpoint"}
        for axis, point in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
            dimensions(axes[axis], point, "Calibration 1m axis endpoint")
            ruler = [i for i in geo.worlds if geo.nodes[i].get("name") == "Ruler_1m_" + axis]
            require(len(ruler) == 1, "Calibration ruler mesh absent")
            low, high = geo.bounds(ruler[0])
            index = {"X": 0, "Y": 1, "Z": 2}[axis]
            close(high[index] - low[index], 1, "Actual one-metre ruler geometry", .002)
        instances = {geo.extras(i).get("calibration_asset"): i for i in geo.worlds
                     if "calibration_asset" in geo.extras(i)}
        for name, position, height in (("standing-worker", (2, 0, 0), 1.7),
                                       ("rack-high", (4, 0, 0), 5.4)):
            dimensions(geo.position(instances[name]), position, "Calibration asset root")
            low, high = geo.bounds(instances[name])
            close(high[1] - low[1], height, "Calibration actual asset height", .02)
        dimensions(geo.position(instances["conveyor-high"]), (6, 0, 0), "Calibration conveyor root")
        anchors = {geo.nodes[i].get("name"): geo.position(i) for i in geo.worlds
                   if geo.extras(i).get("role") == "calibration_measurement_anchor"}
        for level, height in enumerate((.45, 2.25, 4.05), 1):
            dimensions(anchors["calibration_anchor__rack_bin_%02d" % level],
                       (4, height, 0), "Calibration rack bin")
        dimensions(anchors["calibration_anchor__belt_top"], (6, .9, 0), "Calibration belt top")
        checks += ["calibration_actual_1m_ruler_meshes", "calibration_worker_and_rack_metric_heights",
                   "calibration_three_bin_anchors_and_belt_top"]
    return checks, measurements


def check_master(geo):
    layout = json.loads((ROOT / "contracts/layout.example.json").read_text(encoding="utf-8"))
    actors = json.loads((ROOT / "contracts/actors.example.json").read_text(encoding="utf-8"))
    assignment = json.loads((ROOT / "contracts/assignment.example.json").read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for index in geo.worlds:
        groups[geo.extras(index).get("role")].append(index)
    definitions = [
        ("racks", "rack_module", "rack_id", {r["rack_id"]: r["root"] for r in layout["racks"]}),
        ("slots", "logical_storage_slot", "slot_id", {s["slot_id"]: s["bin_anchor"] for s in layout["slots"]}),
        ("occupied_slots", "initial_inventory_symbol", "lot_id", {l["lot_id"]: None for l in assignment["initial_lots"]}),
        ("vehicles", "forklift_vehicle", "vehicle_id", {v["vehicle_id"]: None for v in actors["vehicles"]}),
        ("pack_stations", "packing_station", "pack_id", {p["pack_id"]: p["worker_pos"] for p in layout["pack_stations"]}),
    ]
    actual = {}
    entity_maps = {}
    for label, role, key, expected in definitions:
        mapping = {geo.extras(i)[key]: i for i in groups[role] if key in geo.extras(i)}
        require(len(mapping) == len([i for i in groups[role] if key in geo.extras(i)]), "Duplicate master " + key)
        require(set(mapping) == set(expected), "Actual master IDs differ for " + label)
        for name, point in expected.items():
            index = mapping[name]
            if label != "slots":
                require(geo.visible(index), "Master entity is an empty stand-in: " + name)
            if point is not None:
                dimensions(geo.position(index), point, "Master entity position " + name, .02)
        actual[label] = len(mapping)
        entity_maps[label] = mapping
    slot_by_id = {s["slot_id"]: s for s in layout["slots"]}
    for lot in assignment["initial_lots"]:
        index = entity_maps["occupied_slots"][lot["lot_id"]]
        extras = geo.extras(index)
        require(all(extras.get(key) == lot[key] for key in ("sku_id", "slot_id", "quantity")), "Actual lot binding mismatch")
        point = slot_by_id[lot["slot_id"]]["bin_anchor"]
        dimensions(geo.position(index), point, "Actual lot world position", .02)
        low, high = geo.bounds(index)
        dimensions([high[a] - low[a] for a in range(3)], (.55, .45, .65), "Actual lot symbol size", .015)
    bin_anchors = {geo.extras(i).get("slot_id"): i for i in groups["bin_anchor"] if "slot_id" in geo.extras(i)}
    require(set(bin_anchors) == set(slot_by_id), "Actual master lacks 864 qualified bin anchors")
    for slot_id, index in bin_anchors.items():
        dimensions(geo.position(index), slot_by_id[slot_id]["bin_anchor"], "Master bin anchor", .02)
    actor_map = {geo.extras(i)["actor_id"]: i for i in geo.worlds if "actor_id" in geo.extras(i)}
    require(set(actor_map) == {a["actor_id"] for a in actors["actors"]}, "Actual master actor IDs differ")
    for actor in actors["actors"]:
        index = actor_map[actor["actor_id"]]
        extras = geo.extras(index)
        require(extras.get("role") == actor["role"] and geo.visible(index), "Actor role or actual geometry missing")
        dimensions(geo.position(index), actor["initial_pos"], "Actor business root", .02)
        require("render_offset" in extras, "Actor cosmetic offset not documented")
        if actor["role"] == "forklift_driver":
            vehicle_index = entity_maps["vehicles"][actor["vehicle_id"]]
            require(vehicle_index in [geo.parents.get(i) for i in geo.descendants(vehicle_index)] and
                    index in geo.descendants(vehicle_index), "Driver not attached to vehicle")
            sources = [i for i in geo.descendants(index) if geo.extras(i).get("asset_id") == "driver"]
            require(len(sources) == 1, "Driver seated body missing")
            expected = base.transform(geo.worlds[vehicle_index], (0, .99, -.65))
            dimensions(geo.position(sources[0]), expected, "Driver actual seated body", .02)
    actual["actors"] = len(actor_map)
    cell_ids = groups["conveyor_cell"]
    expected_cells = {}
    for segment in layout["conveyor"]["segments"]:
        start, end, count = segment["from"], segment["to"], segment["cell_count"]
        for cell in range(count):
            expected_cells[(segment["segment_id"], cell)] = (start, end, count)
    cells = {(geo.extras(i)["segment_id"], geo.extras(i)["cell_index"]): i for i in cell_ids}
    require(set(cells) == set(expected_cells) and len(cell_ids) == 179, "Actual 179-cell hierarchy mismatch")
    connection_points = [item["at"] for item in layout["conveyor"]["connections"]]
    logical_ports = {(geo.extras(i).get("cell_id"), geo.extras(i).get("port_name")): i
                     for i in groups["logical_conveyor_cell_port"]}
    require(len(logical_ports) == 358, "Master lacks two canonical logical ports per cell")
    for key, index in cells.items():
        start, end, count = expected_cells[key]
        require(geo.visible(index), "Conveyor cell has no actual geometry")
        logical_from = [start[a] + (end[a] - start[a]) * key[1] / count for a in range(3)]
        logical_to = [start[a] + (end[a] - start[a]) * (key[1] + 1) / count for a in range(3)]
        trim_start = .5 if any(math.dist(logical_from, p) < 1e-5 for p in connection_points) else 0
        trim_end = .5 if any(math.dist(logical_to, p) < 1e-5 for p in connection_points) else 0
        visible_length = 1 - trim_start - trim_end
        fraction = (key[1] + trim_start + visible_length / 2) / count
        expected = [start[a] + (end[a] - start[a]) * fraction for a in range(3)]
        dimensions(geo.position(index), (expected[0], 0, expected[2]), "Conveyor cell root", .02)
        close(geo.extras(index)["visual_length_m"], visible_length, "Trimmed cell visual length")
        ports = {geo.extras(i).get("port_name"): geo.position(i) for i in geo.descendants(index)
                 if geo.extras(i).get("role") == "conveyor_port"}
        for name, fraction in (("input", (key[1] + trim_start) / count),
                               ("output", (key[1] + 1 - trim_end) / count)):
            point = [start[a] + (end[a] - start[a]) * fraction for a in range(3)]
            require(name in ports, "Conveyor cell port missing")
            dimensions(ports[name], point, "Master actual trimmed visual conveyor port", .02)
        cell_id = "%s:%s" % key
        for name, point in (("from", logical_from), ("to", logical_to)):
            require((cell_id, name) in logical_ports, "Canonical logical cell port missing")
            dimensions(geo.position(logical_ports[(cell_id, name)]), point,
                       "Master canonical untrimmed logical cell port", .02)
    actual["conveyor_cells"] = len(cells)
    junctions = {geo.extras(i).get("junction_id"): i for i in groups["conveyor_junction"]}
    require(len(junctions) == 19, "Actual master does not contain nineteen visual junctions")
    for number, point in enumerate(connection_points, 1):
        index = junctions["JUNCTION_%02d" % number]
        require(geo.visible(index), "Visual junction has no mesh geometry")
        dimensions(geo.position(index), (point[0], 0, point[2]), "Junction canonical centre", .02)
        # Independent endpoint-distance test derives every outward arm from the
        # contract, rather than trusting the builder's selected yaw or arm extras.
        arms = set()
        for segment in layout["conveyor"]["segments"]:
            start, end = segment["from"], segment["to"]
            if abs(math.dist(start, point) + math.dist(point, end) - math.dist(start, end)) > 1e-5:
                continue
            for endpoint in (start, end):
                length = math.dist(point, endpoint)
                if length > 1e-5:
                    arms.add(tuple(round((endpoint[a] - point[a]) / length, 8) for a in range(3)))
        expected_ports = [[point[a] + .5 * arm[a] for a in range(3)] for arm in arms]
        ports = [geo.position(i) for i in geo.descendants(index)
                 if geo.extras(i).get("role") == "conveyor_port"]
        require(len(ports) == len(expected_ports) and
                all(any(math.dist(port, expected) < .02 for port in ports) for expected in expected_ports),
                "Junction actual open ports do not match canonical outward arms")
        expected_model = "conveyor-corner" if len(arms) == 2 else "conveyor-diverter"
        require(any(geo.extras(i).get("asset_id") == expected_model for i in geo.descendants(index)),
                "Junction lacks actual corner/diverter prototype")
    actual["conveyor_junctions"] = len(junctions)
    root = next(e for e in geo.root_extras if e.get("asset_id") == "large-warehouse")
    declared = json.loads(root["counts"]) if isinstance(root.get("counts"), str) else root.get("counts")
    require(declared == actual, "Master declared counts differ from independently traversed hierarchy")
    require(geo.triangles <= 350000, "Master exceeds 350k actual instance triangles")
    require(len(geo.meshes) < geo.mesh_nodes, "Master lost linked reusable geometry")
    return actual


def inspect(path):
    geo = Geometry(path)
    asset_id = path.stem
    require(geo.bytes < (20_000_000 if asset_id == "large-warehouse" else 5_000_000), "GLB file exceeds asset budget")
    checks = ["embedded_glb2_no_external_resources", "finite_json_binary_and_world_vertices",
              "valid_buffer_accessors_indices", "no_required_extensions", "v2_namespace",
              "unit_scene_root_at_origin", "world_bounds_from_actual_POSITION_vertices"]
    semantic, measurements = semantic_checks(asset_id, geo)
    checks += semantic
    if asset_id == "large-warehouse":
        measurements["actual_hierarchy_counts"] = check_master(geo)
        checks += ["master_actual_visible_entities_and_ids", "master_864_world_bin_anchors",
                   "master_600_actual_inventory_symbols", "master_24_bodies_2_seated_vehicle_drivers",
                   "master_179_trimmed_visual_cells_and_358_canonical_logical_ports",
                   "master_19_actual_junctions_with_matching_open_world_ports",
                   "master_under_350k_instance_triangles"]
    stats_path = ROOT / "assets/v2/blender" / (asset_id + ".stats.json")
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        require(stats["glb_bytes"] == geo.bytes and stats["triangles"] == geo.triangles, "Stats byte/triangle mismatch")
        bmin, bmax = stats["bounds_blender"]["min"], stats["bounds_blender"]["max"]
        dimensions(geo.minimum, (bmin[0], bmin[2], -bmax[1]), "Stats actual world minimum", 1e-4)
        dimensions(geo.maximum, (bmax[0], bmax[2], -bmin[1]), "Stats actual world maximum", 1e-4)
        checks.append("stats_match_actual_glb_geometry")
    return {
        "asset_id": asset_id, "status": "passed", "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha(path), "bytes": geo.bytes, "triangles": geo.triangles,
        "mesh_definitions": len(geo.meshes), "mesh_nodes": geo.mesh_nodes,
        "draw_primitives": geo.draw_primitives, "nodes": len(geo.worlds),
        "materials": len(geo.materials), "bounds_runtime": {"min": geo.minimum, "max": geo.maximum},
        "size_m": geo.size, "checks": checks, "measurements": measurements,
    }


def canonical_copy_validation():
    work = ROOT / "work/v2-spec-validation"
    (work / "tools").mkdir(parents=True, exist_ok=True)
    source = ROOT / "tools/validate_spec_v2.py"
    before = sha(ROOT / "verification_report.json")
    shutil.copy2(source, work / "tools/validate_spec_v2.py")
    shutil.copytree(ROOT / "contracts", work / "contracts", dirs_exist_ok=True)
    environment = os.environ.copy()
    dependencies = work / "python-deps"
    environment["PYTHONPATH"] = str(dependencies) + os.pathsep + environment.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, str(work / "tools/validate_spec_v2.py")],
                            cwd=work, env=environment, capture_output=True, text=True, timeout=120)
    require(sha(ROOT / "verification_report.json") == before, "Original verification report was modified")
    report = {"status": "passed" if result.returncode == 0 else "failed",
              "executed_copy": str(work / "tools/validate_spec_v2.py"), "exit_code": result.returncode,
              "stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
              "original_verification_report_sha256_unchanged": before,
              "source_validator_sha256": sha(source),
              "scope": "Canonical prepared contracts/schema/arithmetic only; independent of GLB/runtime QA."}
    copied_report = work / "verification_report.json"
    if result.returncode == 0 and copied_report.exists():
        report["canonical_report"] = json.loads(copied_report.read_text(encoding="utf-8"))
    output = ROOT / "assets/v2/canonical-spec-checks.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {key: value for key, value in report.items() if key != "canonical_report"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-incomplete", action="store_true", help="Report missing final assets as pending, never passed.")
    parser.add_argument("--run-spec-copy", action="store_true", help="Execute canonical validator only in work/ copied tree.")
    args = parser.parse_args()
    results = []
    existing = {path.stem: path for path in MODELS.glob("*.glb")}
    expected = REQUIRED | {"large-warehouse"}
    for asset_id in sorted(expected | set(existing)):
        if asset_id not in existing:
            results.append({"asset_id": asset_id, "status": "pending" if args.allow_incomplete else "failed",
                            "error": "Final export not present; not validated."})
            continue
        try:
            result = inspect(existing[asset_id])
        except (ValueError, KeyError, IndexError, TypeError, OSError, struct.error) as error:
            result = {"asset_id": asset_id, "status": "failed", "error": str(error)}
        results.append(result)
        print(asset_id + ": " + result["status"] + (" | " + result["error"] if "error" in result else
              " | " + str(result["triangles"]) + " triangles"))
    spec = canonical_copy_validation() if args.run_spec_copy else None
    failed = any(r["status"] == "failed" for r in results) or (spec is not None and spec["status"] == "failed")
    pending = any(r["status"] == "pending" for r in results)
    status = "failed" if failed else "partial" if pending else "passed"
    output = ROOT / "assets/v2/visual-checks.json"
    report = {"schema_version": "2.0", "layout_version": VERSION,
              "generated_at": datetime.now(timezone.utc).isoformat(), "status": status,
              "method": "GLB JSON/BIN decode; actual POSITION vertices, indices and world hierarchy; no Blender.",
              "master_checked": any(r["asset_id"] == "large-warehouse" and r["status"] == "passed" for r in results),
              "assets": results, "canonical_copy_validation": spec,
              "limitations": ["Project-specific independent checks; Khronos validator is separate.",
                              "Geometry checks do not establish visual, animation or runtime performance acceptance.",
                              "No master pass is claimed while its final file is missing.",
                              "Rejects sparse accessors and non-triangle primitives."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("V2 report: " + status + " | " + str(output))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
