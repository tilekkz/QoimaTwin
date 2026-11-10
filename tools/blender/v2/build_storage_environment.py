"""V2 storage architecture and rack LODs; no v1 output is modified.

All construction inputs are metres in runtime X/Y/Z. The shell contains no
actors, racks, cargo, conveyors or simulated resources. Rack bins are metadata
anchors, with three actual shelf decks at the canonical heights.
"""
import json
import math
import sys

from v2_common import ROOT, VERSION, xyz, reset, material, group, box, beam, cylinder, ico, finish


DECK_TOPS = (.225, 2.025, 3.825)
BIN_CENTRES = (.45, 2.25, 4.05)
RACK_HEIGHT = 4.65
AUXILIARY_TOPS = (1.40, 3.20)


def _rack_metadata(root, lod):
    root['role'] = 'rack_module'
    root['lod'] = lod
    root['origin'] = 'floor_center'
    root['dimensions_m'] = [.9, RACK_HEIGHT, 1.5]
    root['physical_height_m'] = RACK_HEIGHT
    root['logical_envelope_m'] = [.9, 5.4, 1.5]
    root['logical_envelope_is_not_mesh_bounds'] = True
    root['deck_tops_y'] = list(DECK_TOPS)
    root['bin_centres_y'] = list(BIN_CENTRES)
    root['access_face'] = '+X'
    root['auxiliary_shelf_tops_y'] = list(AUXILIARY_TOPS)
    root['auxiliary_shelves_visual_only'] = True
    root['logical_address_count'] = 3
    root['max_stock_height_below_auxiliary_m'] = 1.14
    for index, height in enumerate(BIN_CENTRES, 1):
        anchor = group('anchor_bin__L%02d' % index)
        anchor.parent = root
        anchor.location = xyz((0, height, 0))
        anchor['role'] = 'pickface_anchor' if index == 1 else 'reserve_anchor'
        anchor['level'] = index


def _plain_beam(name, start, end, width, mat, parent):
    left, right = xyz(start), xyz(end)
    delta = right - left
    obj = box(name, (0, 0, 0), (width, delta.length, width), mat, parent, 0)
    obj.location = (left + right) * .5
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = delta.to_track_quat('Z', 'Y')
    return obj


def build_rack_high():
    root = group('rack_high__MODULE')
    _rack_metadata(root, 'high')
    steel = material('V2 rack | charcoal channel steel', '#30464D', .75, .16)
    orange = material('V2 rack | warm orange crossbeams', '#B86C3D', .78, .10)
    birch = material('V2 rack | supported birch decks', '#C3AD88', .86)
    saffron = material('V2 rack | safety guards', '#C4A14A', .8)
    recess = material('V2 rack | punched recess', '#202D33', .9)
    bolt = material('V2 rack | fasteners', '#98A5A6', .62, .35)
    label = material('V2 rack | blank labels', '#D9DCCB', .88)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * .4, sz * .695
            tag = '%s_%s' % (sx, sz)
            box('Footplate_' + tag, (x, .02, z), (.10, .04, .11), steel, root, .004)
            box('Channel_upright_web_' + tag, (x, 2.345, z), (.034, 4.61, .086), steel, root, .003)
            for flange in (-1, 1):
                box('Channel_upright_return_' + tag, (x, 2.345, z + flange*.034),
                    (.086, 4.61, .018), steel, root, .002)
            box('Saffron_guard_' + tag, (x, .22, z), (.10, .36, .10), saffron, root, .005)
            box('Guard_front_plate_' + tag, (x + sx*.046, .22, z),
                (.006, .29, .076), orange, root, .001)
            for index in range(10):
                box('Punched_recess_' + tag + '_' + str(index),
                    (x + sx*.0435, .56 + index * .39, z), (.001, .038, .016), recess, root, 0)
            for height in (.10, .32):
                ico('Guard_bolt_' + tag, (x + sx*.047, height, z), .007, bolt,
                    root, scale=(.3, 1, 1), subdivisions=1)

    for index, top in enumerate((*DECK_TOPS, *AUXILIARY_TOPS), 1):
        addressed = index <= 3
        thickness = .04 if addressed else .018
        prefix = 'Real_addressed_deck_L' if addressed else 'Visual_only_auxiliary_deck_'
        deck = box(prefix + str(index), (0, top - thickness*.5, 0),
                   (.78, thickness, 1.35), birch, root, .003 if addressed else .001)
        deck['visual_only'] = not addressed
        for sx in (-1, 1):
            box('Orange_long_support_%s_%s' % (index, sx),
                (sx*.4, top-(.086 if addressed else .04), 0),
                (.09, .16 if addressed else .065, 1.39), orange, root, .004)
        for sz in (-1, 1):
            box('End_support_%s_%s' % (index, sz),
                (0, top-(.086 if addressed else .04), sz*.695),
                (.78, .16 if addressed else .065, .075), orange, root, .003)
        if addressed:
            for sx in (-1, 1):
                for sz in (-1, 1):
                    box('Connector_plate_L%s_%s_%s' % (index, sx, sz),
                        (sx*.445, top-.086, sz*.695), (.006, .19, .09), steel, root, .001)
                    ico('Connector_bolt_L%s_%s_%s' % (index, sx, sz),
                        (sx*.449, top-.086, sz*.695), .005, bolt, root,
                        scale=(.15, 1, 1), subdivisions=1)
            box('Address_label_rail_L' + str(index), (.443, top-.088, 0),
                (.01, .095, .38), steel, root, .001)
            box('Address_label_blank_L' + str(index), (.449, top-.088, 0),
                (.002, .059, .26), label, root, .0005)

    for sx in (-1, 1):
        box('Lowered_top_long_tie_' + str(sx), (sx*.4, 4.59, 0),
            (.09, .12, 1.39), orange, root, .004)
    for sz in (-1, 1):
        box('Lowered_top_end_tie_' + str(sz), (0, 4.59, sz*.695),
            (.78, .12, .075), orange, root, .004)
    # Each rack section has its own short brace; no five-metre diagonal.
    for index, (bottom, top) in enumerate(((.43, 1.89), (2.19, 3.69), (3.99, 4.50))):
        direction = 1 if index % 2 == 0 else -1
        beam('Rear_section_brace_' + str(index), (-.4, bottom, -.64*direction),
             (-.4, top, .64*direction), .038, steel, root)
        for sz in (-1, 1):
            beam('End_section_brace_%s_%s' % (index, sz), (-.35*direction, bottom, sz*.695),
                 (.35*direction, top, sz*.695), .032, steel, root)
    return root


def build_rack_low():
    root = group('rack_low__MODULE')
    _rack_metadata(root, 'low')
    steel = material('V2 rack LOD | charcoal', '#30464D', .82, .08)
    orange = material('V2 rack LOD | orange beams', '#B86C3D', .82)
    birch = material('V2 rack LOD | birch', '#C3AD88', .88)
    # Retain the compact physical silhouette, five deck masses and thick orange
    # horizontal structure. Fasteners/channels are omitted at this distance.
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx*.4, sz*.695
            tag = '%s_%s' % (sx, sz)
            box('LOD_foot_' + tag, (x, .02, z), (.10, .04, .11), steel, root, 0)
            box('LOD_post_' + tag, (x, 2.345, z), (.086, 4.61, .086), steel, root, 0)
            if sx == 1:
                box('LOD_guard_' + tag, (x, .22, z), (.10, .36, .10), orange, root, 0)
    for index, top in enumerate((*DECK_TOPS, *AUXILIARY_TOPS), 1):
        addressed = index <= 3
        thickness = .04 if addressed else .018
        deck = box('LOD_deck_' + str(index), (0, top-thickness*.5, 0),
                   (.78, thickness, 1.35), birch, root, 0)
        deck['visual_only'] = not addressed
        for sx in (-1, 1):
            box('LOD_long_support_L%s_%s' % (index, sx),
                (sx*.4, top-(.086 if addressed else .04), 0),
                (.09, .16 if addressed else .065, 1.39), orange, root, 0)
    for sz in (-1, 1):
        box('LOD_top_end_tie_' + str(sz), (0, 4.59, sz*.695),
            (.78, .12, .075), orange, root, 0)
    for sx in (-1, 1):
        box('LOD_top_long_tie_' + str(sx), (sx*.4, 4.59, 0),
            (.09, .12, 1.39), orange, root, 0)
    for index, (bottom, top) in enumerate(((.43, 1.89), (2.19, 3.69), (3.99, 4.50))):
        direction = 1 if index % 2 == 0 else -1
        for sz in (-1, 1):
            _plain_beam('LOD_short_brace_%s_%s' % (index, sz),
                        (-.35*direction, bottom, sz*.695), (.35*direction, top, sz*.695),
                        .032, steel, root)
    return root


def _column(root, x, z, steel, concrete):
    box('Column_base', (x, .07, z), (.66, .14, .66), concrete, root, .018)
    box('Column_pedestal', (x, .24, z), (.56, .22, .56), concrete, root, .014)
    box('Column_steel_baseplate', (x, .36, z), (.53, .045, .53), steel, root, .006)
    box('Column_I_web', (x, 4.08, z), (.10, 7.84, .42), steel, root, .005)
    for offset in (-.185, .185):
        box('Column_I_flange', (x, 4.08, z + offset), (.42, 7.84, .05), steel, root, .005)
    box('Column_cap_plate', (x, 7.97, z), (.49, .06, .49), steel, root, .004)
    for height in (1.1, 6.1):
        box('Column_flange_splice_plate', (x, height, z-.216), (.31, .25, .022), steel, root, .003)


def _rear_panel(root, x, width, z, steel, wall, glass):
    box('Rear_corrugated_panel', (x, 3.15, z), (width, 5.9, .15), wall, root, .006)
    # Corrugation is dimensional but deliberately coarse, confined to perimeter.
    rib_count = max(1, int(width / .75))
    for index in range(rib_count):
        rib_x = x - width * .5 + (index + .5) * width / rib_count
        box('Rear_panel_rib', (rib_x, 3.15, z - .095), (.045, 5.76, .045), wall, root, 0)
    box('Clerestory_glazing', (x, 6.79, z), (width, 1.18, .065), glass, root, 0)
    for height in (6.15, 6.79, 7.43):
        box('Clerestory_horizontal_frame', (x, height, z - .04), (width, .065, .10), steel, root, .003)
    for index in range(1, 5):
        box('Clerestory_mullion', (x - width * .5 + width * index / 5, 6.79, z - .04),
            (.06, 1.23, .10), steel, root, 0)
    box('High_wall_cap_panel', (x, 7.72, z), (width, .56, .15), wall, root, .005)
    box('Upper_perimeter_girt', (x, 7.96, z - .045), (width, .08, .17), steel, root, .003)
    box('Rear_wall_raised_plinth', (x, .22, z-.08), (width, .44, .28), wall, root, .01)
    box('Rear_wall_plinth_cap', (x, .45, z-.09), (width, .045, .32), steel, root, .003)


def _zone_line(root, start, end, mat, width=.085):
    left, right = xyz(start), xyz(end)
    delta = right - left
    # Local Z is the line's long direction; local Blender Y is its thin up axis
    # before the orientation, so construct a plane through runtime coordinate boxes.
    if abs(end[0] - start[0]) >= abs(end[2] - start[2]):
        return box('Safety_floor_line', ((start[0] + end[0]) / 2, .004, start[2]),
                   (abs(end[0] - start[0]), .007, width), mat, root, 0)
    return box('Safety_floor_line', (start[0], .004, (start[2] + end[2]) / 2),
               (width, .007, abs(end[2] - start[2])), mat, root, 0)


def build_environment_shell():
    layout = json.loads((ROOT / 'contracts' / 'layout.example.json').read_text(encoding='utf-8'))
    if layout['layout_version'] != VERSION or layout['bounds']['max'] != [72, 8, 48]:
        raise ValueError('The storage shell requires canonical qoima-72x48-v2.')
    if len(layout['racks']) != 288 or len(layout['slots']) != 864:
        raise ValueError('Unexpected v2 storage geometry counts.')
    root = group('environment_shell__V2')
    root['role'] = 'static_architecture_shell'
    root['floor_dimensions_m'] = [72, 48]
    root['clear_height_m'] = 8.
    root['excludes'] = 'racks,cargo,people,conveyors,simulation'
    root['dock_openings'] = json.dumps([
        {'zone': 'receiving', 'pos': [.35, 0, 20], 'heading_deg': 90},
        {'zone': 'receiving', 'pos': [.35, 0, 36], 'heading_deg': 90},
        {'zone': 'shipping', 'pos': [71.65, 0, 3], 'heading_deg': -90},
        {'zone': 'shipping', 'pos': [71.65, 0, 9], 'heading_deg': -90},
    ])
    concrete = material('V2 shell | cool concrete', '#AAB3B8', .94)
    seam = material('V2 shell | slab joints', '#8C989E', .96)
    slab_tones = [material('V2 shell | quiet slab tone '+str(index), color, .94)
                  for index, color in enumerate(('#A9B2B7', '#AEB7BB', '#A6B0B5'))]
    steel = material('V2 shell | charcoal steel', '#354750', .78, .16)
    wall = material('V2 shell | slate wall panels', '#687C86', .84, .06)
    glass = material('V2 shell | pale blue clerestory', '#9CBCC6', .45, .12)
    paint = material('V2 shell | muted saffron zones', '#C1A34C', .9)
    curb = material('V2 shell | perimeter curb', '#89969D', .94)

    box('floor__FLOOR_V2', (36, -.10, 24), (72, .20, 48), concrete, root, .018)
    for ix in range(12):
        for iz in range(8):
            # Quiet construction-scale variation, never a noisy texture.
            box('Concrete_slab_tone_%s_%s' % (ix, iz),
                (3+ix*6, .0004, 3+iz*6), (5.974, .0008, 5.974),
                slab_tones[(ix*7+iz*3+ix//3+iz//2)%3], root, 0)
    for x in range(6, 72, 6):
        box('Concrete_slab_joint_X', (x, .0015, 24), (.018, .002, 47.5), seam, root, 0)
    for z in range(6, 48, 6):
        box('Concrete_slab_joint_Z', (36, .0015, z), (71.5, .002, .018), seam, root, 0)

    rear_columns = [.35, 9.25, 18.15, 27.05, 35.95, 44.85, 53.75, 62.65, 71.65]
    for x in rear_columns:
        _column(root, x, 47.65, steel, curb)
    for x, positions in ((.35, [.35, 8, 14, 24, 30, 42]),
                         (71.65, [.35, 6, 12, 20, 28, 36])):
        for z in positions:
            _column(root, x, z, steel, curb)
    for left, right in zip(rear_columns, rear_columns[1:]):
        _rear_panel(root, (left + right) / 2, right - left - .44, 47.82, steel, wall, glass)

    # Low side parapets leave the entire working floor visible from overhead.
    # Gaps align with the four loading openings, all within peripheral zones.
    for x, segments in (
        (.18, [(.2, 17.6), (22.4, 33.6), (38.4, 47.6)]),
        (71.82, [(.2, .6), (5.4, 6.6), (11.4, 47.6)]),
    ):
        for start, end in segments:
            if end <= start:
                continue
            box('Cutaway_side_parapet', (x, .40, (start + end) / 2),
                (.22, .8, end - start), wall, root, .008)
            box('Side_parapet_cap', (x, .82, (start + end) / 2),
                (.27, .05, end - start), steel, root, .003)
            box('Side_parapet_stepped_plinth', (x, .12, (start+end)/2),
                (.34, .24, end-start), curb, root, .007)
    # Sparse rear side-window modules convey volume without long opaque sidewalls.
    for side_x in (.18, 71.82):
        box('Side_upper_window', (side_x, 6.75, 44.5), (.08, 1.2, 5.5), glass, root, 0)
        for h in (6.12, 6.75, 7.38):
            box('Side_window_horizontal', (side_x, h, 44.5), (.14, .065, 5.65), steel, root, .002)
        for z in (42, 43.25, 44.5, 45.75, 47):
            box('Side_window_mullion', (side_x, 6.75, z), (.14, 1.25, .055), steel, root, 0)
    box('Front_low_cutaway_curb', (36, .09, .17), (71.3, .18, .25), curb, root, .01)

    # Zone paint sits on the slab and introduces no obstruction or invented route.
    for start, end in (
        ((.7, 0, 14.3), (5.8, 0, 14.3)), ((5.8, 0, 14.3), (5.8, 0, 41.7)),
        ((5.8, 0, 41.7), (.7, 0, 41.7)),
        ((64.3, 0, .7), (64.3, 0, 11.7)), ((64.3, 0, 11.7), (71.3, 0, 11.7)),
        ((64.3, 0, .7), (71.3, 0, .7)),
    ):
        _zone_line(root, start, end, paint)
    for z in (14, 28, 42):
        for x in (7.7, 62.4):
            box('Cross_aisle_boundary_mark', (x, .004, z), (.075, .007, 1.5), paint, root, 0)
    for aisle in range(12):
        x = 10 + 4.5 * aisle
        for offset in (-.8, .8):
            box('Aisle_entry_edge_mark', (x + offset, .004, 13.35),
                (.075, .007, .8), paint, root, 0)
    for x, zs in ((2.2, (20, 36)), (69.8, (3, 9))):
        for z in zs:
            for index in range(3):
                for sign in (-1, 1):
                    stripe = box('Dock_floor_chevron', (x + sign * .16, .005, z + (index - 1) * .38),
                                 (.12, .008, .43), paint, root, 0)
                    stripe.rotation_euler.z = math.radians(sign * 45)
    return root


def build_dock():
    root = group('dock__MODULE')
    root['role'] = 'loading_dock'
    root['origin'] = 'floor_center_door_plane'
    root['forward_axis'] = '+Z_into_warehouse'
    root['service_anchor'] = [0, 0, 1.8]
    root['door_opening_m'] = [3.9, 3.8]
    steel = material('V2 dock | charcoal steel', '#354750', .73, .18)
    panel = material('V2 dock | blue grey door', '#6F8490', .8, .08)
    rubber = material('V2 dock | rubber bumpers', '#263238', .95)
    saffron = material('V2 dock | safety yellow', '#C5A14A', .8)
    roller = material('V2 dock | roller steel', '#9DAAA9', .6, .35)
    for sx in (-1, 1):
        box('Dock_frame_upright', (sx * 2.1, 2.6, 0), (.25, 5.2, .30), steel, root, .012)
        for offset in (-.14, .14):
            box('Dock_frame_channel_return', (sx*2.1, 2.6, offset), (.31, 5.2, .045), steel, root, .005)
        box('Dock_frame_baseplate', (sx*2.1, .025, 0), (.40, .05, .42), steel, root, .006)
        box('Dock_outer_seal', (sx * 1.94, 2.1, .025), (.12, 4.15, .19), rubber, root, .008)
        box('Dock_foot_guard', (sx * 2.1, .42, .18), (.32, .84, .32), saffron, root, .012)
        box('Dock_rubber_bumper', (sx * 1.67, .34, .13), (.28, .61, .24), rubber, root, .018)
        box('Dock_roller_side_rail', (sx * 1.85, .14, .76), (.10, .20, 1.42), steel, root, .006)
    box('Dock_header', (0, 5.075, 0), (4.45, .25, .35), steel, root, .012)
    box('Dock_header_front_flange', (0, 5.075, .19), (4.45, .29, .045), steel, root, .005)
    box('Dock_header_seal', (0, 3.88, .035), (3.9, .14, .19), rubber, root, .006)
    # Retracted shutter remains above the loading opening; service space is empty.
    for index in range(6):
        box('Retracted_door_slat', (0, 4.04 + index * .18, -.06),
            (3.88, .17, .10), panel, root, .006)
    cylinder('Door_roll_housing', (0, 4.92, -.08), .15, 3.91, panel, root, axis='X', vertices=12)
    box('Dock_roller_base', (0, .055, .76), (3.62, .11, 1.4), steel, root, .008)
    for index in range(10):
        cylinder('Dock_loading_roller', (0, .16, .16 + index * .13),
                 .06, 3.54, roller, root, axis='X', vertices=8)
    box('Dock_control_box', (2.30, 1.15, .08), (.24, .41, .21), panel, root, .008)
    for height in (1.07, 1.23):
        cylinder('Dock_control_button', (2.30, height, .195), .027, .025,
                 saffron, root, axis='Z', vertices=8)
    anchor = group('anchor_service__DOCK')
    anchor.parent = root
    anchor.location = xyz((0, 0, 1.8))
    anchor['role'] = 'dock_service_anchor'
    return root


if __name__ == '__main__':
    builders = (
        ('rack-high', build_rack_high),
        ('rack-low', build_rack_low),
        ('environment-shell', build_environment_shell),
        ('dock', build_dock),
    )
    selected = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    for asset_id, builder in builders:
        if selected and asset_id not in selected:
            continue
        reset()
        finish(asset_id, builder())
