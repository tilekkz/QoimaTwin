"""Grounded 2.2 x 1.0 m packing station, based on its generated reference sheet."""
import math
import bpy

from asset_common import reset, material, group, box, cylinder, beam, finish


def build():
    root = group("pack_station__PACK")
    root["asset_id"] = "packing-station"
    root["role"] = "packing_station"
    root["layout_version"] = "qoyma-20x18-v1"
    root["tabletop_top_m"] = .85
    root["origin_description"] = "floor at centre of table footprint"
    steel = material("Steel_Charcoal", "#35434C", roughness=.72, metallic=.15)
    casing = material("Equipment_Charcoal", "#46515C", roughness=.7)
    rubber = material("Rubber_Dark", "#252C30", roughness=.9)
    birch = material("Birch_Warm", "#C7A16E", roughness=.77)
    edge = material("Birch_Edge", "#B98F5A", roughness=.79)
    carton = material("Carton_Tan", "#BB905B", roughness=.88)
    inside = material("Carton_Inside", "#CAA775", roughness=.9)
    tape = material("Carton_Tape", "#D6B884", roughness=.86)
    saffron = material("Safety_Saffron", "#D8A744", roughness=.7)
    paper = material("Label_Paper", "#E2E3D6", roughness=.86)
    screen = material("Screen_Teal", "#28565D", roughness=.62)
    hardware = material("Hardware_Grey", "#748187", roughness=.6, metallic=.3)

    # All legs and feet touch Y=0. Tabletop has its prescribed top at .85m.
    for x in (-.985, .985):
        for z in (-.405, .405):
            box("table_foot", (x, .0175, z), (.145, .035, .14), rubber, root, bevel=.008)
            box("table_leg", (x, .409, z), (.085, .753, .085), steel, root, bevel=.007)
            box("foot_collar", (x, .062, z), (.105, .045, .10), casing, root, bevel=.004)
    for z in (-.405, .405):
        box("long_apron", (0, .755, z), (2.03, .10, .065), steel, root, bevel=.005)
        box("shelf_long_support", (0, .198, z), (2.03, .065, .055), steel, root, bevel=.004)
    for x in (-.985, .985):
        box("end_apron", (x, .755, 0), (.065, .10, .81), steel, root, bevel=.005)
        box("shelf_end_support", (x, .198, 0), (.055, .065, .81), steel, root, bevel=.004)
    box("lower_shelf", (0, .2325, -.04), (1.96, .025, .70), steel, root, bevel=.006)
    box("tabletop_edge", (0, .81, 0), (2.2, .08, 1.0), edge, root, bevel=.018)
    box("tabletop_surface", (0, .842, 0), (2.185, .016, .985), birch, root, bevel=.014)
    # Fasteners are subtle actual geometry, anchored on apron faces.
    for x in (-.985, .985):
        for z in (-.44, .44):
            cylinder("apron_bolt", (x, .765, z), .011, .008, hardware, root,
                     axis="Z", vertices=8)
    for i in range(6):
        y = .254 + i * .0125
        box("flat_carton_bundle", (-.51, y, -.06), (.72, .009, .48), carton, root, bevel=.003)
    box("bundle_strap_top", (-.50, .326, -.06), (.04, .008, .485), tape, root, bevel=.001)
    box("bundle_strap_front", (-.50, .289, .184), (.04, .078, .007), tape, root, bevel=.001)
    box("bundle_strap_rear", (-.50, .289, -.304), (.04, .078, .007), tape, root, bevel=.001)

    # Monitor at rear-left, display facing the operator (+Z).
    box("monitor_base", (-.72, .87, -.26), (.34, .04, .22), casing, root, bevel=.012)
    box("monitor_stem", (-.72, 1.035, -.30), (.061, .29, .055), casing, root, bevel=.009)
    box("monitor_body", (-.72, 1.24, -.30), (.49, .36, .065), casing, root, bevel=.014)
    box("monitor_screen", (-.72, 1.244, -.264), (.441, .308, .009), screen, root, bevel=.005)
    box("monitor_chin", (-.72, 1.071, -.263), (.43, .02, .009), casing, root, bevel=.003)
    cylinder("monitor_status", (-.507, 1.081, -.254), .004, .002, saffron, root,
             axis="Z", vertices=8)
    box("monitor_rear_vent", (-.72, 1.23, -.335), (.20, .10, .008), steel, root, bevel=.004)

    # Scanner has an attached cradle, angled grip and head, no loose cables.
    box("scanner_cradle", (-.315, .871, -.245), (.17, .042, .17), casing, root, bevel=.012)
    beam("scanner_handle", (-.315, .894, -.27), (-.315, 1.055, -.245), .055, steel, root)
    box("scanner_yellow_grip", (-.315, .982, -.214), (.047, .095, .018),
        saffron, root, bevel=.007)
    box("scanner_head", (-.315, 1.084, -.236), (.137, .078, .10), casing, root, bevel=.015)
    box("scanner_lens", (-.315, 1.081, -.181), (.102, .041, .009), rubber, root, bevel=.008)

    # A modest open carton: real base, four walls and four attached flaps.
    cx, cz = .23, .005
    width, depth, height, thick = .48, .43, .30, .012
    bottom = .85
    box("carton_bottom", (cx, bottom + thick / 2, cz), (width, thick, depth),
        inside, root, bevel=.002)
    for x in (cx - width / 2 + thick / 2, cx + width / 2 - thick / 2):
        box("carton_side_wall", (x, bottom + height / 2, cz),
            (thick, height, depth), carton, root, bevel=.002)
    for z in (cz - depth / 2 + thick / 2, cz + depth / 2 - thick / 2):
        box("carton_end_wall", (cx, bottom + height / 2, z),
            (width - 2 * thick, height, thick), carton, root, bevel=.002)
    # Flaps extend outwards 35 degrees above horizontal, attached at wall tops.
    flap_len = .135
    angle = math.radians(35)
    for side in (-1, 1):
        z = cz + side * (depth / 2 + math.cos(angle) * flap_len / 2)
        obj = box("carton_end_flap", (cx, bottom + height + math.sin(angle) * flap_len / 2, z),
                  (width, thick, flap_len), inside, root, bevel=.002)
        obj.rotation_euler.x = -side * angle
        x = cx + side * (width / 2 + math.cos(angle) * flap_len / 2)
        obj = box("carton_side_flap", (x, bottom + height + math.sin(angle) * flap_len / 2, cz),
                  (flap_len, thick, depth - .03), carton, root, bevel=.002)
        # Raising the outward edge is negative Blender Y rotation on +X.
        obj.rotation_euler.y = -side * angle

    # Label printer on its own solid base, label emerging into an attached tray.
    px, pz = .805, -.245
    box("printer_foot", (px, .864, pz), (.31, .028, .31), rubber, root, bevel=.009)
    box("printer_body", (px, .985, pz), (.32, .23, .30), casing, root, bevel=.018)
    box("printer_top_lid", (px, 1.108, pz - .022), (.31, .038, .255),
        casing, root, bevel=.014)
    box("printer_slot", (px, .97, pz + .154), (.22, .048, .008), rubber, root, bevel=.004)
    box("printer_label_tray", (px, .871, pz + .242), (.234, .024, .19),
        steel, root, bevel=.006)
    label = box("emerging_label", (px, .926, pz + .205), (.18, .006, .12),
                paper, root, bevel=.002)
    label.rotation_euler.x = math.radians(47)
    box("label_on_tray", (px, .888, pz + .285), (.18, .004, .078), paper, root, bevel=.002)
    box("printer_button", (px + .103, 1.055, pz + .154), (.035, .025, .008),
        saffron, root, bevel=.004)

    # Compact tape dispenser, supported roller and blade housing.
    tx, tz = -.30, .30
    box("tape_dispenser_base", (tx, .873, tz), (.20, .046, .13), casing, root, bevel=.009)
    cylinder("tape_roll", (tx - .025, .956, tz), .066, .059, tape, root,
             axis="X", vertices=16)
    cylinder("tape_roll_core", (tx - .025, .956, tz), .026, .062, rubber, root,
             axis="X", vertices=12)
    for x in (tx - .064, tx + .014):
        box("tape_roll_support", (x, .923, tz), (.014, .065, .058),
            casing, root, bevel=.004)
    box("tape_blade_housing", (tx + .068, .916, tz), (.035, .09, .127),
        saffron, root, bevel=.005)
    box("tape_blade", (tx + .088, .961, tz), (.013, .009, .113),
        hardware, root, bevel=.002)
    return root


if __name__ == "__main__":
    reset()
    finish("packing-station", build())
