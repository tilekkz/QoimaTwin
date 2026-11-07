"""Metric v2 loader calibration: XYZ metre rulers, worker, rack and belt.

No global root rotation/scale. All metadata coordinates use runtime Y-up metres.
Run only through the project's fresh background Blender runner.
"""
import json
from v2_common import reset, finish, group, box, beam, material, xyz
from assemble_large_warehouse import _load, _clone


def build():
    root = group('calibration_root__V2')
    root['role'] = 'metric_axis_and_anchor_calibration'
    root['expected_worker_height_m'] = 1.7
    root['expected_rack_height_m'] = 4.65
    root['logical_rack_envelope_height_m'] = 5.4
    root['expected_conveyor_top_m'] = .9
    root['ruler_interval_m'] = .1
    neutral = material('V2 calibration | neutral slab', '#D1D2C4', .95)
    red = material('V2 calibration | X red', '#BD5348', .85)
    green = material('V2 calibration | Y green', '#53876D', .85)
    blue = material('V2 calibration | Z blue', '#527C9A', .85)
    box('Calibration_support_surface', (3, -.025, 0), (8, .05, 3), neutral, root, 0)
    for axis, endpoint, mat in (
        ('X', (1, .02, 0), red), ('Y', (0, 1, 0), green), ('Z', (0, .02, 1), blue),
    ):
        start = (0, 0, 0) if axis == 'Y' else (0, .02, 0)
        beam('Ruler_1m_' + axis, start, endpoint, .012, mat, root)
        anchor = group('calibration_axis_end__' + axis)
        anchor.parent = root
        point = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}[axis]
        anchor.location = xyz(point)
        anchor['role'] = 'calibration_axis_endpoint'
        anchor['axis'] = axis
        anchor['length_m'] = 1.
        for index in range(11):
            value = index / 10
            if axis == 'X':
                position, size = (value, .028, 0), (.006, .006, .075)
            elif axis == 'Y':
                position, size = (0, value, 0), (.075, .006, .012)
            else:
                position, size = (0, .028, value), (.075, .006, .006)
            box('Ruler_tick_%s_%02d' % (axis, index), position, size, mat, root, 0)

    expected = {'origin': [0, 0, 0], 'worker_floor': [2, 0, 0],
                'worker_head': [2, 1.7, 0], 'rack_floor': [4, 0, 0],
                'belt_top': [6, .9, 0]}
    prototypes = {}
    for asset_id, name, position in (
        ('standing-worker', 'calibration_worker__1_7m', (2, 0, 0)),
        ('rack-high', 'calibration_rack__4_65m', (4, 0, 0)),
        ('conveyor-high', 'calibration_conveyor__0_9m', (6, 0, 0)),
    ):
        prototype = _load(asset_id, 'v2')
        prototypes[asset_id] = prototype
        instance = _clone(prototype, name, root, position)
        instance['calibration_asset'] = asset_id
    for level, height in enumerate((.45, 2.25, 4.05), 1):
        expected['rack_bin_%02d' % level] = [4, height, 0]
    for name, point in expected.items():
        anchor = group('calibration_anchor__' + name)
        anchor.parent = root
        anchor.location = xyz(point)
        anchor['role'] = 'calibration_measurement_anchor'
        anchor['expected_runtime_xyz'] = point
    root['expected_runtime_anchors_json'] = json.dumps(expected)
    root['measurement_note'] = 'Rulers are 1m centreline lengths; tick geometry extends slightly beyond endpoints.'
    for prototype in prototypes.values():
        for obj in list(prototype.children_recursive) + [prototype]:
            import bpy
            bpy.data.objects.remove(obj, do_unlink=True)
    return root


if __name__ == '__main__':
    reset()
    finish('calibration-v2', build(), batch_runtime=False)
