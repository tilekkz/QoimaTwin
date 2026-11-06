"""Opaque IBC tank, geometric steel cage, red cap and wooden pallet."""
import math
from asset_common import reset, material, group, box, cylinder, beam, finish


def _rod(name, loc, radius, depth, mat, parent, axis="Y", vertices=8):
    # Thin cage bars are already faceted round rods; tiny edge bevels add no
    # visible depth at warehouse scale and would triple their triangle count.
    obj = cylinder(name, loc, radius, depth, mat, parent, axis=axis, vertices=vertices)
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)
    return obj


def build():
    root = group("ibc_tote_root")
    root["asset_id"] = "ibc-tote"
    root["role"] = "static_set_dressing"
    root["front_axis"] = "+Z"
    root["reference"] = "assets/references/ibc-tote.png"
    root["nominal_size_m"] = [1.1, 1.2, 1.0]
    plastic = material("ibc_off_white_plastic", "#DEDCD0", .76)
    plastic_rib = material("ibc_molded_ribs", "#D4D2C6", .77)
    cage = material("ibc_charcoal_cage", "#606B70", .56, .50)
    joint = material("ibc_cage_welds", "#798388", .57, .50)
    red = material("ibc_red_cap_and_handle", "#CE3D30", .62)
    wood = material("ibc_pallet_tan", "#BA8950", .87)
    wood_light = material("ibc_pallet_alternate", "#CDA16A", .87)
    wood_end = material("ibc_pallet_end_grain", "#A77B46", .90)
    black = material("ibc_valve_polymer", "#323A3E", .75)
    plate = material("ibc_blank_id_plate", "#C4C7C4", .70, .12)

    # A real slatted pallet: three bottom runners, nine blocks, crosswise top boards.
    for i, x in enumerate((-.45, 0, .45)):
        box("pallet_bottom_runner_%d" % i, (x, .013, 0), (.145, .026, 1.0),
            wood_end, root, bevel=.005)
        for j, z in enumerate((-.415, 0, .415)):
            box("pallet_foot_%d_%d" % (i,j), (x, .063, z), (.145, .074, .16),
                wood, root, bevel=.005)
        box("pallet_upper_stringer_%d" % i, (x, .113, 0), (.145, .026, 1.0),
            wood_end, root, bevel=.004)
    for i in range(7):
        z = -.438 + i*.146
        box("pallet_deck_slat_%d" % i, (0, .141, z), (1.1, .030, .124),
            wood if i % 2 else wood_light, root, bevel=.005)
        for x in (-.45, .45):
            cylinder("pallet_nail_%d_%.1f" % (i,x), (x, .1565, z),
                     .006, .002, cage, root, vertices=6)

    # Opaque blow-moulded tank with soft low-poly corners and shallow top ribs.
    box("offwhite_tank", (0, .641, -.018), (.978, .936, .804),
        plastic, root, bevel=.058)
    for i, x in enumerate((-.32, -.16, .16, .32)):
        box("tank_top_moulded_rib_%d" % i, (x, 1.112, -.018),
            (.016, .010, .69), plastic_rib, root, bevel=.004)
    for i, z in enumerate((-.26, .22)):
        box("tank_top_cross_moulded_rib_%d" % i, (0, 1.112, z),
            (.85, .010, .015), plastic_rib, root, bevel=.004)

    # Steel cage is actual 3D rods with visible separation from the tank.
    # Every horizontal belt wraps continuously around all four sides.
    for j, y in enumerate((.185, .405, .635, .865, 1.125)):
        radius = .021 if j in (0,4) else .011
        for s in (-1, 1):
            make_rod = cylinder if j in (0,4) else _rod
            make_rod("cage_belt_%d_frontrear_%d" % (j,s),
                     (0, y, s*.433-.018), radius, 1.03, cage, root,
                     axis="X", vertices=8)
            make_rod("cage_belt_%d_side_%d" % (j,s),
                     (s*.515, y, -.018), radius, .866, cage, root,
                     axis="Z", vertices=8)
        for s in (-1, 1):
            for t in (-1, 1):
                _rod("cage_belt_joint_%d_%d_%d" % (j,s,t),
                         (s*.515, y, t*.433-.018), radius*1.08, .044,
                         cage, root, vertices=8)
    for s in (-1, 1):
        for t in (-1, 1):
            cylinder("cage_corner_post_%d_%d" % (s,t),
                     (s*.515, .655, t*.433-.018), .019, .94,
                     cage, root, vertices=8)
    for i, x in enumerate((-.34, -.17, 0, .17, .34)):
        for s in (-1, 1):
            _rod("cage_vertical_frontrear_%d_%d" % (i,s),
                     (x, .655, s*.433-.018), .010, .94,
                     cage, root, vertices=8)
    for i, z in enumerate((-.29, -.12, .05, .22)):
        for s in (-1, 1):
            _rod("cage_vertical_side_%d_%d" % (i,s),
                     (s*.515, .655, z), .010, .94,
                     cage, root, vertices=8)
    # Reinforced lower saddle connects cage to pallet.
    for s in (-1, 1):
        box("tank_saddle_%d" % s, (s*.43, .171, -.018),
            (.07, .026, .84), cage, root, bevel=.006)

    # Large red threaded screw cap with distinct grip tabs.
    cylinder("tank_cap_neck", (0, 1.126, -.018), .116, .032,
             plastic_rib, root, vertices=20)
    cylinder("red_screw_cap", (0, 1.171, -.018), .134, .056,
             red, root, vertices=20)
    for i in range(16):
        a = i*math.tau/16
        rib = box("red_cap_grip_%02d" % i,
                  (.133*math.cos(a), 1.173, -.018+.133*math.sin(a)),
                  (.018, .051, .025), red, root, bevel=.003)
        rib.rotation_euler.z = -a
    cylinder("cap_top_inner_disk", (0, 1.199, -.018), .111, .002,
             red, root, vertices=20)

    # Front low discharge valve: connected outlet, red lever and white closure.
    cylinder("discharge_neck", (0, .252, .411), .050, .10,
             plastic_rib, root, axis="Z", vertices=12)
    box("discharge_valve_body", (0, .252, .457), (.106, .105, .078),
        black, root, bevel=.019)
    cylinder("discharge_spout", (0, .252, .484), .041, .029,
             black, root, axis="Z", vertices=12)
    cylinder("discharge_white_closure", (0, .252, .497), .039, .006,
             plastic, root, axis="Z", vertices=12)
    cylinder("red_valve_handle_pivot", (0, .316, .457), .024, .025,
             red, root, vertices=10)
    box("red_valve_handle", (.054, .33, .457), (.126, .018, .024),
        red, root, bevel=.006)
    # Small blank clipped plate, never baked business identifiers.
    box("front_blank_id_plate", (0, .855, .430), (.29, .17, .015),
        plate, root, bevel=.008)
    for x in (-.105, .105):
        box("id_plate_clip_%.2f" % x, (x, .943, .428), (.025, .045, .025),
            joint, root, bevel=.004)
    return root


if __name__ == "__main__":
    reset()
    finish("ibc-tote", build())
