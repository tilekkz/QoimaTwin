"""Freshness/agreement gate for the accepted bounded receiver visual fixture."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'assets/v3/iterations/receiver'
def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def current(hashes):
    for path,expected in hashes.items():assert sha(ROOT/path)==expected,('Stale receiver evidence',path)

runtime=read(BASE/'P05.2/runtime-native-poses.json');native=read(BASE/'P05.2/native-path-checks.json');browser=read(BASE/'P05.3/browser/browser-checks.json');review=read(BASE/'P05.3/visual-review.json')
for report in [runtime,native,browser,review]:assert report['engine_operation'] is False
current(runtime['input_hashes']);current(native['input_hashes']);current(browser['input_hashes'])
assert native['passed'] and native['failure'] is None and native['proposed_layout'] is None
assert native['runtime_pose_sha256']==sha(BASE/'P05.2/runtime-native-poses.json')
assert runtime['checks']['runtime_frames']==2034 and runtime['checks']['arbitrary_seeks']==100
assert runtime['checks']['maximum_joint_step_per_10ms_rad']<.08
assert len(runtime['frames'])==native['native_frames']==len(native['frames'])==410
assert [(f['mode'],f['time']) for f in native['frames']]==[(f['mode'],f['time']) for f in runtime['frames']]
assert sum(f['opposed_terminal_contact'] for f in native['frames'])==41
assert sum(f['C_mouth_gauges'] for f in native['frames'])==820
assert sum(f['connections'] for f in native['frames'])==3280
assert all(f['maximum_boot_floor_error_m']<2e-6 and f['scan_line_clear'] and (f['contact_gap_m'] is None or f['contact_gap_m']<2e-6) for f in native['frames'])
assert browser.get('failure') is None and not browser['fatal'] and not browser['failed_resources'] and browser['preview_only'] is False
assert browser['visible'] is False and browser['lifecycle']['terminated']
for key in ['cold_reduced_motion_no_autoplay','same_actor_HU_and_24_content_frames','scan_receive_idle_blocked_distinct','inward_rest_palms','mobile_360_touch_modes_seek_and_no_overflow','keyboard_range_view_focus_and_semantic_status','manual_play_pause_and_live_reduced_motion','missing_asset_cleanup_recovery','invalid_timeline_cleanup_recovery','loading_status_and_disabled_views','stale_load_no_actor_resurrection']:assert browser['checks'][key] is True,key
assert len({json.dumps(x,sort_keys=True) for x in browser['checks']['replacement_peak_memory']})==1
assert review['passed'] and review['reviewer']=='root' and review['browser_report_sha256']==sha(BASE/'P05.3/browser/browser-checks.json')
assert len(review['images'])==17
assert {f['file'] for f in browser['frames']}.issubset({f['file'] for f in review['images']})
for f in review['images']:assert f['observation'] and sha(BASE/'P05.3/browser'/f['file'])==f['sha256']
print(json.dumps(dict(passed=True,engine_operation=False,runtime_frames=2034,native_frames=410,terminal_contacts=41,reviewed_images=17,scope='Current bounded receiver visual fixture only; no actual barcode decoding, inventory receipt or complete warehouse claim.')))
