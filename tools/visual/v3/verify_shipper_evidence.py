"""Check current bounded shipper geometry/runtime/UI/review agreement without rebuilding."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'assets/v3/iterations/shipper'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def current(hashes):
    for p,h in hashes.items():assert sha(ROOT/p)==h,('Stale shipper proof',p)

r=read(BASE/'P06.2/runtime-native-poses.json');n=read(BASE/'P06.2/native-path-checks.json');b=read(BASE/'P06.3/browser/browser-checks.json');v=read(BASE/'P06.3/visual-review.json');stance=read(BASE/'P06.2/stance-checks.json')
for report in [r,n,b,v,stance]:assert report['engine_operation'] is False
for report in [r,n,b]:current(report['input_hashes'])
assert n['passed'] and n['failure'] is None
assert n['runtime_pose_sha256']==stance['runtime_pose_sha256']==sha(BASE/'P06.2/runtime-native-poses.json')
assert r['checks']['runtime_frames']==2954 and r['checks']['arbitrary_seeks']==100 and r['checks']['rigid_world_transforms']==3
assert r['checks']['maximum_joint_step_per_10ms_rad']<.08
assert len(r['frames'])==len(n['frames'])==n['native_frames']==594
assert [(f['mode'],f['time']) for f in r['frames']]==[(f['mode'],f['time']) for f in n['frames']]
assert sum(f['opposed_parcel_contact'] for f in n['frames'])==161
assert sum(f['parcel_actual_support_rays'] for f in n['frames'])==5346
assert sum(f['connections'] for f in n['frames'])==4752
assert sum(f['C_mouth_gauges'] for f in n['frames'])==1188
assert all(f['maximum_stance_boot_floor_error_m']<2e-6 and min(f['boot_floor_heights_m'])>=-2e-6 and f['heavy_pallet_unmoved'] and (f['contact_gap_m'] is None or f['contact_gap_m']<2e-6) for f in n['frames'])
base={f['side']:f['world'] for f in r['frames'][0]['state']['actualFeet']};previous={};maximum_error=maximum_slip=0
for f in r['frames']:
    for foot in f['state']['actualFeet']:
        side=foot['side'];p=foot['world'];target=foot['target'];expected=[base[side][0],target['lift'],base[side][2]-target['travel']]
        maximum_error=max(maximum_error,math.dist(p,expected));key=(f['mode'],side)
        if key in previous and target['stance'] and previous[key]['target']['stance']:maximum_slip=max(maximum_slip,math.dist(p,previous[key]['world']))
        previous[key]=foot
    assert not f['state']['scanning'] or f['state']['displacement_m']==0
    if f['mode']=='place' and f['time']>=11.4:assert f['state']['displacement_m']==.16
    if f['mode']=='place' and f['time']>=23:assert abs(f['state']['body_distance_m'])<1e-12
assert maximum_error<2e-6 and maximum_slip<2e-6
assert stance['passed'] and abs(stance['maximum_absolute_sole_anchor_target_error_m']-maximum_error)<1e-12 and abs(stance['maximum_consecutive_stance_slip_m']-maximum_slip)<1e-12
assert b.get('failure') is None and not b['fatal'] and not b['failed_resources'] and b['preview_only'] is False
assert b['visible'] is False and b['lifecycle']['terminated']
for key in ['cold_reduced_motion_no_autoplay','same_actor_package_pallet_and_24_content_frames','scan_place_idle_blocked_distinct','inward_rest_palms','mobile_360_touch_modes_seek_and_no_overflow','keyboard_range_view_focus_and_semantic_status','manual_play_pause_and_live_reduced_motion','missing_asset_cleanup_recovery','invalid_timeline_cleanup_recovery','loading_status_and_disabled_views','stale_load_no_actor_resurrection']:assert b['checks'][key] is True,key
assert len({json.dumps(x,sort_keys=True) for x in b['checks']['replacement_peak_memory']})==1
assert v['passed'] and v['reviewer']=='root' and v['browser_report_sha256']==sha(BASE/'P06.3/browser/browser-checks.json')
assert len(v['images'])==24
assert {f['file'] for f in b['frames']}.issubset({f['file'] for f in v['images']})
for f in v['images']:assert f['observation'] and sha(BASE/'P06.3/browser'/f['file'])==f['sha256']
print(json.dumps(dict(passed=True,engine_operation=False,runtime_frames=2954,native_frames=594,actual_parcel_contacts=161,actual_parcel_support_rays=5346,maximum_stance_slip_m=maximum_slip,reviewed_images=24,scope='Current bounded prepared shipper visual fixture, no actual inventory shipment, decoder or whole-warehouse claim.')))
