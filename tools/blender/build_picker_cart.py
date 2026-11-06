"""Dimensional picker and connected narrow trolley, in runtime metres / Y-up.

Visual source: assets/references/picker-cart-reference.png. The logical actor
origin stays on the floor under the person; the cart projects forward along +Z.
"""
import math
import bpy
from mathutils import Vector

from asset_common import reset, material, group, box, cylinder, beam, ico, finish


def mesh_object(name, vertices, faces, mat, parent):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([(x, -z, y) for x, y, z in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def loft(name, rings, mat, parent, sides=8):
    """Horizontal elliptical rings (height, half-width, half-depth, centre-Z)."""
    vertices = []
    for height, width, depth, centre_z in rings:
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            vertices.append((width * math.cos(angle), height,
                             centre_z + depth * math.sin(angle)))
    faces = [tuple(range(sides))]
    for ring in range(len(rings) - 1):
        for i in range(sides):
            a = ring * sides + i
            b = ring * sides + (i + 1) % sides
            faces.append((a + sides, b + sides, b, a))
    faces.append(tuple((len(rings) - 1) * sides + i for i in reversed(range(sides))))
    return mesh_object(name, vertices, faces, mat, parent)


def limb(name, start, end, width_start, width_end, mat, parent, depth_scale=0.85):
    """Eight-sided tapered limb with real elbow/knee silhouette."""
    start, end = Vector(start), Vector(end)
    direction = (end - start).normalized()
    side = Vector((1, 0, 0))
    if abs(side.dot(direction)) > .92:
        side = Vector((0, 0, 1))
    side = (side - direction * side.dot(direction)).normalized()
    depth = direction.cross(side).normalized()
    profile = [(-.32, -.5), (.32, -.5), (.5, -.32), (.5, .32),
               (.32, .5), (-.32, .5), (-.5, .32), (-.5, -.32)]
    vertices = []
    for centre, width in [(start, width_start), (end, width_end)]:
        for a, b in profile:
            v = centre + side * (a * width) + depth * (b * width * depth_scale)
            vertices.append(tuple(v))
    faces = [tuple(reversed(range(8))), tuple(range(8, 16))]
    for i in range(8):
        faces.append((i, (i + 1) % 8, (i + 1) % 8 + 8, i + 8))
    return mesh_object(name, vertices, faces, mat, parent)


def build():
    root = group("picker_root__P1")
    root["asset_id"] = "picker-cart"
    root["role"] = "picker"
    root["layout_version"] = "qoyma-20x18-v1"
    root["front_axis"] = "+Z"
    root["origin_description"] = "floor beneath worker feet"
    body = group("worker_components")
    body.parent = root
    cart = group("cart__P1")
    cart.parent = root
    cart["role"] = "picking_trolley"

    steel = material("Steel_Charcoal", "#35434C", roughness=.72, metallic=.15)
    teal = material("Worker_Teal", "#34616A", roughness=.82)
    teal_dark = material("Worker_Teal_Shadow", "#294F57", roughness=.82)
    saffron = material("Safety_Saffron", "#D8A744", roughness=.7)
    reflective = material("Reflective_Warm_Grey", "#D2D5C9", roughness=.67)
    skin = material("Skin_Warm", "#CFA17F", roughness=.86)
    skin_light = material("Skin_Highlight", "#DAB18D", roughness=.86)
    boots = material("Boots_Charcoal", "#303437", roughness=.9)
    rubber = material("Rubber_Dark", "#252C30", roughness=.9)
    hair = material("Hair_Dark", "#3F3A34", roughness=.9)
    carton = material("Carton_Tan", "#BB905B", roughness=.88)
    tape = material("Carton_Tape", "#D6B884", roughness=.86)
    hub = material("Caster_Hub", "#748187", roughness=.6, metallic=.25)

    # Grounded shoes, tapered trouser legs, and attached cargo pockets.
    for side in (-1, 1):
        x = side * .103
        box("boot_sole", (x, .023, .025), (.155, .046, .265), boots, body, bevel=.012)
        box("boot_upper", (x, .091, .016), (.142, .108, .225), boots, body, bevel=.019)
        box("boot_cuff", (x, .164, -.016), (.132, .066, .148), teal_dark, body, bevel=.008)
        for y in (.104, .13):
            box("boot_lace", (x, y, .13), (.082, .009, .008), hub, body, bevel=.002)
        limb("trouser_shin", (x, .17, -.018), (side * .115, .46, -.055),
             .133, .153, teal, body)
        limb("trouser_thigh", (side * .115, .46, -.055), (side * .104, .805, -.025),
             .153, .176, teal, body)
        box("cargo_pocket", (side * .186, .638, .004), (.035, .16, .105),
            teal_dark, body, bevel=.009)
        box("cargo_pocket_flap", (side * .188, .706, .008), (.038, .038, .115),
            teal, body, bevel=.006)
    loft("hips", [(.745, .145, .095, -.02), (.84, .162, .10, -.02),
                  (.91, .145, .095, -.02)], teal_dark, body)
    box("belt", (0, .87, -.017), (.294, .038, .19), boots, body, bevel=.008)
    box("belt_buckle", (0, .87, .085), (.039, .029, .013), hub, body, bevel=.003)
    loft("work_shirt", [(.88, .145, .096, -.02), (1.02, .16, .108, -.024),
                        (1.24, .198, .116, -.033), (1.325, .177, .09, -.03)],
         teal, body)

    # The vest wraps across the back and has separate front panels and strips.
    box("vest_back", (0, 1.107, -.135), (.293, .405, .025), saffron, body, bevel=.012)
    for x in (-.09, .09):
        box("vest_front_panel", (x, 1.095, .092), (.105, .386, .031),
            saffron, body, bevel=.01)
        box("vest_front_reflective", (x, 1.118, .110), (.023, .34, .008),
            reflective, body, bevel=.002)
        box("vest_back_reflective", (x, 1.139, -.151), (.023, .33, .008),
            reflective, body, bevel=.002)
        beam("vest_shoulder_strap", (x, 1.29, .089), (x, 1.31, -.135),
             .06, saffron, body)
    box("vest_front_cross_strip", (0, 1.015, .112), (.288, .025, .009),
        reflective, body, bevel=.002)
    box("vest_back_cross_strip", (0, 1.015, -.152), (.286, .025, .009),
        reflective, body, bevel=.002)

    # Arms bend forward to the push bar. Small cuffs and hands close each join.
    for side in (-1, 1):
        shoulder = (side * .19, 1.265, -.022)
        elbow = (side * .257, 1.066, .105)
        wrist = (side * .185, .973, .338)
        limb("shirt_upper_arm", shoulder, elbow, .156, .13, teal, body)
        ico("elbow", elbow, .069, teal, body, subdivisions=1)
        limb("shirt_forearm", elbow, wrist, .13, .094, teal, body)
        box("shirt_cuff", (side * .185, .98, .321), (.098, .065, .072),
            teal_dark, body, bevel=.009)
        box("hand_grip", (side * .181, .974, .365), (.084, .065, .083),
            skin_light, body, bevel=.018)
        box("hand_thumb", (side * .145, .966, .365), (.025, .041, .045),
            skin, body, bevel=.008)
        for offset in (-.019, 0, .019):
            box("finger_division", (side * .181 + offset, .949, .397),
                (.005, .011, .006), skin, body, bevel=.001)

    # Proportionate face: roughly one seventh of full height including helmet.
    cylinder("neck", (0, 1.347, -.026), .06, .095, skin, body, vertices=10)
    cylinder("shirt_collar", (0, 1.326, -.026), .072, .041, teal_dark, body,
             vertices=10)
    for side in (-1, 1):
        beam("collar_fold", (side * .047, 1.325, .043),
             (side * .067, 1.275, .093), .037, teal_dark, body)
    loft("head", [(1.385, .061, .067, -.015), (1.416, .087, .087, -.009),
                  (1.516, .100, .092, -.015), (1.584, .082, .075, -.021)],
         skin_light, body, sides=10)
    loft("hair_back", [(1.45, .09, .071, -.046), (1.56, .104, .083, -.031),
                       (1.602, .085, .07, -.028)], hair, body, sides=10)
    # Face is slightly ahead of the hair shell, making eyes/nose visibly attached.
    loft("face_cheeks_and_jaw", [(1.401, .052, .038, .037),
                                (1.428, .071, .047, .039),
                                (1.50, .082, .05, .036),
                                (1.551, .076, .043, .035),
                                (1.563, .061, .030, .030)],
         skin_light, body, sides=10)
    for side in (-1, 1):
        ico("ear", (side * .104, 1.483, -.008), .032, skin, body,
            scale=(.55, 1.0, .7), subdivisions=1)
        ico("eye", (side * .034, 1.509, .090), .0105, boots, body,
            scale=(.78, 1.0, .42), subdivisions=1)
        box("eyebrow", (side * .034, 1.535, .087), (.031, .007, .009),
            hair, body, bevel=.003)
    ico("nose", (0, 1.478, .092), .018, skin, body,
        scale=(.68, .95, 1.15), subdivisions=1)
    beam("smile_left", (-.027, 1.444, .089), (0, 1.438, .094), .005,
         skin, body)
    beam("smile_right", (0, 1.438, .094), (.027, 1.444, .089), .005,
         skin, body)
    cylinder("hardhat_brim", (0, 1.594, .002), .136, .018, saffron, body,
             vertices=12)
    loft("hardhat_dome", [(1.601, .116, .112, -.018), (1.652, .11, .105, -.02),
                          (1.687, .067, .068, -.02), (1.70, .045, .046, -.02)],
         saffron, body, sides=10)
    box("hardhat_ridge", (0, 1.678, -.02), (.026, .037, .139),
        saffron, body, bevel=.008)

    # Compact connected cart: four floor-contact casters and two structural trays.
    for x in (-.23, .23):
        for z in (.43, .95):
            cylinder("caster_tyre", (x, .075, z), .075, .044, rubber, cart,
                     axis="X", vertices=16)
            cylinder("caster_hub", (x, .075, z), .036, .048, hub, cart,
                     axis="X", vertices=12)
            cylinder("caster_axle", (x, .075, z), .013, .066, steel, cart,
                     axis="X", vertices=8)
            for dx in (-.031, .031):
                box("caster_fork", (x + dx, .123, z), (.014, .105, .033),
                    steel, cart, bevel=.004)
            cylinder("caster_swivel", (x, .183, z), .029, .035, hub, cart,
                     vertices=10)
    box("cart_lower_tray", (0, .227, .69), (.55, .045, .65), steel, cart, bevel=.009)
    for x in (-.254, .254):
        for z in (.39, .99):
            box("cart_vertical_post", (x, .506, z), (.035, .558, .035),
                steel, cart, bevel=.006)
            box("cart_safety_corner", (x, .592, z), (.046, .068, .046),
                saffron, cart, bevel=.006)
    box("basket_base", (0, .548, .69), (.535, .035, .63), steel, cart, bevel=.006)
    for z in (.39, .99):
        box("basket_lower_panel", (0, .614, z), (.49, .115, .022), teal_dark, cart,
            bevel=.004)
        box("basket_top_rail", (0, .795, z), (.55, .035, .035), steel, cart, bevel=.007)
        for x in (-.17, 0, .17):
            box("basket_end_rail", (x, .711, z), (.021, .166, .024),
                steel, cart, bevel=.003)
    for x in (-.254, .254):
        box("basket_side_panel", (x, .614, .69), (.022, .115, .57),
            teal_dark, cart, bevel=.004)
        box("basket_side_top", (x, .795, .69), (.035, .035, .65),
            steel, cart, bevel=.007)
        for z in (.53, .69, .85):
            box("basket_side_rail", (x, .711, z), (.024, .166, .021),
                steel, cart, bevel=.003)
        beam("handle_upright", (x, .777, .39), (x, .941, .328), .035, steel, cart)
        beam("handle_shoulder", (x, .941, .328), (x * .9, .965, .365),
             .036, steel, cart)
    cylinder("push_handle", (0, .965, .365), .023, .486, rubber, cart,
             axis="X", vertices=12)

    # Two restrained cartons add useful basket scale without hiding the rails.
    box("lower_carton", (0, .342, .72), (.36, .185, .36), carton, cart, bevel=.007)
    box("lower_carton_tape", (0, .436, .72), (.053, .004, .356), tape, cart, bevel=.001)
    box("upper_carton", (-.078, .683, .73), (.285, .235, .33), carton, cart, bevel=.006)
    box("upper_carton_tape", (-.078, .802, .73), (.044, .004, .326), tape, cart, bevel=.001)
    box("small_carton", (.142, .623, .78), (.13, .115, .23), tape, cart, bevel=.005)
    return root


if __name__ == "__main__":
    reset()
    finish("picker-cart", build())
