"""Contract-sized miniature rack, guided by rack-bay-reference.png.

Coordinate arguments use runtime metres (Y up). Access is +X toward the
aisle; the opposite -X face carries X bracing. Only the .675m deck is active.
"""
from asset_common import reset, material, group, box, beam, ico, finish


def build():
    root = group('rackbay__MODULE')
    root['active_shelf_top_m'] = .675
    root['active_addresses'] = 1
    root['access_face'] = '+X'
    steel = material('Rack | matte charcoal steel', '#34454D', .72, .15)
    beam_mat = material('Rack | blue teal powdercoat', '#376875', .72, .12)
    birch = material('Rack | birch deck', '#C6AB7D', .81)
    edge = material('Rack | birch exposed edge', '#AD8F61', .82)
    saffron = material('Rack | saffron protectors', '#C79D38', .69, .08)
    recess = material('Rack | mounting recess', '#1C2930', .85)
    metal = material('Rack | bolt heads', '#94A3A5', .55, .4)
    label = material('Rack | blank label', '#D9DDCF', .86)

    # Footplates determine exact .9 x 1.5 footprint, with their base at Y=0.
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * .405, sz * .695
            tag = ('left' if sx < 0 else 'aisle') + ('_rear' if sz < 0 else '_front')
            box('Footplate_' + tag, (x, .0175, z), (.09, .035, .11), steel, root, .005)
            box('Upright_' + tag, (x, 1.3175, z), (.052, 2.565, .056), steel, root, .003)
            box('Safety_guard_' + tag, (x, .125, z), (.072, .18, .082), saffron, root, .004)
            box('Guard_cap_' + tag, (x, .218, z), (.075, .014, .084), steel, root, .002)
            # Dark shallow recess marks suggest punched upright slots geometrically.
            for index in range(12):
                h = .325 + index * .184
                box('Upright_recess_' + tag + '_' + str(index), (x + .0265, h, z),
                    (.001, .027, .012), recess, root, 0)
            for h in (.077, .174):
                ico('Guard_fastener_' + tag, (x + .037, h, z), .007, metal, root,
                    scale=(.32, 1, 1), subdivisions=1)

    for level, top in enumerate((.675, 1.52, 2.38), start=1):
        # All birch deck top surfaces are exact, especially the contract active shelf.
        box('Birch_deck_' + str(level), (0, top - .019, 0), (.806, .038, 1.388), birch, root, .004)
        # Restrained exposed long edge separates wood thickness from steel support.
        for sx in (-1, 1):
            box('Deck_edge_' + str(level) + '_' + str(sx), (sx * .395, top - .022, 0),
                (.012, .025, 1.348), edge, root, .002)
            box('Longitudinal_beam_' + str(level) + '_' + str(sx),
                (sx * .405, top - .068, 0), (.052, .09, 1.388), beam_mat, root, .004)
        for sz in (-1, 1):
            box('End_beam_' + str(level) + '_' + str(sz), (0, top - .068, sz * .695),
                (.806, .09, .056), beam_mat, root, .004)
            for sx in (-1, 1):
                # Dimensional connection plate and deliberately low-poly bolt head.
                box('Beam_bracket_' + str(level) + '_' + str(sx) + '_' + str(sz),
                    (sx * .433, top - .057, sz * .695),
                    (.014, .115, .069), beam_mat, root, .002)
                ico('Beam_bolt_' + str(level) + '_' + str(sx) + '_' + str(sz),
                    (sx * .441, top - .055, sz * .695), .008, metal, root,
                    scale=(.32, 1, 1), subdivisions=1)

    # Four perimeter top ties finish the frame without introducing a fourth deck.
    for sx in (-1, 1):
        box('Top_long_tie_' + str(sx), (sx * .405, 2.566, 0),
            (.052, .068, 1.388), beam_mat, root, .003)
    for sz in (-1, 1):
        box('Top_end_tie_' + str(sz), (0, 2.566, sz * .695),
            (.806, .068, .056), beam_mat, root, .003)

    # Structural bracing stays behind the shelf and on the two short ends.
    for start, end in (
        ((-.412, .285, -.667), (-.412, 2.36, .667)),
        ((-.421, .285, .667), (-.421, 2.36, -.667)),
    ):
        beam('Rear_X_brace', start, end, .031, beam_mat, root)
    for sz in (-1, 1):
        beam('End_diagonal_' + str(sz), (-.378, .34, sz * .695),
             (.378, 2.33, sz * .695), .027, beam_mat, root)

    # One address holder on the active shelf, toward the aisle; it has no SKU ID.
    box('Active_label_frame', (.435, .605, 0), (.022, .077, .245), steel, root, .004)
    box('Active_label_insert', (.447, .605, 0), (.004, .052, .209), label, root, .002)
    return root


if __name__ == '__main__':
    reset()
    finish('rack-bay', build())

