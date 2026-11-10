"""Verify current P05.4 gates; write acceptance only after explicit root review approval."""
import argparse
import collections
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EPS = 2e-6
BLOCKED = {
    'frontend/public/data/v3/warehouse-fixture-v3.json',
    'frontend/public/data/v3/worker-registry-v3.json',
    'frontend/public/data/v3/worker-profiles-v3.json',
    'frontend/public/data/v3/route-policy-v3.json',
    'frontend/src/adaptive-v3/warehouseActionSourceManifest.json',
    'docs/adaptive-v3/evidence/P05.json',
    'docs/adaptive-v3/evidence/P06.json',
    'docs/adaptive-v3/evidence/P05.4.json',
    'docs/adaptive-v3/evidence/P06.4.json',
}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    assert type(value) in (int, float) and math.isfinite(value), ('Not a finite number', value)
    return value


def current(hashes):
    for relative, expected in hashes.items():
        path = (ROOT / relative).resolve()
        assert path.is_relative_to(ROOT.resolve()), relative
        assert sha(path) == expected, ('Stale current evidence', relative)


def inputs(reports):
    result = {}
    for report in reports:
        assert report['engine_operation'] is False
        for path, expected in report.get('input_hashes', {}).items():
            assert path not in BLOCKED and not path.startswith('docs/adaptive-v3/evidence/W05'), ('Acceptance cycle', path)
            assert path not in result or result[path] == expected, ('Disagreeing gate sources', path)
            result[path] = expected
    current(result)
    return result


def browser_review(base, browser, review, image_count, role_check):
    assert browser.get('failure') is None and not browser['fatal'] and not browser['failed_resources']
    assert browser['preview_only'] is False and browser['visible'] is False and browser['lifecycle']['terminated'] is True
    for key in ['cold_reduced_motion_no_autoplay', role_check, 'inward_rest_palms',
                'mobile_360_touch_modes_seek_and_no_overflow', 'keyboard_range_view_focus_and_semantic_status',
                'manual_play_pause_and_live_reduced_motion', 'missing_asset_cleanup_recovery',
                'invalid_timeline_cleanup_recovery', 'loading_status_and_disabled_views',
                'stale_load_no_actor_resurrection']:
        assert browser['checks'][key] is True, key
    mode_key = 'scan_receive_idle_blocked_distinct' if image_count == 17 else 'scan_place_idle_blocked_distinct'
    assert browser['checks'][mode_key] is True
    assert len({json.dumps(x, sort_keys=True) for x in browser['checks']['replacement_peak_memory']}) == 1
    assert review['passed'] is True and review['reviewer'] == 'root' and review['engine_operation'] is False
    assert review['browser_report_sha256'] == sha(base / 'browser/browser-checks.json')
    assert isinstance(review['reviewed_at'], str) and review['reviewed_at']
    assert len(review['images']) == image_count and len({x['file'] for x in review['images']}) == image_count
    assert {x['file'] for x in browser['frames']}.issubset({x['file'] for x in review['images']})
    artifacts = {}
    for image in review['images']:
        assert isinstance(image['observation'], str) and image['observation'].strip()
        path = (base / 'browser' / image['file']).resolve()
        assert path.is_relative_to((base / 'browser').resolve()) and sha(path) == image['sha256']
        artifacts[path.relative_to(ROOT).as_posix()] = image['sha256']
    return artifacts


def options():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Require exact current acceptance wrapper; write nothing')
    parser.add_argument('--write-wrapper', action='store_true', help='Only after actual root browser/image-review GO; recomputes CPU gate first')
    parser.add_argument('--classify-proximal-joins', action='store_true', help='Record explicit root classification of the enumerated pre-existing proximal model joins')
    parser.add_argument('--recompute-cpu', action='store_true', help='Run full CPU check-only before checking report agreement')
    args = parser.parse_args()
    assert not (args.check_only and args.write_wrapper)
    return args


def finish(task, role, reports, artifacts, summary, cpu_summary, joins, args):
    source_hashes = inputs(reports)
    verifier_paths = ['tools/visual/v3/verify_receiver_evidence.py']
    if role == 'shipper':
        verifier_paths.append('tools/visual/v3/verify_shipper_evidence.py')
    source_hashes.update({p: sha(ROOT / p) for p in verifier_paths})
    if args.recompute_cpu or args.write_wrapper:
        result = subprocess.run(['node', f'tools/check-{role}-elbows-v3.mjs', '--check-only'],
                                cwd=ROOT / 'frontend', capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, ('CPU recomputation failed', (result.stdout + result.stderr)[-3000:])
    current(source_hashes)
    current(artifacts)
    path = ROOT / f'docs/adaptive-v3/evidence/{task}.json'
    existing = read(path) if path.exists() else None
    classified = args.classify_proximal_joins or bool(existing and existing.get('proximal_join_classification', {}).get('reviewer') == 'root')
    if args.write_wrapper:
        assert classified or not joins, 'Root must explicitly classify listed proximal observations before acceptance'
    wrapper = dict(task_id=task, passed=True, reviewer='root', source_kind='visual_fixture',
                   engine_operation=False, operational_admission=False, visual_complete=False,
                   backend_integration_complete=False, current_isolated_kit_acceptance=True,
                   completed_jobs=0, role=role, reviewed_at=reports[-1]['reviewed_at'],
                   checks=summary, cpu_elbow_and_hand_gate=cpu_summary,
                   complete_collision_certificate=False,
                   proximal_join_classification=dict(reviewer='root' if classified else None,
                       kind='pre_existing_proximal_model_joins', observations=joins,
                       total_observations=sum(x['observations'] for x in joins),
                       scope='Only the enumerated upper-sleeve/shoulder-band/shirt/vest joins; no head, wrist, distal-body or workcell waiver. These remain recorded intersections, not a zero-intersection claim.'),
                   source_hashes=source_hashes, artifacts=artifacts,
                   historical_proofs=[dict(path=f'docs/adaptive-v3/evidence/{task[:3]}.{n}.json',
                       sha256=sha(ROOT / f'docs/adaptive-v3/evidence/{task[:3]}.{n}.json'), current_acceptance=False) for n in (2, 3)],
                   scope='Current bounded prepared single-actor visual fixture. Native, runtime, CPU and actual root image review agree on current source bytes. No inventory operation, decoder, warehouse physical join, throughput or complete continuous collision/ergonomics certificate.')
    blob = (json.dumps(wrapper, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if args.write_wrapper:
        temporary = path.with_suffix('.json.tmp')
        temporary.write_bytes(blob)
        temporary.replace(path)
    elif existing:
        assert classified or not joins
        assert path.read_bytes() == blob, ('Stale acceptance wrapper; rerun current gates and explicit root review', task)
    elif args.check_only:
        raise AssertionError(('Current acceptance wrapper not yet issued by root', task))
    print(json.dumps(dict(task_id=task, gates_passed=True, passed=bool(existing or args.write_wrapper),
        wrapper_written=args.write_wrapper, wrapper_present=path.exists(), proximal_root_classification_pending=bool(joins and not classified),
        engine_operation=False, checks=summary, acceptance_sha256=sha(path) if path.exists() else None)))


def verify_receiver(args):
    base = ROOT / 'assets/v3/iterations/receiver'
    paths = dict(runtime=base/'P05.2/runtime-native-poses.json', native=base/'P05.2/native-path-checks.json',
                 browser=base/'P05.3/browser/browser-checks.json', review=base/'P05.3/visual-review.json',
                 cpu=ROOT/'docs/adaptive-v3/evidence/P05.4-checks.json')
    r, n, b, c, v = (read(paths[k]) for k in ['runtime', 'native', 'browser', 'cpu', 'review'])
    inputs([r, n, b, c, v])
    assert n['passed'] is True and n['failure'] is None and n['proposed_layout'] is None
    assert n['runtime_pose_sha256'] == sha(paths['runtime'])
    assert r['checks']['runtime_frames'] == 2034 and r['checks']['arbitrary_seeks'] == 100
    assert number(r['checks']['maximum_joint_step_per_10ms_rad']) < .08
    assert len(r['frames']) == n['native_frames'] == len(n['frames']) == 410
    assert [(f['mode'], f['time']) for f in n['frames']] == [(f['mode'], f['time']) for f in r['frames']]
    assert sum(f['opposed_terminal_contact'] for f in n['frames']) == 41
    assert sum(f['C_mouth_gauges'] for f in n['frames']) == 820
    assert sum(f['connections'] for f in n['frames']) == 3280
    assert all(number(f['maximum_boot_floor_error_m']) < EPS and f['scan_line_clear'] and
               (f['contact_gap_m'] is None or number(f['contact_gap_m']) < EPS) for f in n['frames'])
    assert c['executed'] is True and c['passed'] is True and c['complete_collision_certificate'] is False
    assert not c['failures'] and not c['mouth_gauge']['dense_current_failures']
    assert c['first_natural_mouth_red']['violation'] and number(c['first_natural_mouth_red']['contact_error_m']) < EPS
    assert any(a['rejected'] for a in c['baseline_red']['arms']) and number(c['baseline_red']['contact_error_m']) < EPS
    checks = c['checks']
    assert checks['dense_frames'] == 2034 and checks['boundary_frames'] >= 50 and checks['arbitrary_seeks'] == 100 and checks['rigid_world_transforms'] == 3
    for key in ['builder_check_only', 'same_actor_HU_and_pallet_matrix', 'invalid_inputs_unchanged', 'dispose_rebind_restore', 'disposed_actor_not_resurrected']:
        assert checks[key] is True, key
    for key, maximum in [('maximum_eligible_pole_y_m', .02), ('maximum_eligible_signed_native_bend_rad', .15), ('maximum_active_contact_error_m', EPS), ('maximum_joint_step_per_10ms_rad', .08)]:
        assert number(checks[key]) < maximum, key
    basis = c['native_contact_faces']
    assert number(basis['maximum_opposed_normal_dot']) < -.99999
    assert number(basis['pad_hand_local']['distance_m']) < EPS and number(basis['screen_cell_local']['distance_m']) < EPS
    clear = c['native_clearance']
    assert clear['passed'] is True and clear['current_nonadjacent_material_witnesses'] == 0
    assert clear['sampled_poses_per_version'] == len(clear['current']) == 37
    assert clear['dense_preparation_head']['poses_per_version'] == 482 and not clear['dense_preparation_head']['current']
    assert clear['controls']['overlapping_closed_mesh'] is True and clear['controls']['boundary_only_rejected'] is True
    pairs = collections.Counter()
    for frame in clear['current']:
        for w in frame['witnesses']:
            assert w['adjacent_shoulder_seam'] is True and w['subject'] == 'worker-manual__batch_22'
            assert w['target'] in ['worker-manual__batch_06', 'worker-manual__batch_26']
            pairs[(w['subject'], w['target'])] += 1
    joins = [dict(subject=a, target=b, observations=count) for (a, b), count in sorted(pairs.items())]
    assert sum(pairs.values()) == clear['current_positive_witnesses'] == clear['adjacent_shoulder_seam_observations']['current']
    artifacts = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths.values()}
    artifacts.update(browser_review(base/'P05.3', b, v, 17, 'same_actor_HU_and_24_content_frames'))
    finish('P05.4', 'receiver', [r, n, b, c, v], artifacts,
           dict(runtime_frames=2034, native_frames=410, terminal_contacts=41, C_mouth_gauges=820, reviewed_images=17),
           dict(dense_frames=2034, boundary_frames=checks['boundary_frames'], mouth_failures=0, dense_head_poses=482,
                dense_head_failures=0, sampled_nonadjacent_material_witnesses=0,
                maximum_contact_error_m=checks['maximum_active_contact_error_m'],
                tangent_twist_rad=basis['tangent_twist_rad'], opposed_native_normals=True), joins, args)


if __name__ == '__main__':
    verify_receiver(options())
