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


def _sweep(name, rings, mat, joint, sides=8, depth_ratio=.88, axis_start=None, axis_end=None, twists=None):
    """Smoothly tapered bent volume; each ring is (centre-point, full-width)."""
    vertices = []
    for row, (point, width) in enumerate(rings):
        previous = Vector(rings[max(0, row - 1)][0])
        following = Vector(rings[min(len(rings) - 1, row + 1)][0])
        axis = (following - previous).normalized()
        if row == 0 and axis_start is not None:
            axis = Vector(axis_start).normalized()
        if row == len(rings) - 1 and axis_end is not None:
            axis = Vector(axis_end).normalized()
        side = Vector((1, 0, 0))
        if abs(side.dot(axis)) > .94:
            side = Vector((0, 0, 1))
        side = (side - axis * side.dot(axis)).normalized()
        depth = axis.cross(side).normalized()
        for i in range(sides):
            angle = math.tau * i / sides + (twists[row] if twists else 0)
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


def _soft_sleeve(obj):
    # End caps must not contribute opposite normals to the two sleeves sharing
    # an elbow ring. Their side normals should continue across the cloth seam.
    for index, face in enumerate(obj.data.polygons):
        face.use_smooth = index not in (0, len(obj.data.polygons) - 1)
    return obj


def _rounded_cloth_join(name, loc, radii, mat, joint):
    """Soft cloth connection; deliberately avoids visible icosahedron diamonds."""
    pivot = Vector(joint.get("bind_pivot_runtime", [0, 0, 0]))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1,
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
        "cloth": material("Personnel_Cloth", "#496C6E", .86),
        "vest": material("Personnel_Vest", "#D8A644", .85),
        "skin": material("Personnel_Skin", "#CCA17F", .92),
        "boots": material("Personnel_Boots", "#303A3D", .9),
        "hair": material("Personnel_Hair", "#493A30", .92),
        "reflective": material("Personnel_Reflective", "#CED3C9", .76),
    }
    mats["helmet"] = mats["vest"] if low else material("Personnel_Helmet", "#D8AC4C", .7)
    mats["eye"] = mats["boots"]
    mats["eye_white"] = mats["skin"] if low else material("Personnel_Eye_White", "#E6DED1", .9)
    return mats


SHIRT_PROFILE = ((.855, .165, .111, -.012), (.965, .169, .115, -.012),
                 (1.105, .178, .122, -.015), (1.245, .202, .117, -.015),
                 (1.302, .200, .102, -.015), (1.360, .100, .066, -.008))


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
    sides = 8 if low else 16
    # Short, rounded jaw and cheek planes. The forehead continues under the hat;
    # the neck meets the underside rather than supporting a trapezoid mask.
    face_rings = [(1.412, .050, .045, .007), (1.432, .078, .062, .005),
                  (1.469, .096, .075, .000), (1.513, .099, .082, -.006),
                  (1.558, .094, .082, -.009), (1.600, .083, .074, -.012),
                  (1.622, .061, .056, -.013)]
    if low:
        face_rings = [face_rings[i] for i in (0, 2, 4, 6)]
    head_mesh = _loft("warm_sculpted_head",
                     [(y + offset, w, d, z, 0) for y, w, d, z in face_rings],
                     mats["skin"], joint, sides)
    if not low:
        _smooth(head_mesh)
    # A fitted hair shell, with a low rear hairline instead of a pointed nape.
    segments = 4 if low else 10
    vertices = []
    for row in range(3):
        for i in range(segments + 1):
            angle = math.pi + math.pi * i / segments
            y = (1.489 + .012 * abs(math.cos(angle)), 1.565, 1.607)[row]
            width, depth = ((.091, .078), (.097, .085), (.084, .077))[row]
            vertices.append((width * math.cos(angle), y + offset,
                             -.010 + depth * math.sin(angle)))
    step = segments + 1
    _mesh("fitted_hair_nape", vertices,
          [((row + 1) * step + i, (row + 1) * step + i + 1,
            row * step + i + 1, row * step + i)
           for row in range(2) for i in range(segments)], mats["hair"], joint)
    for s in (-1, 1):
        ear = _loft("small_natural_ear", [(1.482 + offset, .009, .014, -.012, s * .095),
                                           (1.509 + offset, .015, .019, -.012, s * .096),
                                           (1.534 + offset, .009, .014, -.012, s * .095)],
                    mats["skin"], joint, 4 if low else 8)
        if not low:
            _smooth(ear)
            eye = _loft("eye_white", [(1.521 + offset, .014, .004, .074, s * .035),
                                       (1.535 + offset, .014, .004, .074, s * .035)],
                        mats["eye_white"], joint, 8)
            _smooth(eye)
            pupil = _loft("eye_pupil", [(1.523 + offset, .005, .003, .079, s * .034),
                                        (1.534 + offset, .005, .003, .079, s * .034)],
                         mats["eye"], joint, 8)
            _smooth(pupil)
            _sweep("soft_eyebrow", [((s * .018, 1.550 + offset, .074), .005),
                                     ((s * .036, 1.554 + offset, .071), .006),
                                     ((s * .053, 1.550 + offset, .066), .004)],
                   mats["hair"], joint, sides=6)
            _loft("short_sideburn", [(1.526 + offset, .010, .017, -.011, s * .089),
                                      (1.589 + offset, .013, .024, -.014, s * .089)],
                  mats["hair"], joint, 6)
        else:
            _box("eye", (s * .034, 1.528 + offset, .077), (.010, .012, .005),
                 mats["eye"], joint, bevel=0)
    nose = _sweep("small_nose", [((0, 1.529 + offset, .073), .015),
                                 ((0, 1.496 + offset, .094), .023),
                                 ((0, 1.489 + offset, .079), .022)], mats["skin"], joint,
                  sides=4 if low else 8, depth_ratio=.7)
    if not low:
        _smooth(nose)
        _sweep("quiet_smile", [((-.024, 1.470 + offset, .076), .0028),
                                ((0, 1.463 + offset, .079), .0030),
                                ((.024, 1.470 + offset, .076), .0028)],
               mats["hair"], joint, sides=4, depth_ratio=.5)
    _loft("hardhat_rolled_brim", [(1.584 + offset, .118, .130, .010, 0),
                                  (1.590 + offset, .125, .141, .010, 0),
                                  (1.600 + offset, .119, .135, .010, 0)],
          mats["helmet"], joint, 8 if low else 16)
    _loft("hardhat_full_dome", [(1.596 + offset, .108, .108, -.010, 0),
                                (1.631 + offset, .104, .104, -.012, 0),
                                (1.665 + offset, .083, .083, -.013, 0),
                                (1.687 + offset, .052, .052, -.014, 0),
                                ((1.700 if low else 1.696) + offset, .018, .020, -.014, 0)],
          mats["helmet"], joint, 8 if low else 16)
    if not low:
        _sweep("hardhat_raised_centre_rib",
               [((0, 1.627 + offset, -.109), .014),
                ((0, 1.678 + offset, -.072), .016),
                ((0, 1.696 + offset, -.014), .018),
                ((0, 1.678 + offset, .044), .016),
                ((0, 1.627 + offset, .086), .014)],
               mats["helmet"], joint, sides=4, depth_ratio=.44)


def _boot(joint, x, ground, z, low, mats):
    sides = 4 if low else 10
    _loft("boot_thick_sole", [(ground, .070, .124, z + .025, x),
                             (ground + .012, .074, .128, z + .025, x),
                             (ground + .034, .072, .126, z + .025, x)],
          mats["boots"], joint, sides)
    _loft("boot_upper", [(ground + .03, .067, .121, z + .025, x),
                         (ground + .086, .065, .112, z + .021, x),
                         (ground + .176, .057, .074, z - .014, x)],
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
        _loft("hand_palm", [(y - .030, .030, .022, z + .005, x),
                            (y + .012, .035, .025, z + .002, x),
                            (y + .055, .028, .022, z, x)],
              mats["skin"], joint, 4 if low else 10)
        if not low:
            for i in range(4):
                dx = (i - 1.5) * .015
                length = .044 - .008 * abs(i - 1.5)
                _sweep("relaxed_finger", [((x + dx, y - .022, z + .005), .015),
                                          ((x + dx, y - .022 - length, z + .014), .012)],
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
    _loft("joined_trouser_hips", [(.742 + offset, .142, .102, -.01, 0),
                                 (.795 + offset, .176, .117, -.014, 0),
                                 (.870 + offset, .160, .106, -.014, 0),
                                 (.902 + offset, .158, .104, -.014, 0)],
          mats["cloth"], pelvis, sides)
    _torso_mesh(torso, offset, low, mats)
    _cloth_vest(torso, offset, low, mats)
    _loft("shirt_collar_back_and_neck_base",
          [(1.347 + offset, .075, .061, -.008, 0),
           (1.390 + offset, .058, .054, -.006, 0)],
          mats["cloth"], torso, 6 if low else 10)
    _loft("short_natural_neck", [(1.358 + offset, .052, .052, -.006, 0),
                                (1.434 + offset, .051, .051, -.004, 0)],
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
        middle = Vector(hip).lerp(Vector(knee), .42)
        middle.z += .007
        upper_knee = Vector(hip).lerp(Vector(knee), .88)
        leg_axis = Vector(ankle) - Vector(hip)
        _sweep("full_work_trouser_thigh_" + suffix,
               [(hip, .209), (tuple(middle), .213), (tuple(upper_knee), .177), (knee, .166)],
               mats["cloth"], thigh, limb_sides, 1.04, axis_end=leg_axis,
               twists=None if low else [0, .11, -.035, 0])
        calf = Vector(knee).lerp(Vector(ankle), .37)
        calf.z -= .013
        lower_calf = Vector(knee).lerp(Vector(ankle), .82)
        lower_calf.z += .004
        _sweep("folded_work_trouser_calf_" + suffix,
               [(knee, .166), (tuple(calf), .178), (tuple(lower_calf), .137), (ankle, .139)],
               mats["cloth"], shin, limb_sides, 1.00, axis_start=leg_axis,
               twists=None if low else [0, -.11, .075, 0])
        if not low and not seated:
            _rounded_cloth_join("hidden_cloth_knee_fill_" + suffix, knee,
                                (.072, .069, .072), mats["cloth"], shin)
        _boot(foot, ankle[0], ground, foot_z, low, mats)
        if not low:
            p = Vector(hip).lerp(Vector(knee), .35)
            p.x += s * .098
            _box("tailored_cargo_pocket_" + suffix, p, (.022, .115, .130),
                 mats["cloth"], thigh, bevel=.006)
            _box("soft_cargo_pocket_flap_" + suffix, (p.x + s * .003, p.y + .045, p.z),
                 (.026, .028, .137), mats["cloth"], thigh, bevel=.004)

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
        bicep = tuple(Vector(shoulder).lerp(Vector(elbow), .42))
        elbow_axis = Vector(wrist) - Vector(shoulder)
        shoulder_rings = [((s * .112, 1.313 + offset, -.010), .060),
                          ((s * .171, 1.275 + offset, -.010), .145),
                          (bicep, .166), (elbow, .137)]
        sleeve = _sweep("continuous_shoulder_and_sleeve_" + suffix,
                        shoulder_rings, mats["cloth"], upper, limb_sides, 1.02,
                        axis_end=elbow_axis)
        if not low:
            _soft_sleeve(sleeve)
        middle = Vector(elbow).lerp(Vector(wrist), .42)
        middle.z -= .004
        sleeve = _sweep("tapered_forearm_" + suffix,
                        [(elbow, .137), (tuple(middle), .143), (wrist, .101)],
                        mats["cloth"], lower, limb_sides, 1.02, axis_start=elbow_axis)
        if not low:
            _soft_sleeve(sleeve)
        if not low and not seated:
            _rounded_cloth_join("hidden_cloth_elbow_fill_" + suffix, elbow,
                                (.059, .057, .059), mats["cloth"], lower)
        if not low:
            near = tuple(Vector(elbow).lerp(Vector(wrist), .88))
            _sweep("folded_sleeve_cuff_" + suffix, [(near, .108), (wrist, .106)],
                   mats["cloth"], lower, sides=10, depth_ratio=1.02)
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


def _cart_tyre(joint, centre, mat):
    """Rounded tyre shoulders; the wheel axis and visible hub stay articulated."""
    x, y, z = centre
    sides = 20
    profile = ((-.024, .055), (-.021, .064), (-.014, .068),
               (.014, .068), (.021, .064), (.024, .055))
    vertices = [(x + dx, y + radius * math.cos(math.tau * i / sides),
                 z + radius * math.sin(math.tau * i / sides))
                for dx, radius in profile for i in range(sides)]
    faces = [tuple(reversed(range(sides)))]
    for row in range(len(profile) - 1):
        for i in range(sides):
            a, b = row * sides + i, row * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple((len(profile) - 1) * sides + i for i in range(sides)))
    tyre = _mesh("rounded_caster_tyre", vertices, faces, mat, joint)
    for poly in tyre.data.polygons[1:-1]:
        poly.use_smooth = True
    return tyre


def build_picking_cart():
    root = group("picking_cart_root")
    root["bind_pivot_runtime"] = [0, 0, 0]
    root["role"] = "picker_cart"
    root["preserve_articulation"] = True
    root["front_axis"] = "+Z"
    root["origin_description"] = "floor centre of cart footprint"
    root["worker_attach_offset_runtime"] = [0, 0, .62]
    root["handle_targets_runtime"] = json.dumps([[-.18, .94, -.34], [.18, .94, -.34]])
    root["basket_floor_top_m"] = .553
    root["basket_inner_size_runtime"] = [.610, .151, .564]
    root["basket_panel_clear_size_runtime"] = [.624, .151, .578]
    root["wheel_radius_m"] = .068
    root["reference"] = "assets/references/picker-cart-reference.png"
    steel = material("Cart_Charcoal_Steel", "#35434C", .77, .15)
    teal = material("Cart_Teal_Panel", "#496C6E", .85)
    safety = material("Cart_Safety", "#D4A744", .78)
    rubber = material("Personnel_Boots", "#303A3D", .9)
    hub = material("Cart_Hub", "#77858A", .65, .25)
    for x in (-.285, .285):
        for z in (-.255, .255):
            label = ("front" if z > 0 else "rear") + ("_L" if x < 0 else "_R")
            swivel_pivot = (x, .163, z)
            swivel = _joint("swivel_" + label, swivel_pivot, root)
            swivel["rotation_axis_runtime"] = "Y"
            wheel = _joint("wheel_" + label, (x, .068, z), swivel, swivel_pivot)
            wheel["rotation_axis_runtime"] = "X"
            _cart_tyre(wheel, (x, .068, z), rubber)
            cylinder("recessed_caster_hub", (0, 0, 0), .031, .051, hub, wheel,
                     axis="X", vertices=16)
            cylinder("caster_axle", (0, 0, 0), .012, .070, steel, wheel,
                     axis="X", vertices=12)
            _box("caster_hub_spin_spoke", (x + (.028 if x > 0 else -.028), .080, z),
                 (.004, .039, .008), steel, wheel, bevel=.001)
            for dx in (-.034, .034):
                _box("folded_caster_yoke", (x + dx, .114, z), (.012, .085, .037),
                     steel, swivel, bevel=.004)
            _box("caster_yoke_bridge", (x, .151, z), (.080, .014, .043),
                 steel, swivel, bevel=.003)
            cylinder("caster_swivel_bearing", (x, .165, z), .027, .025, hub, root, vertices=12)
            box("caster_chassis_mount", (x, .182, z), (.079, .018, .079),
                steel, root, bevel=.004)
    box("cart_lower_shelf", (0, .211, 0), (.69, .040, .65), steel, root, bevel=.009)
    box("cart_lower_shelf_inlay", (0, .233, 0), (.617, .008, .575), teal, root, bevel=.003)
    box("cart_basket_floor", (0, .538, 0), (.664, .03, .63), steel, root, bevel=.006)
    for x in (-.323, .323):
        for z in (-.30, .30):
            _sweep("continuous_cart_corner_post", [((x, .23, z), .032),
                                                      ((x, .54, z), .032),
                                                      ((x, .783, z), .036)],
                   steel, root, sides=10, depth_ratio=1)
            box("cart_corner_safety_bumper", (x, .559, z), (.049, .046, .049),
                safety, root, bevel=.006)
        box("solid_basket_side_panel", (x, .624, 0), (.022, .142, .568), teal, root, bevel=.004)
        _sweep("rounded_basket_side_rim", [((x, .783, -.317), .036),
                                           ((x, .783, .317), .036)],
               steel, root, sides=12, depth_ratio=1)
        for z in (-.15, 0, .15):
            box("basket_upper_short_rail", (x, .736, z), (.017, .089, .017),
                steel, root, bevel=.002)
        _sweep("one_piece_curved_handle_upright",
               [((x, .772, -.30), .034), ((math.copysign(.28, x), .868, -.347), .034),
                ((math.copysign(.25, x), .918, -.363), .034),
                ((math.copysign(.223, x), .94, -.34), .034)],
               steel, root, sides=12, depth_ratio=1)
    for z in (-.30, .30):
        box("solid_basket_end_panel", (0, .624, z), (.626, .142, .022), teal, root, bevel=.004)
        _sweep("rounded_basket_end_rim", [((-.323, .783, z), .036),
                                          ((.323, .783, z), .036)],
               steel, root, sides=12, depth_ratio=1)
        for x in (-.16, 0, .16):
            box("basket_end_upper_short_rail", (x, .736, z), (.017, .089, .017), steel, root, bevel=.002)
    cylinder("hand_contact_bar", (0, .94, -.34), .021, .48, rubber, root,
             axis="X", vertices=20)
    for x in (-.246, .246):
        cylinder("handle_closed_end_cap", (x, .94, -.34), .023, .016, steel, root,
                 axis="X", vertices=16)
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
