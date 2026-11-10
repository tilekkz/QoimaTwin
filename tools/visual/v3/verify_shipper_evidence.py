"""Verify current P06.4 gates; acceptance requires actual root browser/image-review GO."""
import collections
import math
from verify_receiver_evidence import ROOT, EPS, read, sha, number, inputs, browser_review, options, finish


def verify_shipper(args):
    base = ROOT / 'assets/v3/iterations/shipper'
    paths = dict(runtime=base/'P06.2/runtime-native-poses.json', native=base/'P06.2/native-path-checks.json',
                 stance=base/'P06.2/stance-checks.json', browser=base/'P06.3/browser/browser-checks.json',
                 review=base/'P06.3/visual-review.json', cpu=ROOT/'docs/adaptive-v3/evidence/P06.4-checks.json')
    r, n, stance, b, c, v = (read(paths[k]) for k in ['runtime', 'native', 'stance', 'browser', 'cpu', 'review'])
    inputs([r, n, stance, b, c, v])
    assert n['passed'] is True and n['failure'] is None
    assert n['runtime_pose_sha256'] == stance['runtime_pose_sha256'] == sha(paths['runtime'])
    assert stance['native_report_ref']['sha256'] == sha(paths['native'])
    assert stance['frames'] == 594 and stance['foot_samples'] == 1188
    assert stance['native_boot_support_agreement'] is True and stance['scan_static_and_parcel_displacement_and_body_return_checks'] is True
    assert r['checks']['runtime_frames'] == 2954 and r['checks']['arbitrary_seeks'] == 100 and r['checks']['rigid_world_transforms'] == 3
    assert number(r['checks']['maximum_joint_step_per_10ms_rad']) < .08
    assert len(r['frames']) == len(n['frames']) == n['native_frames'] == 594
    assert [(f['mode'], f['time']) for f in r['frames']] == [(f['mode'], f['time']) for f in n['frames']]
    assert sum(f['opposed_parcel_contact'] for f in n['frames']) == 161
    assert sum(f['parcel_actual_support_rays'] for f in n['frames']) == 5346
    assert sum(f['connections'] for f in n['frames']) == 4752
    assert sum(f['C_mouth_gauges'] for f in n['frames']) == 1188
    assert all(number(f['maximum_stance_boot_floor_error_m']) < EPS and min(f['boot_floor_heights_m']) >= -EPS and
               f['heavy_pallet_unmoved'] is True and (f['contact_gap_m'] is None or number(f['contact_gap_m']) < EPS) for f in n['frames'])
    base_feet = {f['side']: f['world'] for f in r['frames'][0]['state']['actualFeet']}
    previous = {}
    maximum_error = maximum_slip = 0
    for frame in r['frames']:
        for foot in frame['state']['actualFeet']:
            side, point, target = foot['side'], foot['world'], foot['target']
            expected = [base_feet[side][0], target['lift'], base_feet[side][2] - target['travel']]
            maximum_error = max(maximum_error, math.dist(point, expected))
            key = (frame['mode'], side)
            if key in previous and target['stance'] and previous[key]['target']['stance']:
                maximum_slip = max(maximum_slip, math.dist(point, previous[key]['world']))
            previous[key] = foot
        assert not frame['state']['scanning'] or frame['state']['displacement_m'] == 0
        if frame['mode'] == 'place' and frame['time'] >= 11.4:
            assert frame['state']['displacement_m'] == .16
        if frame['mode'] == 'place' and frame['time'] >= 23:
            assert abs(frame['state']['body_distance_m']) < 1e-12
    assert maximum_error < EPS and maximum_slip < EPS and stance['passed'] is True
    assert abs(stance['maximum_absolute_sole_anchor_target_error_m'] - maximum_error) < 1e-12
    assert abs(stance['maximum_consecutive_stance_slip_m'] - maximum_slip) < 1e-12
    assert c['arm_regression_passed'] is True and c['complete_collision_certificate'] is False
    before, after = c['before_red'], c['after_green']
    assert before['anatomy_failures'] > 0 and number(before['maximum_contact_error_m']) < EPS
    assert after['frames'] == after['C_mouth_frames'] == 2954
    for key in ['anatomy_failures', 'C_mouth_failures', 'head_penetration_failures', 'dense_preparation_fixture_failures']:
        assert after[key] == 0, key
    assert after['head_probe_frames'] >= 2701 and after['dense_preparation_fixture_frames'] >= 202
    for key, maximum in [('maximum_eligible_pole_y_m', .02), ('maximum_eligible_signed_backbend_rad', .15), ('maximum_contact_error_m', EPS), ('maximum_joint_step_per_10ms_rad', .08)]:
        assert number(after[key]) < maximum, key
    assert c['preparation_regression']['before_transverse_witness']['found'] is True
    assert c['preparation_regression']['whole_preparation_transverse_gate_passed'] is True
    basis = c['native_contact_basis']
    assert basis['measured_point_and_opposed_native_normals_preserved'] is True
    assert number(basis['hand_pad']['gap_m']) < EPS and number(basis['parcel_wall']['gap_m']) < EPS
    assert basis['rejected_natural_old_orientation_control']['kind'] == 'triangle_inside_shrunken_C_mouth'
    assert c['lifecycle']['continuous_random_seeks'] == 100 and c['lifecycle']['continuous_reverse_repeat_checks'] == 200
    assert c['lifecycle']['zero_repeat_and_dispose_exact'] is True
    for key in ['same_actor_package_pallet_UUIDs', 'original_24_content_frames', 'body_parcel_feet_match_old_at_every_dense_sample', 'native_GLB_hashes_match_accepted_inputs']:
        assert c['conservation'][key] is True
    clear = c['native_clearance']
    assert clear['new_pair_time_requires_followup'] is False and not clear['new_pair_time_witnesses']
    assert len(clear['after']) == 13
    pairs = collections.Counter()
    allowed = {'worker-manual__batch_06#0', 'worker-manual__batch_06#1', 'worker-manual__batch_26#1', 'worker-manual__batch_26#3'}
    for frame in clear['after']:
        for witness in frame['positive_penetration_witnesses']:
            assert witness['source_component'] == 'worker-manual__batch_22#0' and witness['target_component'] in allowed, ('Unclassified nonadjacent native witness', witness)
            pairs[(witness['source_component'], witness['target_component'])] += 1
    joins = [dict(subject=a, target=b, observations=count) for (a, b), count in sorted(pairs.items())]
    artifacts = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths.values()}
    artifacts.update(browser_review(base/'P06.3', b, v, 24, 'same_actor_package_pallet_and_24_content_frames'))
    finish('P06.4', 'shipper', [r, n, stance, b, c, v], artifacts,
           dict(runtime_frames=2954, native_frames=594, parcel_contacts=161, actual_support_rays=5346,
                C_mouth_gauges=1188, maximum_stance_slip_m=maximum_slip, reviewed_images=24),
           dict(dense_frames=2954, mouth_failures=0, dense_head_poses=after['head_probe_frames'], dense_head_failures=0,
                dense_preparation_fixture_frames=after['dense_preparation_fixture_frames'], dense_preparation_fixture_failures=0,
                new_pair_time_witnesses=0, maximum_contact_error_m=after['maximum_contact_error_m'],
                tangent_twist_rad=basis['tangent_twist_rad'], opposed_native_normals=True), joins, args)


if __name__ == '__main__':
    verify_shipper(options())
