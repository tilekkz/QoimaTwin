"""Reference-led static saffron forklift. Runtime axes: X right, Y up, +Z forks."""
import math
import bpy
from mathutils import Vector
from asset_common import reset, material, group, box, cylinder, beam, finish


def _mesh(name, vertices, faces, mat, parent, bevel=0.01):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([(x, -z, y) for x, y, z in vertices], [], faces)
    mesh.materials.append(mat)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    if bevel:
        mod = obj.modifiers.new("Small softened mechanical edges", "BEVEL")
        mod.width = bevel
        mod.segments = 1
    obj.modifiers.new("Weighted face normals", "WEIGHTED_NORMAL")
    return obj


def _prism(name, points_x_y, z0, z1, mat, parent, bevel=0.01):
    # Mirrored side panels keep outward winding rather than flipped normals.
    area = sum(points_x_y[i][0] * points_x_y[(i + 1) % len(points_x_y)][1]
               - points_x_y[(i + 1) % len(points_x_y)][0] * points_x_y[i][1]
               for i in range(len(points_x_y)))
    if area < 0:
        points_x_y = list(reversed(points_x_y))
    count = len(points_x_y)
    verts = [(x, y, z) for z in (z0, z1) for x, y in points_x_y]
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count)
              for i in range(count)]
    return _mesh(name, verts, faces, mat, parent, bevel)


def _wheel(name, x, y, z, radius, tire, hub, steel, parent):
    cylinder(name + "_rubber_sidewall", (x, y, z), radius - 0.014, .18,
             tire, parent, axis="X", vertices=20)
    for i in range(16):
        angle = i * math.tau / 16
        tread = box(name + "_tread_%02d" % i,
                    (x, y + (radius - .014) * math.cos(angle),
                     z + (radius - .014) * math.sin(angle)),
                    (.182, .028, radius * .20), tire, parent, bevel=.004)
        tread.rotation_euler.x = angle
    side = 1 if x > 0 else -1
    cylinder(name + "_recessed_rim", (x + side * .091, y, z),
             radius * .58, .012, steel, parent, axis="X", vertices=16)
    cylinder(name + "_hub", (x + side * .098, y, z),
             radius * .35, .012, hub, parent, axis="X", vertices=12)
    for i in range(6):
        a = math.tau * i / 6
        cylinder(name + "_lug_%02d" % i,
                 (x + side * .100, y + radius * .43 * math.cos(a),
                  z + radius * .43 * math.sin(a)),
                 .013, .010, hub, parent, axis="X", vertices=6)


def _steering_ring(parent, mat, center, normal):
    bpy.ops.mesh.primitive_torus_add(major_segments=16, minor_segments=6,
                                   major_radius=.135, minor_radius=.017,
                                   location=(center[0], -center[2], center[1]))
    obj = bpy.context.object
    obj.name = "steering_wheel_ring"
    obj.rotation_euler = Vector((normal[0], -normal[2], normal[1])).to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    obj.parent = parent
    right = Vector((1, 0, 0))
    normal_v = Vector(normal).normalized()
    other = normal_v.cross(right).normalized()
    for i in range(3):
        a = math.tau * i / 3
        outer = Vector(center) + .125 * (right * math.cos(a) + other * math.sin(a))
        beam("steering_wheel_spoke_%d" % i, center, tuple(outer), .018, mat, parent)


def build():
    root = group("forklift_root")
    root["asset_id"] = "forklift"
    root["role"] = "static_set_dressing"
    root["front_axis"] = "+Z"
    root["reference"] = "assets/references/forklift.png"
    root["nominal_size_m"] = [1.1, 2.15, 2.6]
    saffron = material("industrial_saffron", "#EAB32F", .68)
    yellow_light = material("saffron_edge", "#F7C547", .66)
    yellow_dark = material("saffron_recess", "#B77C19", .74)
    dark = material("charcoal_steel", "#293238", .67, .25)
    steel = material("lift_steel", "#58626A", .55, .55)
    tire = material("rubber_tire", "#202529", .88)
    seat = material("seat_cushion", "#424B51", .85)
    silver = material("hydraulic_piston", "#AAB2B3", .38, .65)
    amber = material("amber_lamp", "#F6A51B", .4)
    red = material("rear_lamp", "#A1392C", .42)

    # A faceted chassis and sloping counterweight, rather than a stack of cubes.
    _prism("tapered_main_chassis",
           [(-.41, .15), (.41, .15), (.47, .42), (.46, .57),
            (-.46, .57), (-.47, .42)], -1.29, .22, saffron, root, .025)
    _prism("rear_counterweight",
           [(-.40, .20), (.40, .20), (.49, .66), (.46, .88),
            (.37, .96), (-.37, .96), (-.46, .88), (-.49, .66)],
           -1.30, -.83, saffron, root, .025)
    box("rear_hood_panel", (0, .964, -1.065), (.76, .016, .36),
        yellow_light, root, bevel=.018)
    box("rear_counterweight_seam", (0, .55, -1.299), (.81, .016, .006),
        yellow_dark, root, bevel=.003)
    box("rear_tow_recess", (0, .32, -1.302), (.22, .085, .013),
        dark, root, bevel=.014)
    for s in (-1, 1):
        _wheel(("left" if s < 0 else "right") + "_front", s * .45,
               .30, .06, .30, tire, dark, steel, root)
        _wheel(("left" if s < 0 else "right") + "_rear", s * .45,
               .225, -1.02, .225, tire, dark, steel, root)
        # Raised fenders follow the tire shoulder and form a connected side step.
        _prism("side_panel_%d" % s,
               [(s * .37, .47), (s * .48, .47), (s * .48, .80),
                (s * .37, .91)], -.88, -.48, saffron, root, .012)
        box("front_fender_%d" % s, (s * .43, .625, .06),
            (.22, .055, .55), yellow_light, root, bevel=.018)
        box("access_step_%d" % s, (s * .43, .40, -.37),
            (.20, .06, .33), dark, root, bevel=.008)
        for j in range(4):
            box("step_grip_%d_%d" % (s, j), (s * .43, .434, -.48 + .072*j),
                (.17, .007, .018), steel, root, bevel=.002)
        box("rear_light_black_housing_%d" % s, (s * .34, .85, -1.296),
            (.15, .10, .024), dark, root, bevel=.012)
        box("rear_red_lamp_%d" % s, (s * .34, .851, -1.313),
            (.12, .055, .012), red, root, bevel=.008)
        box("rear_amber_lamp_%d" % s, (s * .36, 1.005, -1.05),
            (.09, .075, .09), amber, root, bevel=.012)

    # Driver bay with a raised cushioned seat, visible steering column and levers.
    box("driver_floorboard", (0, .515, -.29), (.73, .045, .69),
        dark, root, bevel=.01)
    box("seat_pedestal", (0, .72, -.68), (.43, .35, .39), dark, root, bevel=.025)
    box("seat_lower_cushion", (0, .93, -.64), (.51, .12, .43), seat, root, bevel=.045)
    back = box("seat_back_cushion", (0, 1.20, -.85), (.49, .50, .12),
               seat, root, bevel=.045)
    back.rotation_euler.x = math.radians(-8)
    box("seat_back_inset", (0, 1.21, -.777), (.37, .35, .022), dark, root, bevel=.03)
    for s in (-1, 1):
        beam("seat_arm_support_%d" % s, (s*.27, .82, -.73),
             (s*.27, 1.0, -.68), .035, dark, root)
        box("seat_armrest_%d" % s, (s*.27, 1.025, -.65),
            (.065, .045, .28), seat, root, bevel=.02)
    beam("angled_steering_column", (0, .55, -.035),
         (0, 1.12, -.26), .075, dark, root)
    _steering_ring(root, dark, (0, 1.13, -.27), (0, .8, -.6))
    box("control_lever_console", (.31, .73, -.28), (.18, .18, .25),
        dark, root, bevel=.02)
    for i in range(2):
        beam("control_lever_%d" % i, (.265+.08*i, .82, -.25),
             (.265+.08*i, 1.00, -.20), .016, steel, root)
        cylinder("control_lever_grip_%d" % i, (.265+.08*i, 1.01, -.20),
                 .026, .055, dark, root, vertices=8)

    # Four connected roll cage uprights and a slatted overhead guard.
    for s in (-1, 1):
        beam("roll_cage_rear_%d" % s, (s*.39, .86, -1.04),
             (s*.39, 2.07, -.96), .075, dark, root)
        beam("roll_cage_front_%d" % s, (s*.39, .57, .08),
             (s*.39, 2.07, -.06), .075, dark, root)
        box("roof_longitudinal_rail_%d" % s, (s*.39, 2.085, -.51),
            (.095, .095, 1.08), dark, root, bevel=.018)
    for z in (-1.0, -.02):
        box("roof_cross_rail_%.2f" % z, (0, 2.085, z),
            (.87, .095, .09), dark, root, bevel=.015)
    for i in range(5):
        box("overhead_guard_slat_%d" % i, (0, 2.10, -.87+.175*i),
            (.72, .045, .055), steel, root, bevel=.006)

    # Nested mast, roller faces, hydraulic ram, visible chains and fork backrest.
    for s in (-1, 1):
        box("outer_mast_rail_%d" % s, (s*.34, 1.19, .285),
            (.11, 1.92, .14), dark, root, bevel=.01)
        box("mast_channel_recess_%d" % s, (s*.34, 1.19, .361),
            (.045, 1.76, .015), tire, root, bevel=.002)
        box("inner_mast_rail_%d" % s, (s*.245, 1.24, .385),
            (.062, 1.65, .075), steel, root, bevel=.006)
        for j, y in enumerate((.52, 1.36, 2.025)):
            cylinder("mast_roller_%d_%d" % (s,j), (s*.245, y, .437),
                     .047, .045, dark, root, axis="Z", vertices=12)
            cylinder("mast_roller_hub_%d_%d" % (s,j), (s*.245, y, .463),
                     .019, .012, silver, root, axis="Z", vertices=8)
        for j in range(19):
            box("lifting_chain_link_%d_%02d" % (s,j),
                (s*.12, .50+.081*j, .412), (.026, .060, .026),
                steel if j % 2 else dark, root, bevel=.003)
        for edge in (-1, 1):
            box("continuous_chain_side_%d_%d" % (s,edge),
                (s*.12+edge*.011, 1.266, .412), (.006, 1.59, .018),
                dark, root, bevel=.001)
    box("mast_upper_bridge", (0, 2.105, .29), (.79, .09, .16),
        dark, root, bevel=.012)
    box("mast_lower_bridge", (0, .30, .29), (.77, .10, .16),
        dark, root, bevel=.01)
    cylinder("hydraulic_ram_body", (0, .82, .32), .063, 1.03,
             dark, root, vertices=12)
    cylinder("hydraulic_ram_piston", (0, 1.47, .32), .027, .47,
             silver, root, vertices=12)
    cylinder("hydraulic_ram_collar", (0, 1.32, .32), .075, .07,
             steel, root, vertices=12)
    box("fork_carriage_top", (0, .69, .475), (.81, .095, .075),
        dark, root, bevel=.012)
    box("fork_carriage_bottom", (0, .24, .475), (.81, .085, .075),
        dark, root, bevel=.012)
    for x in (-.39, -.195, .195, .39):
        box("load_backrest_%.3f" % x, (x, .71, .483),
            (.033, .76, .045), steel, root, bevel=.006)
    box("load_backrest_header", (0, 1.09, .483), (.82, .045, .045),
        steel, root, bevel=.009)
    for s in (-1, 1):
        x = s*.225
        box("fork_heel_%d" % s, (x, .27, .53), (.115, .44, .068),
            steel, root, bevel=.009)
        vertices = [(x-.057, .045, .49), (x+.057, .045, .49),
                    (x+.057, .045, 1.30), (x-.057, .045, 1.30),
                    (x-.057, .096, .49), (x+.057, .096, .49),
                    (x+.047, .061, 1.30), (x-.047, .061, 1.30)]
        _mesh("tapered_flat_fork_%d" % s, vertices,
              [(0,1,2,3), (4,7,6,5), (0,4,5,1), (1,5,6,2),
               (2,6,7,3), (3,7,4,0)], steel, root, .004)
    return root


if __name__ == "__main__":
    reset()
    finish("forklift", build())
