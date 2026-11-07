"""One metric R04 straight module; shared L08 ports, no autonomous clock."""
import json

from v3_common import ROOT, reset, group, material, box, cylinder, anchor, finish


def build():
    spec = json.loads((ROOT / "assets/v3/specs/conveyor-straight.dimensions.json").read_text())
    root = group("conveyor_straight_root")
    root["reference_id"] = spec["reference_id"]
    root["role"] = "light_conveyor_module"
    root["deck_top_y_m"] = spec["deck_top_y_m"]
    root["usable_width_m"] = spec["usable_width_m"]
    root["source_clock_required"] = True
    teal = material("V3_Conveyor_Petrol", "#2E7376")
    dark = material("V3_Conveyor_Charcoal", "#293D46")
    rubber = material("V3_Conveyor_Belt", "#3B474C", roughness=.95)
    rubber_alt = material("V3_Conveyor_BeltSegment", "#404B4F", roughness=.95)
    brass = material("V3_Conveyor_Marker", "#D3B583")
    bolt = material("V3_Conveyor_Bolt", "#89958F")
    frame = group("conveyor_frame", root)
    belt = group("belt_surface", root)
    belt["source_motion_axis_runtime"] = "+Z"
    belt["period_m"] = .25
    # Side beams sit directly under the deck edges; the taller rails restrain
    # cargo while leaving exactly.82m clear between their inner faces.
    for side in (-1, 1):
        box(f"frame_side_{side}", (side * .385, .82, 0), (.12, .16, .98), teal, frame, .009)
        box(f"guard_rail_{side}", (side * .43, .945, 0), (.04, .11, 1), teal, frame, .006)
        box(f"marker_plate_{side}", (side * .446, .815, .23), (.008, .073, .14), brass, frame, .003)
        for z in (-.35, .35):
            box(f"leg_{side}_{z}", (side * .36, .43, z), (.09, .74, .11), teal, frame, .006)
            box(f"foot_{side}_{z}", (side * .36, .035, z), (.16, .07, .22), dark, frame, .004)
            cylinder(f"mount_bolt_{side}_{z}", (side * .445, .80, z), .012, .010, bolt, frame, axis="X", vertices=8)
    for z in (-.35, .35):
        box(f"cross_member_{z}", (0, .755, z), (.80, .08, .10), dark, frame, .006)
    # A low continuous brace makes the four legs a frame rather than poles.
    for side in (-1, 1):
        box(f"lower_brace_{side}", (side * .36, .24, 0), (.07, .08, .70), dark, frame, .005)
    for i in range(4):
        box(f"belt_panel_{i}", (0, .89, -.375 + i * .25), (.82, .06, .25),
            rubber if i % 2 == 0 else rubber_alt, belt, 0)
    for z in (-.45, .45):
        cylinder(f"end_roller_{z}", (0, .875, z), .045, .80, dark, frame, axis="X", vertices=12)
    # A contained drive housing, connected to a crossmember, adds useful depth
    # without exceeding the declared.90m module footprint.
    box("drive_housing", (.20, .665, -.28), (.22, .16, .20), dark, frame, .012)
    box("drive_cover", (.20, .665, -.385), (.16, .105, .01), teal, frame, .004)
    for name, point in {**spec["connection_ports"], **spec["service_anchors"]}.items():
        anchor(name, point, root, "conveyor_connection" if "port" in name else "support_anchor")
    return root


if __name__ == "__main__":
    # Load the declared dimensions before creating any geometry.
    spec = json.loads((ROOT / "assets/v3/specs/conveyor-straight.dimensions.json").read_text())
    reset()
    report = finish("conveyor-straight", build())
    for edge in ("min", "max"):
        assert max(abs(a-b) for a,b in zip(report["bounds_runtime"][edge], spec["bounds_runtime"][edge])) < 1e-5
    for name, point in {**spec["connection_ports"], **spec["service_anchors"]}.items():
        assert max(abs(a-b) for a,b in zip(report["anchors"][name], point)) < 1e-5
    print("V3_STRAIGHT_DIMENSIONS_AND_PORTS_VERIFIED")
