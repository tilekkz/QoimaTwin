"""Check freshness and agreement of the separate bounded SMALL-pick QA gates."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/worker-base/P03.5.3.3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def current(hashes):
    for path, expected in hashes.items():
        assert sha(ROOT / path) == expected, ('Stale evidence', path)


runtime = read(BASE / 'runtime-native-poses.json')
native = read(BASE / 'native-path-checks.json')
browser = read(BASE / 'browser/browser-checks.json')
review = read(BASE / 'visual-review.json')
for report in (runtime, native, browser, review):
    assert report['engine_operation'] is False
current(runtime['input_hashes'])
current(native['native_dependency_sha256'])
current(browser['input_hashes'])
assert native['input_hashes'] == runtime['input_hashes']
assert native['runtime_source_sha256'] == sha(BASE / 'runtime-native-poses.json')
assert native['passed'] and native['failure'] is None
assert runtime['checks']['runtime_frames'] == 3601
assert runtime['checks']['arbitrary_seeks'] == 100
assert runtime['checks']['maximum_joint_angle_change_per_10ms_rad'] < .08
assert runtime['checks']['native_frames_exported'] == len(runtime['frames']) == 557
assert native['actual_native_frames'] == len(native['frames']) == 557
assert [f['time'] for f in native['frames']] == [f['time'] for f in runtime['frames']]
assert sum(f['actual_contact_checks'] for f in native['frames']) == 2928
assert all(f['maximum_contact_gap_m'] < 2e-6 and f['maximum_boot_floor_error_m'] < 2e-6
           and f['central_C_mouth_clear'] and f['source_packages_conserved']
           for f in native['frames'])
assert native['frames'][-1]['actual_tote_support_contacts'] == 2
assert browser.get('failure') is None and not browser['fatal'] and not browser['failedResources']
assert browser['visible'] is False and browser['lifecycle']['terminated']
for key in ['cold_reduced_motion_manual_only', 'same_actor_tool_and_four_package_objects',
            'mobile_360_touch_seek_and_no_page_overflow', 'keyboard_seek',
            'keyboard_view_focus_labels_and_status', 'manual_play_pause',
            'live_reduced_motion_pauses', 'missing_asset_cleanup_recovery',
            'invalid_timeline_cleanup_recovery', 'loading_status_and_disabled_views',
            'stale_load_does_not_resurrect_actor']:
    assert browser['checks'][key] is True, key
assert len({json.dumps(m, sort_keys=True) for m in browser['checks']['replacement_memory']}) == 1
assert review['passed'] and review['reviewer'] == 'root'
assert review['browser_report_sha256'] == sha(BASE / 'browser/browser-checks.json')
assert len(review['images']) >= 16
for image in review['images']:
    assert image['observation'] and sha(BASE / 'browser' / image['file']) == image['sha256']
assert set(f['file'] for f in browser['frames']).issubset({r['file'] for r in review['images']})
print(json.dumps(dict(passed=True, engine_operation=False, runtime_frames=3601,
                      native_frames=557, contacts=2928, reviewed_images=len(review['images']),
                      scope='Current bounded visual fixture QA only; not continuous collision certification or an engine run.')))
