"""v2 personnel: coherent cloth/anatomy, near/far LODs, seated vehicle driver.

All authored positions are runtime metres / Y-up / front +Z. The driver origin
is the seat contact plane, mounted at (0, .99, -.64) in the existing forklift.
No v1 builder or asset is modified. The separate cart contains no person.
"""
import json
import math

import bpy
from mathutils import Vector

from v2_common import reset, material, group, box, cylinder, beam, ico, finish, xyz


def _mesh(name, vertices, faces, mat, joint):
    pivot = Vector(joint.get("bind_pivot_runtime", [0, 0, 0]))
    data = bpy.data.meshes.new(name + "_mesh")
    data.from_pydata([tuple(xyz(Vector(v) - pivot)) for v in vertices], [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.parent = joint
    obj["part"] = joint.get("joint_name", "prop")
    return obj


def _loft(name, rings, mat, joint, sides=12, top_heights=None, cap=True):
    """Rings are (height, half-width, half-depth, centre-Z, centre-X)."""
    vertices = []
    for row, (height, width, depth, z, x) in enumerate(rings):
        for i in range(sides):
            angle = math.tau * i / sides
            y = top_heights[i] if top_heights is not None and row == len(rings) - 1 else height
            vertices.append((x + width * math.cos(angle), y, z + depth * math.sin(angle)))
    faces = [tuple(range(sides))] if cap else []
    for row in range(len(rings) - 1):
        for i in range(sides):
            a, b = row * sides + i, row * sides + (i + 1) % sides
            faces.append((a + sides, b + sides, b, a))
    if cap:
        faces.append(tuple((len(rings) - 1) * sides + i for i in reversed(range(sides))))
    return _mesh(name, vertices, faces, mat, joint)


def _sweep(name, rings, mat, joint, sides=8, depth_ratio=.88):
    """Smoothly tapered bent volume; each ring is (centre-point, full-width)."""
    vertices = []
    for row, (point, width) in enumerate(rings):
        previous = Vector(rings[max(0, row - 1)][0])
        following = Vector(rings[min(len(rings) - 1, row + 1)][0])
        axis = (following - previous).normalized()
        side = Vector((1, 0, 0))
        if abs(side.dot(axis)) > .94:
            side = Vector((0, 0, 1))
        side = (side - axis * side.dot(axis)).normalized()
        depth = axis.cross(side).normalized()
        for i in range(sides):
            angle = math.tau * i / sides
            offset = side * (math.cos(angle) * width / 2)
            offset += depth * (math.sin(angle) * width * depth_ratio / 2)
            vertices.append(tuple(Vector(point) + offset))
    faces = [tuple(reversed(range(sides)))]
    for row in range(len(rings) - 1):
        for i in range(sides):
            a, b = row * sides + i, row * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple((len(rings) - 1) * sides + i for i in range(sides)))
    return _mesh(name, vertices, faces, mat, joint)


def _joint(name, pivot, parent, parent_pivot=(0, 0, 0)):
    obj = group("joint__" + name)
    obj.parent = parent
    obj.location = xyz(Vector(pivot) - Vector(parent_pivot))
    obj["joint_name"] = name
    obj["bind_pivot_runtime"] = list(pivot)
    obj["bind_parent"] = parent.get("joint_name", "root")
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = .05
    return obj


def _box(name, loc, size, mat, joint, bevel=.006):
    pivot = Vector(joint.get("bind_pivot_runtime", [0, 0, 0]))
    return box(name, Vector(loc) - pivot, size, mat, joint, bevel=bevel)


def _ico(name, loc, radius, mat, joint, scale=(1, 1, 1)):
    pivot = Vector(joint.get("bind_pivot_runtime", [0, 0, 0]))
    return ico(name, Vector(loc) - pivot, radius, mat, joint, scale=scale, subdivisions=1)


def _smooth(obj):
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def _rounded_cloth_join(name, loc, radii, mat, joint):
    """Soft cloth connection; deliberately avoids visible icosahedron diamonds."""
    pivot = Vector(joint.get("bind_pivot_runtime", [0, 0, 0]))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1,
                                        location=xyz(Vector(loc) - pivot))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (radii[0], radii[2], radii[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.parent = joint
    obj.data.materials.append(mat)
    return _smooth(obj)


def _palette(low):
    mats = {
        "cloth": material("Personnel_Cloth", "#3C6469", .83),
        "vest": material("Personnel_Vest", "#D4A744", .78),
        "skin": material("Personnel_Skin", "#CAA282", .9),
        "boots": material("Personnel_Boots", "#303A3D", .9),
        "hair": material("Personnel_Hair", "#443F37", .9),
        "reflective": material("Personnel_Reflective", "#CED3C9", .76),
    }
    mats["helmet"] = mats["vest"] if low else material("Personnel_Helmet", "#D8AC4C", .7)
    mats["eye"] = mats["boots"]
    return mats


SHIRT_PROFILE = ((.865, .147, .104, -.012), (1.07, .171, .118, -.015),
                 (1.282, .202, .108, -.015), (1.354, .143, .077, -.013))


def _profile_at(y):
    for index in range(len(SHIRT_PROFILE) - 1):
        a, b = SHIRT_PROFILE[index:index + 2]
        if y <= b[0]:
            t = max(0, (y - a[0]) / (b[0] - a[0]))
            return tuple(a[i] + (b[i] - a[i]) * t for i in range(1, 4))
    return SHIRT_PROFILE[-1][1:]


def _torso_mesh(joint, offset, low, mats):
    sides = 8 if low else 16
    vertices = [(width * math.cos(math.tau * i / sides), y + offset,
                 z + depth * math.sin(math.tau * i / sides))
                for y, width, depth, z in SHIRT_PROFILE for i in range(sides)]
    faces = [tuple(range(sides))]
    for row in range(len(SHIRT_PROFILE) - 1):
        for i in range(sides):
            a, b = row * sides + i, row * sides + (i + 1) % sides
            # Fixed diagonal shared by the exact garment envelope below.
            faces.extend(((a, a + sides, b + sides), (a, b + sides, b)))
    faces.append(tuple((len(SHIRT_PROFILE) - 1) * sides + i for i in reversed(range(sides))))
    shirt = _mesh("shaped_shirt_torso", vertices, faces, mats["cloth"], joint)
    if not low:
        for face in shirt.data.polygons:
            face.use_smooth = face.center.z + joint["bind_pivot_runtime"][1] > 1.175 + offset


def _cloth_vest(joint, offset, low, mats):
    sides = 8 if low else 16
    # Same angular grid AND triangle diagonals as the shirt. Every clipped vest
    # point is a barycentric point on the corresponding outer-offset triangle,
    # so the shirt peak at Y=1.282 cannot pierce a stretched garment chord.
    heights = []
    for i in range(sides):
        angle = math.tau * i / sides
        front, lateral = math.sin(angle), abs(math.cos(angle))
        top = 1.325
        if front > .65:
            top = 1.19 + .145 * min(1, lateral / .55)
        elif lateral > .85:
            top = 1.295
        heights.append(top)
    vertices, faces, lookup = [], [], {}

    def index(point):
        key = tuple(round(value, 9) for value in point)
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(point)
        return lookup[key]

    for row in range(len(SHIRT_PROFILE) - 1):
        y0, y1 = SHIRT_PROFILE[row][0], SHIRT_PROFILE[row + 1][0]
        for i in range(sides):
            j = (i + 1) % sides
            for triangle in (((0, y0), (1, y0), (1, y1)),
                             ((0, y0), (1, y1), (0, y1))):
                polygon = list(triangle)
                clipped = []
                for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                    ga = heights[i] + (heights[j] - heights[i]) * a[0] - a[1]
                    gb = heights[i] + (heights[j] - heights[i]) * b[0] - b[1]
                    if ga >= -1e-10:
                        clipped.append(a)
                    if (ga >= 0) != (gb >= 0):
                        t = ga / (ga - gb)
                        clipped.append((a[0] + (b[0] - a[0]) * t,
                                        a[1] + (b[1] - a[1]) * t))
                if len(clipped) < 3:
                    continue
                corners = []
                for angular, y in ((i, y0), (j, y0), (j, y1), (i, y1)):
                    width, depth, z = _profile_at(y)
                    angle = math.tau * angular / sides
                    corners.append(Vector(((width + .004) * math.cos(angle),
                                           y + offset,
                                           z + (depth + .004) * math.sin(angle))))
                face = []
                for u, y in clipped:
                    v = (y - y0) / (y1 - y0)
                    if v <= u:
                        point = corners[0] * (1 - u) + corners[1] * (u - v) + corners[2] * v
                    else:
                        point = corners[0] * (1 - v) + corners[2] * u + corners[3] * (v - u)
                    candidate = index(tuple(point))
                    if not face or face[-1] != candidate:
                        face.append(candidate)
                if len(face) > 1 and face[0] == face[-1]:
                    face.pop()
                if len(set(face)) >= 3:
                    faces.append(tuple(reversed(face)))
    vest = _mesh("continuous_tailored_vest", vertices, faces, mats["vest"], joint)
    if not low:
        thickness = vest.modifiers.new("Real cloth edge thickness", "SOLIDIFY")
        thickness.thickness = .002
        thickness.offset = 0
    for centre in (.966, 1.047):
        rings = []
        for y in (centre - .01, centre + .01):
            width, depth, z = _profile_at(y)
            rings.append((y + offset, width + .006, depth + .006, z, 0))
        _loft("vest_wrapped_reflective_band",
              rings,
              mats["reflective"], joint, sides, cap=False)
    if not low:
        zipper = []
        for y in (.875, .966, 1.07, 1.17):
            _, depth, z = _profile_at(y)
            zipper.extend(((-.004, y + offset, z + depth + .006),
                           (.004, y + offset, z + depth + .006)))
        _mesh("vest_centre_zip", zipper,
              [(i, i + 1, i + 3, i + 2) for i in (0, 2, 4)], mats["cloth"], joint)
        # Two folded shirt collar leaves, not a raised cylinder around the neck.
        for s in (-1, 1):
            vertices = [(s * .022, 1.381 + offset, .047),
                        (s * .065, 1.368 + offset, .033),
                        (s * .082, 1.329 + offset, .066),
                        (s * .048, 1.314 + offset, .092),
                        (s * .025, 1.355 + offset, .072)]
            projected_area = sum(vertices[i][0] * vertices[(i + 1) % 5][1]
                                 - vertices[(i + 1) % 5][0] * vertices[i][1]
                                 for i in range(5))
            if projected_area < 0:
                vertices.reverse()
            # The small cloth flap is closed with a 4mm back surface.
            vertices += [(x, y, z - .004) for x, y, z in vertices]
            faces = [tuple(range(5)), tuple(reversed(range(5, 10)))]
            faces += [(i, (i + 1) % 5, (i + 1) % 5 + 5, i + 5) for i in range(5)]
            _mesh("shirt_folded_collar", vertices, faces, mats["cloth"], joint)


def _head(joint, offset, low, mats):
    sides = 8 if low else 14
    # Head is a single volumetric tapered cheek/jaw shape, with no box overlay.
    head_mesh = _loft("sculpted_head", [(1.435 + offset, .061, .051, .003, 0),
                            (1.46 + offset, .080, .069, .002, 0),
                            (1.505 + offset, .094, .082, -.003, 0),
                            (1.566 + offset, .096, .083, -.009, 0),
                            (1.614 + offset, .080, .070, -.015, 0),
                            (1.638 + offset, .052, .047, -.018, 0)]
          if not low else [(1.424 + offset, .047, .046, .002, 0),
                           (1.49 + offset, .089, .079, -.002, 0),
                           (1.577 + offset, .094, .080, -.012, 0),
                           (1.63 + offset, .060, .054, -.018, 0)],
          mats["skin"], joint, sides)
    if not low:
        _smooth(head_mesh)
    _loft("hair_cap", [(1.588 + offset, .093, .081, -.019, 0),
                        (1.631 + offset, .078, .071, -.020, 0),
                        (1.647 + offset, .047, .045, -.021, 0)],
          mats["hair"], joint, 8 if low else 12)
    # Hair continues down the actual rear skull; it is not a floating hat band.
    segments = 4 if low else 8
    vertices = []
    for row in range(2):
        for i in range(segments + 1):
            angle = math.pi + math.pi * i / segments
            y = 1.479 + .065 * abs(math.cos(angle)) if row == 0 else 1.606
            vertices.append((.096 * math.cos(angle), y + offset,
                             -.011 + .083 * math.sin(angle)))
    step = segments + 1
    faces = [(i + step, i + step + 1, i + 1, i) for i in range(segments)]
    _mesh("hair_nape_and_rear_skull", vertices, faces, mats["hair"], joint)
    for s in (-1, 1):
        if low:
            _loft("ear", [(1.51 + offset, .012, .015, -.008, s * .094),
                           (1.552 + offset, .014, .018, -.008, s * .094)],
                  mats["skin"], joint, 4)
            _box("eye", (s * .034, 1.55 + offset, .071), (.013, .014, .007),
                 mats["eye"], joint, bevel=0)
        else:
            _ico("ear", (s * .096, 1.526 + offset, -.006), .025,
                 mats["skin"], joint, scale=(.58, 1, .73))
            _ico("eye", (s * .034, 1.55 + offset, .071), .009,
                 mats["eye"], joint, scale=(.72, .95, .4))
            _box("eyebrow", (s * .034, 1.574 + offset, .068), (.028, .006, .007),
                 mats["hair"], joint, bevel=.002)
            # Sideburns join the back hair but leave the face profile visible.
            _loft("hair_sideburn", [(1.537 + offset, .012, .018, -.008, s * .088),
                                    (1.602 + offset, .014, .025, -.016, s * .087)],
                  mats["hair"], joint, 6)
    _sweep("nose", [((0, 1.541 + offset, .071), .017),
                     ((0, 1.513 + offset, .093), .025),
                     ((0, 1.502 + offset, .080), .020)], mats["skin"], joint,
           sides=4 if low else 6, depth_ratio=.8)
    if not low:
        # Restrained shallow smile, small enough to read as a face rather than mask.
        _sweep("mouth", [((-.024, 1.476 + offset, .070), .0035),
                          ((0, 1.471 + offset, .077), .0035),
                          ((.024, 1.476 + offset, .070), .0035)],
               mats["hair"], joint, sides=4, depth_ratio=.65)
    _loft("hardhat_brim", [(1.622 + offset, .126, .132, .006, 0),
                           (1.637 + offset, .125, .130, .006, 0)],
          mats["helmet"], joint, 8 if low else 14)
    _loft("hardhat_dome", [(1.633 + offset, .107, .105, -.015, 0),
                           (1.672 + offset, .102, .100, -.017, 0),
                           (1.693 + offset, .065, .065, -.018, 0),
                           (1.70 + offset, .040, .043, -.018, 0)],
          mats["helmet"], joint, 8 if low else 12)
    if not low:
        _box("hardhat_longitudinal_rib", (0, 1.682 + offset, -.020),
             (.019, .027, .137), mats["helmet"], joint, bevel=.006)


def _boot(joint, x, ground, z, low, mats):
    sides = 6 if low else 10
    _loft("boot_thick_sole", [(ground, .071, .126, z + .025, x),
                             (ground + .034, .071, .126, z + .025, x)],
          mats["boots"], joint, sides)
    _loft("boot_upper", [(ground + .03, .067, .121, z + .025, x),
                         (ground + .086, .065, .112, z + .021, x),
                         (ground + .176, .054, .074, z - .014, x)],
          mats["boots"], joint, sides)
    if not low:
        _box("boot_toe_cap", (x, ground + .066, z + .117), (.107, .022, .025),
             mats["boots"], joint, bevel=.008)
        for y in (.091, .113):
            _box("boot_lace", (x, ground + y, z + .090), (.074, .005, .006),
                 mats["hair"], joint, bevel=.001)


def _hand(joint, centre, low, mats, grip=False):
    x, y, z = centre
    if grip:
        _loft("curved_grip_palm", [(y - .024, .036, .028, z, x),
                                  (y + .024, .036, .027, z - .003, x)],
              mats["skin"], joint, 6 if low else 10)
        if not low:
            for i in range(4):
                dx = (i - 1.5) * .015
                _sweep("curved_grip_finger", [((x + dx, y + .012, z + .019), .013),
                                              ((x + dx, y - .013, z + .035), .013),
                                              ((x + dx, y - .029, z + .014), .010)],
                       mats["skin"], joint, sides=6)
            inward = -1 if x > 0 else 1
            _sweep("grip_thumb", [((x + inward * .035, y + .008, z), .022),
                                   ((x + inward * .031, y - .021, z + .012), .018)],
                   mats["skin"], joint, sides=6)
    else:
        _loft("hand_palm", [(y - .028, .029, .020, z + .003, x),
                            (y + .055, .030, .022, z, x)],
              mats["skin"], joint, 4 if low else 10)
        if not low:
            for i in range(4):
                dx = (i - 1.5) * .015
                length = .044 - .008 * abs(i - 1.5)
                _sweep("relaxed_finger", [((x + dx, y - .02, z + .004), .014),
                                          ((x + dx, y - .02 - length, z + .012), .011)],
                       mats["skin"], joint, sides=6)
            inward = -1 if x > 0 else 1
            _sweep("relaxed_thumb", [((x + inward * .027, y + .01, z + .007), .022),
                                      ((x + inward * .043, y - .021, z + .017), .016)],
                   mats["skin"], joint, sides=6)


def _build_person(low=False, seated=False, pose="neutral"):
    root = group("driver_root" if seated else "worker_root")
    root["front_axis"] = "+Z"
    root["preserve_articulation"] = not low
    root["role"] = "forklift_driver" if seated else "worker"
    root["role_tint_materials"] = "Personnel_Cloth;Personnel_Vest"
    root["pose"] = "seated" if seated else pose
    root["reference"] = "assets/references/v2/" + ("driver.png" if seated else "standing-worker.png")
    root["bind_pivot_runtime"] = [0, 0, 0]
    root["origin_description"] = "seat contact plane" if seated else "floor beneath worker"
    if seated:
        root["vehicle_seat_anchor_runtime"] = [0, .99, -.65]
        root["vehicle_floorboard_top_m"] = .54
    else:
        root["cart_attach_offset_runtime"] = [0, 0, .62]
        root["cart_hand_targets_runtime"] = json.dumps([[-.18, .94, .28], [.18, .94, .28]])
    mats = _palette(low)
    sides = 8 if low else 12
    limb_sides = 4 if low else 10
    offset = -.775 if seated else 0
    pelvis_pivot = (0, .825 + offset, -.01)
    pelvis = _joint("pelvis", pelvis_pivot, root)
    torso_pivot = (0, .885 + offset, -.01)
    torso = _joint("torso", torso_pivot, pelvis, pelvis_pivot)
    head_pivot = (0, 1.393 + offset, -.004)
    head = _joint("head", head_pivot, torso, torso_pivot)
    _loft("joined_trouser_hips", [(.746 + offset, .13, .087, -.01, 0),
                                 (.818 + offset, .157, .102, -.014, 0),
                                 (.902 + offset, .143, .096, -.014, 0)],
          mats["cloth"], pelvis, sides)
    _torso_mesh(torso, offset, low, mats)
    _cloth_vest(torso, offset, low, mats)
    _loft("shirt_collar_back_and_neck_base",
          [(1.347 + offset, .075, .061, -.008, 0),
           (1.390 + offset, .058, .054, -.006, 0)],
          mats["cloth"], torso, 6 if low else 10)
    _loft("short_natural_neck", [(1.344 + offset, .050, .051, -.006, 0),
                                (1.444 + offset, .049, .050, -.004, 0)],
          mats["skin"], head, 6 if low else 10)
    _head(head, offset, low, mats)

    for s, suffix in ((-1, "L"), (1, "R")):
        if seated:
            hip = (s * .092, .073, .008)
            knee = (s * .125, .030, .343)
            ankle = (s * .13, -.32, .408)
            ground, foot_z = -.45, .432
        else:
            hip = (s * .093, .79, -.011)
            knee = (s * .111, .463, .012)
            ankle = (s * .117, .161, -.012)
            ground, foot_z = 0, -.004
        thigh = _joint("thigh_" + suffix, hip, pelvis, pelvis_pivot)
        shin = _joint("shin_" + suffix, knee, thigh, hip)
        foot = _joint("foot_" + suffix, (ankle[0], ground + .055, foot_z), shin, knee)
        middle = tuple(Vector(hip).lerp(Vector(knee), .48))
        _sweep("tailored_thigh_" + suffix, [(hip, .183), (middle, .176), (knee, .143)],
               mats["cloth"], thigh, limb_sides, .88)
        calf = tuple(Vector(knee).lerp(Vector(ankle), .40))
        _sweep("shaped_calf_" + suffix, [(knee, .145), (calf, .15), (ankle, .108)],
               mats["cloth"], shin, limb_sides, .85)
        if low:
            _ico("cloth_knee_join_" + suffix, knee, .080, mats["cloth"], shin)
        else:
            _rounded_cloth_join("cloth_knee_join_" + suffix, knee,
                                (.073, .070, .065), mats["cloth"], shin)
        _boot(foot, ankle[0], ground, foot_z, low, mats)
        if not low:
            p = Vector(hip).lerp(Vector(knee), .35)
            p.x += s * .073
            _box("attached_cargo_pocket_" + suffix, p, (.025, .112, .104),
                 mats["cloth"], thigh, bevel=.008)
            _box("cargo_pocket_flap_" + suffix, (p.x + s * .003, p.y + .048, p.z + .004),
                 (.028, .027, .111), mats["cloth"], thigh, bevel=.005)

        shoulder = (s * .176, 1.303 + offset, -.010)
        if seated:
            elbow = (s * .22, .294, .137)
            wrist = (s * .115, .149, .352)
            palm = (s * .108, .14, .38)
            grip = True
        elif pose == "cart":
            elbow = (s * .25, 1.082, .09)
            wrist = (s * .183, .953, .25)
            palm = (s * .18, .94, .28)
            grip = True
        else:
            elbow = (s * .235, 1.082, .018)
            wrist = (s * .247, .88, .055)
            palm = (s * .247, .828, .065)
            grip = False
        upper = _joint("upper_arm_" + suffix, shoulder, torso, torso_pivot)
        lower = _joint("forearm_" + suffix, elbow, upper, shoulder)
        hand = _joint("hand_" + suffix, wrist, lower, elbow)
        bicep = tuple(Vector(shoulder).lerp(Vector(elbow), .4))
        shoulder_cap = (s * .146, 1.329 + offset, -.010)
        shoulder_round = (s * .194, 1.284 + offset, -.009)
        shoulder_rings = [(shoulder_cap, .126), (shoulder_round, .167),
                          (bicep, .153), (elbow, .113)] if low else [
                          ((s * .133, 1.311 + offset, -.010), .102),
                          ((s * .176, 1.273 + offset, -.009), .146),
                          (bicep, .148), (elbow, .113)]
        arm_mesh = _sweep("sloped_shoulder_and_upper_arm_" + suffix,
               shoulder_rings,
               mats["cloth"], upper, limb_sides, .94)
        if not low:
            _smooth(arm_mesh)
        middle = tuple(Vector(elbow).lerp(Vector(wrist), .5))
        _sweep("tapered_forearm_" + suffix,
               [(elbow, .115), (middle, .109), (wrist, .079)],
               mats["cloth"], lower, limb_sides, .91)
        if low:
            _ico("cloth_elbow_join_" + suffix, elbow, .065, mats["cloth"], lower)
        else:
            _rounded_cloth_join("cloth_elbow_join_" + suffix, elbow,
                                (.058, .060, .055), mats["cloth"], lower)
        if not low:
            near = tuple(Vector(elbow).lerp(Vector(wrist), .88))
            _sweep("sleeve_cuff_" + suffix, [(near, .092), (wrist, .089)],
                   mats["cloth"], lower, sides=8, depth_ratio=.95)
        _hand(hand, palm, low, mats, grip)

    pivots = {obj["joint_name"]: list(obj["bind_pivot_runtime"])
              for obj in root.children_recursive if obj.get("joint_name")}
    root["joint_pivots_json"] = json.dumps(pivots, separators=(",", ":"))
    root["animation_contract"] = "named rigid joint parents; bind pose only; no armature"
    return root


def build_high_worker(pose="neutral"):
    return _build_person(low=False, seated=False, pose=pose)


def build_low_worker():
    return _build_person(low=True, seated=False)


def build_picker_worker():
    return build_high_worker(pose="cart")


def build_seated_driver():
    return _build_person(low=False, seated=True)


def build_picking_cart():
    root = group("picking_cart_root")
    root["bind_pivot_runtime"] = [0, 0, 0]
    root["role"] = "picker_cart"
    root["preserve_articulation"] = True
    root["front_axis"] = "+Z"
    root["origin_description"] = "floor centre of cart footprint"
    root["worker_attach_offset_runtime"] = [0, 0, .62]
    root["handle_targets_runtime"] = json.dumps([[-.18, .94, -.34], [.18, .94, -.34]])
    root["reference"] = "assets/references/picker-cart-reference.png"
    steel = material("Cart_Charcoal_Steel", "#35434C", .74, .15)
    teal = material("Cart_Teal_Panel", "#3C6469", .83)
    safety = material("Cart_Safety", "#D4A744", .78)
    rubber = material("Personnel_Boots", "#303A3D", .9)
    hub = material("Cart_Hub", "#77858A", .65, .25)
    for x in (-.232, .232):
        for z in (-.255, .255):
            label = ("front" if z > 0 else "rear") + ("_L" if x < 0 else "_R")
            swivel_pivot = (x, .163, z)
            swivel = _joint("swivel_" + label, swivel_pivot, root)
            swivel["rotation_axis_runtime"] = "Y"
            wheel = _joint("wheel_" + label, (x, .068, z), swivel, swivel_pivot)
            wheel["rotation_axis_runtime"] = "X"
            cylinder("caster_tyre", (0, 0, 0), .068, .042, rubber, wheel,
                     axis="X", vertices=12)
            cylinder("caster_hub", (0, 0, 0), .029, .046, hub, wheel,
                     axis="X", vertices=8)
            _box("caster_hub_spin_mark", (x + (.025 if x > 0 else -.025), .081, z),
                 (.006, .038, .009), steel, wheel, bevel=.001)
            for dx in (-.03, .03):
                _box("caster_yoke", (x + dx, .112, z), (.012, .086, .027),
                     steel, swivel, bevel=.003)
            cylinder("caster_swivel", (x, .163, z), .024, .025, hub, root, vertices=8)
    box("cart_lower_shelf", (0, .198, 0), (.55, .038, .65), steel, root, bevel=.007)
    box("cart_basket_floor", (0, .538, 0), (.535, .03, .63), steel, root, bevel=.006)
    for x in (-.252, .252):
        for z in (-.30, .30):
            box("cart_post", (x, .483, z), (.032, .55, .032), steel, root, bevel=.004)
            box("cart_corner_safety", (x, .594, z), (.042, .055, .042),
                safety, root, bevel=.004)
        box("basket_side_inset", (x, .615, 0), (.021, .12, .56), teal, root, bevel=.003)
        box("basket_side_top", (x, .776, 0), (.032, .032, .65), steel, root, bevel=.005)
        for z in (-.15, 0, .15):
            box("basket_vertical_rail", (x, .708, z), (.02, .135, .02),
                steel, root, bevel=.002)
        beam("handle_stem", (x, .76, -.30), (x, .918, -.363), .033, steel, root)
        beam("handle_curve", (x, .918, -.363), (x * .88, .94, -.34), .033, steel, root)
    for z in (-.30, .30):
        box("basket_end_inset", (0, .615, z), (.48, .12, .021), teal, root, bevel=.003)
        box("basket_end_top", (0, .776, z), (.55, .032, .032), steel, root, bevel=.005)
        for x in (-.16, 0, .16):
            box("basket_end_rail", (x, .708, z), (.02, .135, .02), steel, root, bevel=.002)
    cylinder("hand_contact_bar", (0, .94, -.34), .022, .48, rubber, root,
             axis="X", vertices=10)
    # Cart remains empty: cargo and item counts belong to replay state.
    return root


def build():
    return build_high_worker()


if __name__ == "__main__":
    for asset_id, builder in (("standing-worker", build_high_worker),
                              ("picker-worker", build_picker_worker),
                              ("worker-low", build_low_worker),
                              ("driver", build_seated_driver),
                              ("picking-cart", build_picking_cart)):
        reset()
        finish(asset_id, builder())
