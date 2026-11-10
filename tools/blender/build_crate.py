"""Standard carton with a centred origin and geometric seams/tape/label.

The exact .55 x .45 x .65 envelope puts the lower surface at .675m when
the root is placed at the canonical .9m bin anchor.
"""
from asset_common import reset, material, group, box, finish


def build():
    root = group('crate__MODULE')
    root['origin'] = 'geometric_center'
    root['dimensions_m'] = [.55, .45, .65]
    kraft = material('Carton | kraft tan', '#B98D55', .86)
    lid_mat = material('Carton | warm flap', '#C49B65', .87)
    edge = material('Carton | folded edge', '#A67A45', .88)
    seam = material('Carton | seam recess', '#795C3B', .91)
    tape = material('Carton | paper tape', '#D4B37D', .81)
    tape_fold = material('Carton | folded tape end', '#C8A66D', .84)
    ivory = material('Carton | blank label', '#DFDCC6', .91)

    # Bottom folded rim establishes the exact width/depth and bottom surface.
    box('Carton_body', (0, -.0075, 0), (.548, .421, .648), kraft, root, .006)
    box('Folded_bottom_rim', (0, -.218, 0), (.55, .014, .65), edge, root, .004)
    # Recesses are geometric, so no raster or procedural textures are needed.
    for sx in (-1, 1):
        box('Bottom_seam_X_' + str(sx), (sx * .2743, -.203, 0),
            (.0008, .0022, .625), seam, root, 0)
    for sz in (-1, 1):
        box('Bottom_seam_Z_' + str(sz), (0, -.203, sz * .3243),
            (.525, .0022, .0008), seam, root, 0)
        box('Lid_recess_Z_' + str(sz), (0, .1995, sz * .3243),
            (.523, .0025, .0008), seam, root, 0)

    # Two separate closed top flaps with a readable centre joint under tape.
    for sx in (-1, 1):
        box('Closed_top_flap_' + str(sx), (sx * .138, .213, 0),
            (.271, .02, .646), lid_mat, root, .003)
        box('Lid_recess_X_' + str(sx), (sx * .2743, .1995, 0),
            (.0008, .0025, .624), seam, root, 0)
    box('Centre_lid_joint', (0, .2215, 0), (.003, .002, .637), seam, root, 0)
    # Single paper tape strip wraps coherently from the lid over both short ends.
    box('Paper_tape_top', (0, .224, 0), (.079, .002, .642), tape, root, .0005)
    for sz in (-1, 1):
        box('Paper_tape_wrap_' + str(sz), (0, .167, sz * .324),
            (.079, .113, .002), tape, root, .001)
        box('Paper_tape_fold_' + str(sz), (0, .1145, sz * .324),
            (.074, .008, .002), tape_fold, root, .001)

    # A single restrained packaging fold and blank label face the aisle (+X).
    box('Side_fold_recess', (.2743, -.004, -.265), (.0008, .386, .002), edge, root, 0)
    box('Label_inset_border', (.2743, .050, -.069), (.0010, .105, .163), edge, root, .0002)
    box('Blank_shipping_label', (.2747, .050, -.069), (.0006, .092, .150), ivory, root, .0001)
    return root


if __name__ == '__main__':
    reset()
    finish('crate', build())

