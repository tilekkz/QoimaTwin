"""Exact 1.4 X .075 Y 1.0 Z empty buffer bed, origin at floor centre."""
from asset_common import reset, material, group, box, cylinder, finish


def _fastener(name, loc, radius, depth, mat, parent, axis="Y", vertices=6):
    obj = cylinder(name, loc, radius, depth, mat, parent, axis=axis, vertices=vertices)
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)
    return obj


def build():
    root = group("buffer_pallet_root")
    root["asset_id"] = "buffer-pallet"
    root["role"] = "buffer_bed"
    root["reference"] = "assets/references/buffer-pallet.png"
    root["size_m"] = [1.4, .075, 1.0]
    root["top_height_m"] = .075
    root["layout_version"] = "qoyma-20x18-v1"
    root["contains_cargo"] = False
    wood = material("buffer_warm_tan_wood", "#B88A56", .88)
    alternate = material("buffer_alternate_wood", "#C89C64", .88)
    endgrain = material("buffer_runner_endgrain", "#A97C47", .90)
    metal = material("buffer_charcoal_rail", "#485157", .65, .35)
    yellow = material("buffer_safety_yellow", "#E7B82F", .70)
    fastener = material("buffer_fastener", "#7A8284", .56, .50)

    # Six small feet and three shallow connected stringers leave actual entry slots.
    for i, x in enumerate((-.56, 0, .56)):
        for j, z in enumerate((-.41, .41)):
            box("low_foot_%d_%d" % (i,j), (x, .0135, z), (.12, .027, .16),
                endgrain, root, bevel=.002)
        box("shallow_longitudinal_runner_%d" % i, (x, .040, 0),
            (.11, .026, .96), endgrain, root, bevel=.002)

    # Eight separate planks: their top surfaces are exactly Y=.075.
    for i in range(8):
        z = -.434 + i*.124
        box("buffer_top_slat_%d" % i, (0, .064, z), (1.36, .022, .112),
            wood if i % 2 else alternate, root, bevel=.002)
        for x in (-.56, .56):
            _fastener("recessed_slat_fastener_%d_%.2f" % (i,x),
                     (x, .074, z), .0045, .002, fastener, root, vertices=6)
    # Reinforcing side rails stay inside the exact 1.4x1.0 footprint.
    for s in (-1, 1):
        box("charcoal_edge_rail_%d" % s, (s*.690, .050, 0),
            (.020, .044, 1.0), metal, root, bevel=.002)
        for j, z in enumerate((-.43, 0, .43)):
            _fastener("rail_bolt_%d_%d" % (s,j), (s*.698, .049, z),
                     .008, .004, fastener, root, axis="X", vertices=8)
        for t in (-1, 1):
            # A thin inset yellow patch keeps overall top exactly at .075.
            box("inset_yellow_corner_%d_%d" % (s,t), (s*.647, .073, t*.446),
                (.086, .004, .087), yellow, root, bevel=.001)
            box("corner_front_guard_%d_%d" % (s,t), (s*.647, .049, t*.491),
                (.086, .043, .018), metal, root, bevel=.002)
    return root


if __name__ == "__main__":
    reset()
    finish("buffer-pallet", build())
