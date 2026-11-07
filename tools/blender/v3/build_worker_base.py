"""P01 staged worker source, with explicit accepted-source export entry point.

Run through v3/run_build.py in fresh --factory-startup background Blender.
The accepted dimension plan supplies all primary frames and named joints.
Stage saves remain source-only. --export opens the accepted neutral source,
saves its editable components through finish, then batches only within joints.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import sys

import bpy
from mathutils import Matrix, Vector

from v3_common import ROOT, reset, group, pivot, anchor, box, material, xyz, runtime_xyz, finish

SPEC = ROOT / "assets/v3/specs/worker-base.dimensions.json"
SOURCE = ROOT / "assets/v3/blender/worker-base.blend"
MAPPING = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def _tag(obj, part_id):
    obj["part_id"] = part_id
    obj["stage"] = "P01.2"
    return obj


def _part_box(name, part, joints, spec, mats):
    parent = joints[part["parent"]]
    parent_world = Vector(spec["joints"][part["parent"]]["bind_world_runtime"])
    obj = box(name, Vector(part["centre_runtime"]) - parent_world,
              part["full_size_local_xyz_m"], mats[part["material_slot"]], parent,
              bevel=part["bevel_m"])
    # Mesh orientation may change; all named pivot bind frames remain identity.
    basis = part["basis_xyz_runtime"]
    runtime_rotation = Matrix([[basis[column][row] for column in range(3)] for row in range(3)])
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = (MAPPING @ runtime_rotation @ MAPPING.transposed()).to_quaternion()
    return _tag(obj, name)


def _local_box(name, centre, size, mat, parent, bind_world, bevel=.003, part_id=None):
    obj = box(name, Vector(centre) - Vector(bind_world), size, mat, parent, bevel=bevel)
    return _tag(obj, part_id or name)


def _panel(name, polygon, inner_z, outer_z, mat, parent, bind_world):
    """Solid garment panel, with real closed8mm edges and an outside envelope."""
    count = len(polygon)
    vertices = [(x, y, z) for z in (outer_z, inner_z) for x, y in polygon]
    faces = [tuple(range(count)), tuple(reversed(range(count, count * 2)))]
    faces += [(i, i + count, (i + 1) % count + count, (i + 1) % count) for i in range(count)]
    if outer_z < inner_z:
        faces = [tuple(reversed(face)) for face in faces]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([xyz(Vector(point) - Vector(bind_world)) for point in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("Small flat garment edge", "BEVEL")
    bevel.width = .0015
    bevel.segments = 1
    bevel.harden_normals = True
    normal = obj.modifiers.new("Weighted garment faces", "WEIGHTED_NORMAL")
    normal.keep_sharp = True
    return _tag(obj, "vest_envelope")


def _vest(parent, bind, mats):
    # Blue volume wraps front/back/sides; V-neck reveals the actual dark shirt.
    left = [(-.21, .645), (-.008, .645), (-.008, .995),
            (-.075, 1.115), (-.185, 1.135), (-.21, 1.105)]
    right = [(-x, y) for x, y in reversed(left)]
    _panel("vest_front_L", left, .122, .13, mats["role_vest"], parent, bind)
    _panel("vest_front_R", right, .122, .13, mats["role_vest"], parent, bind)
    back = [(-.21, .645), (.21, .645), (.21, 1.105), (.18, 1.13),
            (.075, 1.13), (.065, 1.11), (-.065, 1.11), (-.075, 1.13),
            (-.18, 1.13), (-.21, 1.105)]
    _panel("vest_back", back, -.132, -.14, mats["role_vest"], parent, bind)
    for sign in (-1, 1):
        _local_box("vest_side", (sign * .206, .875, -.005), (.008, .46, .262),
                   mats["role_vest"], parent, bind, .0015, "vest_envelope")
        _local_box("vest_front_reflective", (sign * .109, .77, .131), (.19, .034, .004),
                   mats["reflective"], parent, bind, .0007, "vest_envelope")
        _local_box("vest_side_reflective", (sign * .211, .77, -.005), (.004, .034, .27),
                   mats["reflective"], parent, bind, .0007, "vest_envelope")
    _local_box("vest_back_reflective", (0, .77, -.141), (.42, .034, .004),
               mats["reflective"], parent, bind, .0007, "vest_envelope")


def _mitten(name, parent, bind, mat):
    sign = -1 if name.endswith("_L") else 1
    # C-shaped solid mitten. The45mm front-open channel surrounds the declared
    # grip anchor and clears a40mm bar, while all pads overlap the rear spine.
    _local_box(name + "_spine", (sign * .315, .66, .02375), (.094, .15, .0575),
               mat, parent, bind, .004, name)
    _local_box(name + "_upper_pad", (sign * .315, .71125, .06475), (.094, .0475, .0405),
               mat, parent, bind, .004, name)
    _local_box(name + "_lower_pad", (sign * .315, .61375, .06475), (.094, .0575, .0405),
               mat, parent, bind, .004, name)
    _local_box(name + "_thumb", (sign * .268, .709, .05), (.03, .04, .09),
               mat, parent, bind, .004, name)


def _head_details(parent, bind, mats):
    # Marks have real depth and embed into the planar head by1-2mm.
    for sign, side in ((-1, "L"), (1, "R")):
        _local_box("face_eye_" + side, (sign * .063, 1.355, .152), (.025, .043, .007),
                   mats["badge_ink"], parent, bind, .0008, "face_mark")
        _local_box("face_brow_" + side, (sign * .063, 1.411, .152), (.058, .014, .007),
                   mats["hair"], parent, bind, .001, "face_mark")
        _local_box("ear_" + side, (sign * .174, 1.331, -.005), (.049, .085, .075),
                   mats["skin"], parent, bind, .006, "ear")
        _local_box("hair_temple_" + side, (sign * .165, 1.414, -.059), (.014, .095, .168),
                   mats["hair"], parent, bind, .002, "hair_mass")
    # One closed U-shaped planar band rather than detached corner pieces.
    smile = [(-.047, 1.280), (-.037, 1.267), (-.022, 1.259), (0, 1.256),
             (.022, 1.259), (.037, 1.267), (.047, 1.280), (.038, 1.284),
             (.030, 1.275), (.017, 1.268), (0, 1.266), (-.017, 1.268),
             (-.030, 1.275), (-.038, 1.284)]
    _tag(_panel("face_smile", smile, .1485, .1555, mats["badge_ink"], parent, bind), "face_mark")
    _local_box("hair_back", (0, 1.377, -.1415), (.326, .19, .014),
               mats["hair"], parent, bind, .002, "hair_mass")


def _badge(parent, bind, mats):
    # The preliminary plan's badge back atZ.134 would float4mm above the vest.
    # BackZ.128 now embeds2mm into the garment; faceZ.140 supports all ink.
    base = _local_box("role_badge_base", (-.105, 1.015, .134), (.09, .11, .012),
                      mats["badge_base"], parent, bind, .004, "role_badge")
    base["role_code"] = "01"
    base["role_badge"] = "picker_cart"
    # Convex ink solids avoid an unstable concave-ngon face across the basket.
    cart = [(-.012, -.006), (.020, -.006), (.026, .012), (-.015, .012)]
    polygon = [(x - .105, y + 1.035) for x, y in cart]
    _tag(_panel("role_badge_cart", polygon, .1385, .1445,
                mats["badge_ink"], parent, bind), "role_badge_ink")
    handle = [(-.021, .022), (-.014, -.004), (-.009, -.004), (-.016, .022)]
    _tag(_panel("role_badge_cart_handle", [(x - .105, y + 1.035) for x, y in handle],
                .1385, .1440, mats["badge_ink"], parent, bind), "role_badge_ink")
    _local_box("role_badge_cart_grip", (-.127, 1.0565, .142), (.014, .005, .006),
               mats["badge_ink"], parent, bind, .0006, "role_badge_ink")
    for side, x in (("L", -.111), ("R", -.087)):
        wheel = [(x + .004 * math.cos(i * math.tau / 8),
                  1.020 + .004 * math.sin(i * math.tau / 8)) for i in range(8)]
        _tag(_panel("role_badge_cart_wheel_" + side, wheel, .1385, .1445,
                    mats["badge_ink"], parent, bind), "role_badge_ink")
    # Built-in Bfont -> editable mesh, no external font dependency or texture.
    curve = bpy.data.curves.new("Role01_text", "FONT")
    curve.body = "01"
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = .041
    curve.extrude = .0015
    curve.resolution_u = 4
    obj = bpy.data.objects.new("role_badge_code_01", curve)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.location = xyz(Vector((-.105, .989, .1405)) - Vector(bind))
    obj.rotation_euler = (math.pi / 2, 0, 0)
    obj.data.materials.append(mats["badge_ink"])
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    _tag(bpy.context.object, "role_badge_ink")


def build():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    root = group(spec["root_name"])
    root["asset_id"] = "worker-base"
    root["reference_id"] = "R05"
    root["dimensions_file"] = "assets/v3/specs/worker-base.dimensions.json"
    root["dimensions_sha256"] = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    root["preserve_articulation"] = True
    root["role"] = "base_worker"
    root["stage"] = "P01.2_source_silhouette"
    root["role_tint_materials"] = "V3_Worker_RoleVest;V3_Worker_RoleHeadwear"
    mats = {slot: material(data["name"], data["base_color"], data["roughness"], data["metallic"])
            for slot, data in spec["material_slots"].items()}
    objects = {root.name: root}
    pending = dict(spec["joints"])
    while pending:
        ready = [(name, data) for name, data in pending.items() if data["parent"] in objects]
        if not ready:
            raise ValueError("Unknown parent/cycle in accepted worker joint plan")
        for name, data in ready:
            obj = pivot(name, data["bind_local_runtime"], objects[data["parent"]], axis="X")
            obj["joint_name"] = name.removeprefix("joint__")
            obj["bind_world_runtime"] = data["bind_world_runtime"]
            obj["limits_xyz_json"] = json.dumps(data["limits_radians_xyz"])
            objects[name] = obj
            del pending[name]
    for name, part in spec["parts"].items():
        if name == "vest_envelope":
            bind = spec["joints"][part["parent"]]["bind_world_runtime"]
            _vest(objects[part["parent"]], bind, mats)
        elif name.startswith("mitten_"):
            bind = spec["joints"][part["parent"]]["bind_world_runtime"]
            _mitten(name, objects[part["parent"]], bind, mats["skin"])
        else:
            _part_box(name, part, objects, spec, mats)
    for name, data in spec["anchors"].items():
        anchor(name, data["local_runtime"], objects[data["parent"]])
    head = objects["joint__head"]
    bind = spec["joints"]["joint__head"]["bind_world_runtime"]
    _head_details(head, bind, mats)
    torso_bind = spec["joints"]["joint__torso"]["bind_world_runtime"]
    _badge(objects["joint__torso"], torso_bind, mats)
    from correct_worker_palms import inward_palms
    inward_palms(root)
    return root


def export_accepted_source():
    """No rebuild: export exactly the source reviewed in P01.5."""
    accepted_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    root = bpy.data.objects["worker_base_root"]
    if any(obj.name.startswith("QA_ONLY") for obj in root.children_recursive):
        raise ValueError("QA gauges cannot enter the production export")
    source_meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    editable_modifier_count = sum(len(obj.modifiers) for obj in source_meshes)
    assert len(source_meshes) == 56 and editable_modifier_count > 0
    assert root.get("preserve_articulation")
    from correct_worker_palms import inward_palms
    inward_palms(root)
    report = finish("worker-base", root, batch_runtime=True)
    report["accepted_source_before_export_sha256"] = accepted_hash
    report["accepted_source_snapshot"] = "assets/v3/iterations/worker-base/P01.4/iteration-02.blend"
    report["editable_source_modifiers_before_finish"] = editable_modifier_count
    report["source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    report["export_entry_point"] = "build_worker_base --export (existing accepted source, no rebuild)"
    (SOURCE.parent / "worker-base.stats.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("V3_WORKER_EXPORTED " + json.dumps({"sha256": report["sha256"],
          "runtime_meshes": report["runtime_meshes"], "triangles": report["triangles"]}))
    return report


def save_stage(stage="P01.2", iteration="01"):
    if not re.fullmatch(r"P01\.[1-7]", stage) or not re.fullmatch(r"[0-9]{2}", iteration):
        raise ValueError("Invalid stage/iteration")
    reset()
    root = build()
    root["stage"] = stage
    for obj in root.children_recursive:
        if obj.get("stage"):
            obj["stage"] = stage
    bpy.context.view_layer.update()
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    directory = ROOT / "assets/v3/iterations/worker-base" / stage
    directory.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    shutil.copy2(SOURCE, directory / ("iteration-" + iteration + ".blend"))
    graph = bpy.context.evaluated_depsgraph_get()
    points, triangles = [], 0
    for obj in root.children_recursive:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        points.extend(runtime_xyz(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices)
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    anchors = {obj.name: runtime_xyz(obj.matrix_world.translation)
               for obj in root.children_recursive if obj.get("anchor_id")}
    joints = {obj.name: {"parent": obj.parent.name, "position": runtime_xyz(obj.matrix_world.translation)}
              for obj in root.children_recursive if obj.get("pivot_id")}
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert abs(low[1]) < .00001 and abs(high[1] - 1.7) < .002
    assert high[0] - low[0] <= .76 and high[2] - low[2] <= .38001
    assert len(joints) == 17 and len(anchors) == 7
    for name, data in spec["anchors"].items():
        if name.startswith('anchor_hand_grip_'): continue  # FIX01.1 neutral axial roll
        assert max(abs(a-b) for a, b in zip(anchors[name], data["position_runtime"])) < .00001
    report = {"asset_id": "worker-base", "stage": stage, "iteration": iteration,
              "source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
              "bounds_runtime": {"min": low, "max": high},
              "dimensions_m": [high[i] - low[i] for i in range(3)], "evaluated_triangles": triangles,
              "mesh_parts": sum(obj.type == "MESH" for obj in root.children_recursive),
              "joints": joints, "anchors": anchors, "glb_exported": False,
              "scope": "Editable staged worker source; no GLB export; accepted pose/detail scope is recorded per stage evidence"}
    (directory / ("iteration-" + iteration + ".numeric.json")).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("V3_WORKER_STAGE " + json.dumps(report))
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="P01.2")
    parser.add_argument("--iteration", default="01")
    parser.add_argument("--export", action="store_true")
    arguments = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if arguments.export:
        export_accepted_source()
    else:
        save_stage(arguments.stage, arguments.iteration)
