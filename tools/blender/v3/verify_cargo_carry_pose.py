"""Static closed-solid carry candidate gate using exact captured runtime transforms.

Read-only source append in a dedicated background Blender process. Never saves or
rebuilds a source model. A passing candidate is not an accepted carry action.
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v3_common import ROOT, reset, xyz, runtime_xyz
from build_sealed_parcel import append_source
from build_picker_figure import physical_body
from build_standard_carton import collect
from native_clearance import penetration, touching, connected_parts

assert bpy.app.background, 'Dedicated background process required'
EPS = 2e-6
C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
OUT = ROOT / 'assets/v3/iterations/warehouse/W04.3/carry-native'
CANDIDATE = 'assets/v3/iterations/warehouse/W04.3/candidate-carry-pose.json'
CAPTURE = 'assets/v3/iterations/warehouse/W04.3/carry-candidate-browser/review-capture.json'
SOURCES = [
    CANDIDATE, CAPTURE,
    'assets/v3/blender/worker-base.blend',
    'assets/v3/blender/worker-manual.blend',
    'assets/v3/blender/small-carton.blend',
    'frontend/public/models/v3/worker-base.glb',
    'frontend/public/models/v3/worker-manual.glb',
    'frontend/public/models/v3/small-carton.glb',
    'assets/v3/specs/worker-base.dimensions.json',
    'docs/v3/contract-proposals/cargo-catalog-v3.json',
    'tools/blender/v3/verify_cargo_carry_pose.py',
    'tools/blender/v3/native_clearance.py',
    'tools/blender/v3/build_picker_figure.py',
    'tools/blender/v3/build_standard_carton.py',
    'tools/blender/v3/build_sealed_parcel.py',
    'tools/blender/v3/v3_common.py',
]


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def signature(parts):
    content = [{k: p[k] for k in ['name', 'verts', 'triangles']}
               for p in sorted(parts, key=lambda p: p['name'])]
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def segment(obj):
    original = {'joint__head', 'joint__torso', 'joint__pelvis'} | {
        f'joint__{part}_{side}' for side in ['L', 'R']
        for part in ['upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot']}
    node = obj.parent
    while node is not None:
        if node.name in original:
            return node.name
        node = node.parent
    return 'root'


report = dict(passed=False, candidate_only=True, accepted_pose=False,
              source_kind='visual_fixture', engine_operation=False,
              background=True, blender_version=bpy.app.version_string,
              owned_pid=os.getpid(), contact_tolerance_m=EPS, input_hashes={})
stage = 'inputs'
failure = None
try:
    inputs = {p: sha(p) for p in SOURCES}
    candidate, capture = read(CANDIDATE), read(CAPTURE)
    inputs.update(capture['input_hashes'])
    for path, digest in inputs.items():
        assert sha(path) == digest, ('Stale input', path)
    assert candidate['candidate_only'] and candidate['engine_operation'] is False
    assert capture['candidate_sha256'] == sha(CANDIDATE) and not capture['fatal']
    assert capture['lifecycle']['terminated']
    assert len(capture['frames']) == 5
    poses = [f['state']['joints'] for f in capture['frames']]
    assert len({json.dumps(p, sort_keys=True) for p in poses}) == 1
    pose = poses[0]
    assert len(pose) == 27
    assert all(f['state']['worker_scale'] == f['state']['cargo_scale'] == [1, 1, 1]
               for f in capture['frames'])
    hu = candidate['cargo']
    assert hu['dimensions_xyz_m'] == [.32, .24, .24] and hu['gross_mass_kg'] == .94
    assert hu['quantity_units'] == 24 and hu['scale'] == [1, 1, 1]
    assert hu['position_m'] == [0, .85, .4] and hu['yaw_rad'] == 0
    record = next(r for r in read('docs/v3/contract-proposals/cargo-catalog-v3.json')['records']
                  if r['archetype_id'] == 'SMALL_CARTON')
    for key in ['dimensions_xyz_m', 'gross_mass_kg', 'units_per_handling_unit']:
        actual = hu['quantity_units'] if key == 'units_per_handling_unit' else hu[key]
        assert actual == record['handling_unit'][key]
    report.update(input_hashes=inputs, runtime_pose_sha256=sha(CAPTURE),
                  candidate_sha256=sha(CANDIDATE), identical_captured_views=5,
                  exact_runtime_joints=27, immutable_HU=hu)

    stage = 'neutral_source_agreement'
    reset()
    base = append_source('assets/v3/blender/worker-base.blend', 'worker_base_root', None)
    base_parts, _ = physical_body(base)
    base_by = {p['name']: p for p in base_parts}
    assert len(base_by) == 50
    base_signature = signature(base_parts)
    reset()
    worker = append_source('assets/v3/blender/worker-manual.blend', 'worker_base_root', None)
    native_neutral, _ = physical_body(worker)
    assert len(native_neutral) == 50 and {p['name'] for p in native_neutral} == set(base_by)
    maximum_neutral_error = 0
    for part in native_neutral:
        reference = base_by[part['name']]
        assert part['triangles'] == reference['triangles']
        assert len(part['verts']) == len(reference['verts'])
        maximum_neutral_error = max(maximum_neutral_error,
                                    *(abs(a - b) for v, w in zip(part['verts'], reference['verts'])
                                      for a, b in zip(v, w)))
    assert maximum_neutral_error < EPS
    report['neutral_source_agreement'] = dict(
        original_body_parts=50, manual_body_parts=50,
        maximum_world_vertex_error_m=maximum_neutral_error,
        original_signature=base_signature, manual_neutral_signature=signature(native_neutral),
        method='Same named native closed pieces/topology, world vertex comparison before posing')
    raw_geometry = {o.name: [tuple(v.co) for v in o.data.vertices]
                    for o in worker.children_recursive if o.type == 'MESH'}
    nodes = {o.name: o for o in worker.children_recursive}
    assert set(pose) == {name for name in nodes if name.startswith('joint__')}

    stage = 'original_and_manual_limits'
    original_limits = read('assets/v3/specs/worker-base.dimensions.json')['joints']
    assert len(original_limits) == 15
    checked_limits = []
    maximum_declared_runtime_rotation_error = 0
    for name, angles in candidate['jointEulerXYZ'].items():
        if name in original_limits:
            bounds = original_limits[name]['limits_radians_xyz']
        elif name.startswith('joint__shoulder_lift_'):
            bounds = [[-.8, 0], [0, 0], [0, 0]]
        elif name.startswith('joint__elbow_swivel_'):
            bounds = [[-math.pi, math.pi], [0, 0], [0, 0]]
        elif name.startswith('joint__palm_roll_'):
            bounds = [[0, 0], [-math.pi, math.pi], [0, 0]]
        else:
            raise AssertionError(('Unknown changed joint', name))
        assert all(lo - 1e-10 <= a <= hi + 1e-10 for a, (lo, hi) in zip(angles, bounds))
        if 'custom_axis_runtime' in nodes[name]:
            expected_rotation = Quaternion(Vector(nodes[name]['custom_axis_runtime']).normalized(), angles[0])
        else:
            expected_rotation = (Matrix.Rotation(angles[0], 3, 'X')
                                 @ Matrix.Rotation(angles[1], 3, 'Y')
                                 @ Matrix.Rotation(angles[2], 3, 'Z')).to_quaternion()
        q = pose[name]['quaternion']
        captured_rotation = Quaternion((q[3], q[0], q[1], q[2])).normalized()
        rotation_error = expected_rotation.rotation_difference(captured_rotation).angle
        maximum_declared_runtime_rotation_error = max(maximum_declared_runtime_rotation_error, rotation_error)
        assert rotation_error <= 2e-6, ('Declared angles do not match actual captured pose', name, rotation_error)
        checked_limits.append(dict(joint=name, angles=angles, bounds=bounds))
    unchanged_original = []
    for name in set(original_limits) - set(candidate['jointEulerXYZ']):
        native_rotation = nodes[name].matrix_basis.to_quaternion().to_matrix()
        expected = (C.transposed() @ native_rotation @ C).to_quaternion()
        q = pose[name]['quaternion']
        captured = Quaternion((q[3], q[0], q[1], q[2])).normalized()
        assert expected.rotation_difference(captured).angle <= 2e-6, ('Unchanged original joint moved', name)
        unchanged_original.append(name)
    for name, position in candidate.get('jointTranslations', {}).items():
        assert name in ['joint__finger_thumb_L', 'joint__finger_thumb_R']
        assert position == [0, 0, -.005]
        assert list(nodes[name]['signed_travel_m']) == [-.005, 0]
    maximum_local_position_error = 0
    for name, transform in pose.items():
        expected = candidate.get('jointTranslations', {}).get(name, runtime_xyz(nodes[name].location))
        error = math.dist(expected, transform['position'])
        maximum_local_position_error = max(maximum_local_position_error, error)
        assert error <= EPS, ('Unexpected local joint translation', name, error)
    report['limits'] = dict(original_joint_limits_retained=15,
                            changed_rotation_joints=checked_limits,
                            unchanged_original_rest_joints=sorted(unchanged_original),
                            maximum_declared_runtime_rotation_error_rad=maximum_declared_runtime_rotation_error,
                            all27_local_positions_match_source_or_approved_translation=True,
                            maximum_runtime_local_position_error_m=maximum_local_position_error,
                            approved_thumb_retraction_m=.005,
                            candidate_angles_used_for_limit_check_only=True,
                            native_pose_uses_exact_captured_quaternions=True)

    stage = 'apply_exact_runtime_pose'
    for name, transform in pose.items():
        node = nodes[name]
        node.location = xyz(transform['position'])
        q = transform['quaternion']
        node.rotation_mode = 'QUATERNION'
        node.rotation_quaternion = (C @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
                                    @ C.transposed()).to_quaternion()
    cargo = append_source('assets/v3/blender/small-carton.blend', 'small-carton', None)
    cargo.location = xyz(hu['position_m'])
    bpy.context.view_layer.update()
    assert all(raw_geometry[o.name] == [tuple(v.co) for v in o.data.vertices]
               for o in worker.children_recursive if o.type == 'MESH')
    worker_parts, _ = physical_body(worker)
    cargo_parts, _ = collect(cargo)
    by = {p['name']: p for p in worker_parts}
    assert len(worker_parts) == 50
    assert all(abs(v - 1) < EPS for o in [worker, cargo] + list(worker.children_recursive)
               + list(cargo.children_recursive) for v in o.scale)
    report.update(native_body_parts=50, native_cargo_parts=len(cargo_parts),
                  original_raw_mesh_vertices_unchanged=True, scale_one=True,
                  posed_body_signature=signature(worker_parts))

    stage = 'native_body_cargo_penetration'
    cargo_hits = []
    for a in worker_parts:
        for b in cargo_parts:
            hit = penetration(a, b, EPS)
            if hit is not None:
                cargo_hits.append(hit)
    report['body_cargo'] = dict(pairs_checked=len(worker_parts) * len(cargo_parts),
                                true_closed_solid_penetrations=cargo_hits)
    assert not cargo_hits, ('Actual body/cargo penetration', cargo_hits[:5])

    stage = 'native_body_self_penetration'
    segment_of = {p['name']: segment(bpy.data.objects[p['name']]) for p in worker_parts}
    adjacent = [('torso', 'pelvis'), ('head', 'torso')]
    for side in ['L', 'R']:
        adjacent += [(f'upper_arm_{side}', 'torso'), (f'forearm_{side}', f'upper_arm_{side}'),
                     (f'hand_{side}', f'forearm_{side}'), (f'thigh_{side}', 'pelvis'),
                     (f'shin_{side}', f'thigh_{side}'), (f'foot_{side}', f'shin_{side}')]
    adjacent = {frozenset(['joint__' + a, 'joint__' + b]) for a, b in adjacent}
    foreign, adjacent_hits, assembly_hits, pairs = [], [], [], 0
    for index, a in enumerate(worker_parts):
        for b in worker_parts[index + 1:]:
            pairs += 1
            hit = penetration(a, b, EPS)
            if hit is None:
                continue
            hit['segments'] = [segment_of[a['name']], segment_of[b['name']]]
            if hit['segments'][0] == hit['segments'][1]:
                hit['classification'] = 'same_rigid_body_segment_assembly'
                assembly_hits.append(hit)
            elif frozenset(hit['segments']) in adjacent:
                hit['classification'] = 'declared_adjacent_rigid_joint_interface'
                adjacent_hits.append(hit)
            else:
                hit['classification'] = 'nonadjacent_foreign_body_parts'
                foreign.append(hit)
    report['body_self'] = dict(all_physical_pairs_checked=pairs,
                               same_segment_assembly_intersections=assembly_hits,
                               adjacent_joint_interface_intersections=adjacent_hits,
                               nonadjacent_penetrations=foreign,
                               segment_of_physical_parts=segment_of,
                               adjacency_policy='Only same rigid segment or explicit original bone adjacency; every actual allowed witness is recorded. No foreign-part whitelist.')
    assert not foreign, ('Nonadjacent actual body penetration', foreign[:5])

    stage = 'physical_connectivity'
    all_body_links = connected_parts(worker_parts)
    hand_links, forearm_links, explicit_links = {}, {}, []
    for side in ['L', 'R']:
        hand = [by[f'mitten_{side}_{part}'] for part in ['lower_pad', 'upper_pad', 'thumb', 'spine']]
        hand_links[side] = connected_parts(hand)
        forearm_links[side] = connected_parts([by[f'fore_sleeve_{side}'], by[f'cuff_{side}']] + hand)
        for a, b in [('upper_sleeve', 'fore_sleeve'), ('cuff', 'mitten_spine'),
                     ('trouser_thigh', 'trouser_shin'), ('trouser_shin', 'boot')]:
            left = a + '_' + side
            right = f'mitten_{side}_spine' if b == 'mitten_spine' else b + '_' + side
            assert touching(by[left], by[right], EPS), ('Native limb detached', left, right)
            explicit_links.append([left, right])
        shoulder = [p['name'] for p in worker_parts if segment_of[p['name']] == 'joint__torso'
                    and touching(by['upper_sleeve_' + side], p, EPS)]
        assert shoulder, ('Native shoulder detached', side)
        explicit_links += [['upper_sleeve_' + side, name] for name in shoulder]
    report['connectivity'] = dict(all50_native_parts_connected=True,
                                  all_body_contact_edges=all_body_links,
                                  four_piece_hand_contact_edges=hand_links,
                                  forearm_cuff_hand_contact_edges=forearm_links,
                                  explicit_shoulder_elbow_wrist_leg_links=explicit_links)

    stage = 'opposed_native_glove_carton_contacts'
    contacts = []
    for contact in candidate['contacts']:
        side = contact['side']
        point = nodes['joint__hand_' + side].matrix_world @ xyz(contact['local_hand_m'])
        pad = by[f'mitten_{side}_lower_pad']
        pn_point, pn, _, pad_distance = pad['bvh'].find_nearest(point)
        native_hits = [(p['bvh'].find_nearest(point), p['name']) for p in cargo_parts]
        (box_point, box_normal, _, box_distance), box_name = min(native_hits, key=lambda item: item[0][3])
        assert pad_distance <= EPS and box_distance <= EPS
        assert math.dist(runtime_xyz(point), contact['world_contact_m']) <= EPS
        toward_box = Vector((1 if side == 'L' else -1, 0, 0))
        outward_box = Vector(runtime_xyz(box_normal)).normalized()
        assert outward_box.dot(toward_box) < -.99999
        hand_parts = [p for p in worker_parts if p['name'].startswith('mitten_' + side + '_')]
        hand_support_projection = max(toward_box.dot(Vector(v)) for p in hand_parts for v in p['verts'])
        target_projection = toward_box.dot(Vector(runtime_xyz(point)))
        assert hand_support_projection <= target_projection + EPS, ('Hand crosses clamp support plane', side)
        contacts.append(dict(side=side, native_hand_part=pad['name'], native_carton_part=box_name,
                             expected_world_m=contact['world_contact_m'], native_world_m=runtime_xyz(point),
                             hand_surface_gap_m=pad_distance, carton_surface_gap_m=box_distance,
                             actual_surface_pair_gap_m=(pn_point - box_point).length,
                             selected_hand_face_normal_runtime=runtime_xyz(pn),
                             carton_face_normal_runtime=runtime_xyz(box_normal),
                             clamp_normal_runtime=list(toward_box),
                             hand_support_plane_excess_m=hand_support_projection-target_projection,
                             contact_kind='Native convex fingertip/edge contact; opposite support planes. Individual edge-face normals may tilt, not claimed parallel flat-face contact.'))
    assert len(contacts) == 2 and Vector(contacts[0]['clamp_normal_runtime']).dot(Vector(contacts[1]['clamp_normal_runtime'])) < -.99999
    report['opposed_contacts'] = contacts

    stage = 'native_floor_and_dimensions'
    floor = {side: abs(by['boot_' + side]['low'][1]) for side in ['L', 'R']}
    assert max(floor.values()) <= EPS and min(p['low'][1] for p in worker_parts) >= -EPS
    low = [min(p['low'][i] for p in cargo_parts) for i in range(3)]
    high = [max(p['high'][i] for p in cargo_parts) for i in range(3)]
    assert all(abs((b-a)-d) <= EPS for a, b, d in zip(low, high, hu['dimensions_xyz_m']))
    report['native_floor_and_HU'] = dict(boot_floor_error_m=floor, cargo_bounds=dict(min=low,max=high),
                                        exact_dimensions_preserved=True, original15limits_preserved=True)
except Exception as error:
    failure = dict(stage=stage, error=str(error))
    print('CARRY_NATIVE_REJECTED ' + json.dumps(failure), flush=True)

for path, digest in report['input_hashes'].items():
    if sha(path) != digest:
        failure = dict(stage='final_source_freshness', error='Input changed during native check', path=path)
report.update(passed=failure is None, failure=failure,
              scope='One static candidate pose from five identical captured views. Native closed-solid winding/transverse penetration, actual adjacency/connectivity and opposed convex-edge support-plane contacts. No strength, friction adequacy, balance/stability, ergonomic, moving action/trajectory, engine operation or full W04 acceptance.')
OUT.mkdir(parents=True, exist_ok=True)
if failure:
    history_path = OUT / 'rejections.json'
    history = json.loads(history_path.read_text(encoding='utf8')) if history_path.exists() else []
    history.append(report)
    history_path.write_text(json.dumps(history, indent=2)+'\n', encoding='utf8')
(OUT / 'native-checks.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
assert failure is None, failure
print('CARRY_NATIVE_VERIFIED ' + json.dumps(dict(parts=report['native_body_parts'],cargo_parts=report['native_cargo_parts'],contacts=len(report['opposed_contacts']))), flush=True)
