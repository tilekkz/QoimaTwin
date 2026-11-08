"""Verify current W04.3 native holder evidence without rendering or changing reports."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/warehouse/W04.3'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def current(hashes):
    for path, digest in hashes.items():
        assert sha(path) == digest, ('Stale holder evidence', path)


pure = read('docs/adaptive-v3/evidence/W04.3-holder-state-checks.json')
kit = read('docs/adaptive-v3/evidence/W04.3-support-kit-checks.json')
geometry = read('docs/adaptive-v3/evidence/W04.3-geometry-carrier-checks.json')
browser = read('assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json')
summary = read('docs/adaptive-v3/evidence/W04.3-browser-checks.json')
clearance = read('docs/adaptive-v3/evidence/W04.3-scene-clearance-checks.json')
review = read('assets/v3/iterations/warehouse/W04.3/visual-review.json')
for report in [pure, kit, geometry, browser, summary]:
    assert report['passed'] and report['source_kind'] == 'visual_fixture'
    assert report['engine_operation'] is False and report['operational_admission'] is False
    current(report.get('input_hashes', {}))
assert len(pure['positive_cases']) == 15 and len(pure['negative_cases']) == 68
assert all(case['rejected'] for case in pure['negative_cases'])
assert pure['vehicle_families_checked'] == 6 and pure['one_holder_per_physical_entity']
assert pure['initial_HUs'] == 530 and pure['quantity_units'] == 12256
assert abs(pure['gross_mass_kg'] - 9403.85) < 1e-8
assert len(kit['cases']) == 24 and kit['reviewed_native_pose_joints'] == 27
assert kit['source_byte_identity'] and kit['maximum_pose_local_position_error_m'] < 1e-12
assert kit['maximum_pose_quaternion_component_error'] < 1e-12
assert len(geometry['checks']) == 29
assert browser['mode'] == 'full_holder_gate' and browser['visible'] is False
assert len(browser['checks']) == 20 and all(browser['checks'].values())
assert browser['lifecycle']['terminated'] and not browser.get('failure')
assert not browser['fatal'] and not browser['unexpected']
assert len(browser['observations']) == 10 and len(browser['frames']) == 14
assert len(browser['negative_cases']) == 4 and summary['checks'] == 20
fixture = read('frontend/public/data/v3/warehouse-fixture-v3.json')
stock = {h['handling_unit_id']: h for h in fixture['inputs']['initial_stock']}
worker_ids = set(read('frontend/public/data/v3/worker-registry-v3.json')['workers'][i]['actor_id'] for i in range(24))
families = set()
max_contact = 0.0
for row in browser['observations']:
    native, scene = row['native'], row['scene']
    hu = stock[row['handling_unit_id']]
    assert native['dimensions_xyz_m'] == hu['dimensions_xyz_m']
    assert native['gross_mass_kg'] == hu['gross_mass_kg']
    assert native['quantity_units'] == hu['quantity_units']
    assert native['model_scale_factor'] == 1 and native['vertices'] > 0
    assert len(native['mesh_instances']) == native['mesh_parts'] > 0
    assert scene['workers'] == 24 and set(scene['worker_ids']) == worker_ids
    assert scene['stock_HUs'] == scene['cargo_binding_count'] == 530
    assert scene['actions_scheduled'] == scene['completed_jobs'] == 0
    assert scene['holders']['equipment']['cart_ids'] == ['C01']
    assert scene['holders']['equipment']['cart_totes'] == 1
    assert scene['holders']['equipment']['long_cradle_count'] == 1
    d, bounds = hu['dimensions_xyz_m'], native['bounds_cargo_local']
    for values, expected in [(bounds['min'], [-d[0]/2, 0, -d[2]/2]), (bounds['max'], [d[0]/2, d[1], d[2]/2])]:
        assert max(abs(a-b) for a, b in zip(values, expected)) <= 2e-6
    if row['kind'] == 'actor':
        assert native['horizontal_support_claimed'] is False
        assert native['contact_kind'] == 'static_two_hand_side_clamp'
        assert {c['side'] for c in native['contacts']} == {'L', 'R'}
        for contact in native['contacts']:
            assert contact['native_cargo_gap_m'] <= 2e-6 and contact['native_glove_gap_m'] <= 2e-6
            max_contact = max(max_contact, contact['native_cargo_gap_m'], contact['native_glove_gap_m'])
        assert abs(math.atan2(math.sin(native['yaw_rad']-math.pi/2), math.cos(native['yaw_rad']-math.pi/2))) < 1e-8
        assert scene['holders']['actor_pose']['position'] == [14.86, 0, 44.38]
        assert all(value == [0, 0, -.005] for value in native['thumb_positions'].values())
    else:
        assert native['native_contact_area_sum_m2'] > 1e-8
        assert native['maximum_contact_gap_m'] <= 2e-6
        assert abs(native['actual_bottom_gap_m']) <= 2e-6
        assert native['geometric_centre_inside_support_hull']
        max_contact = max(max_contact, native['maximum_contact_gap_m'])
        if row['kind'] == 'vehicle':
            families.add(hu['archetype_id'])
assert families == {'HEAVY_BOX', 'PALLET_LOAD', 'IBC', 'LONG_BUNDLE', 'DRUM', 'FRAGILE_CRATE'}
assert clearance['executed'] and clearance['overall_clearance_passed']
assert clearance['source_kind'] == 'visual_fixture' and clearance['engine_operation'] is False
current(clearance['input_hashes'])
assert len(clearance['results']) == 28
assert all(not r['proof']['collision_detected'] and not r['proof']['positive_penetration_witnesses'] for r in clearance['results'])
assert review['passed'] and review['reviewer'] == 'root'
assert review['browser_report_sha256'] == sha('assets/v3/iterations/warehouse/W04.3/browser/browser-checks.json')
assert {i['file'] for i in review['images']} == {f['file'] for f in browser['frames']}
for item in review['images']:
    assert item['observation'] and sha('assets/v3/iterations/warehouse/W04.3/browser/' + item['file']) == item['sha256']
print(json.dumps(dict(passed=True, source_kind='visual_fixture', engine_operation=False,
                     holder_poses=10, vehicle_families=6, browser_checks=20, reviewed_images=14,
                     stationary_clearance_cases=28, maximum_native_contact_gap_m=max_contact,
                     scope='Static same-HU holder contacts, ownership and source-bound review. Native penetration witness search is bounded; no strength, dynamic stability, physical action, loaded route or actual engine acceptance.')))
