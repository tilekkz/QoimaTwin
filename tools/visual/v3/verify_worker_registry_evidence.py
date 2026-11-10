"""Current-source agreement for the canonical24 visual role catalogue."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'assets/v3/iterations/worker-registry'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def current(hashes):
    for p,h in hashes.items():assert sha(ROOT/p)==h,('Stale worker registry proof',p)
r=read(BASE/'P10.1/registry-checks.json');b=read(BASE/'P10.3/browser/browser-checks.json');v=read(BASE/'P10.3/visual-review.json');d=read(ROOT/'frontend/public/data/v3/worker-registry-v3.json');canonical=read(ROOT/'contracts/actors.example.json')
for report in [r,b,v,d]:assert report['engine_operation'] is False
current(r['input_hashes']);current(b['input_hashes']);current(d['source_hashes'])
assert r['passed'] and r['canonical_actor_count']==24 and r['clips']==16 and r['worker_clip_links']==74 and r['negative_mutations_rejected']==23
assert [(w['actor_id'],w['baseline_role']) for w in d['workers']]==[(a['actor_id'],a['role']) for a in canonical['actors']]
assert len({w['actor_id'] for w in d['workers']})==24 and 'PK01' not in [w['actor_id'] for w in d['workers']]
assert d['vehicles']==[dict(vehicle_id=v['vehicle_id'],driver_actor_id=v['driver_actor_id']) for v in canonical['vehicles']]
for c in d['clips']:
    assert c['warehouse_joined'] is False
    for ref in [c['proof'],*c['sources']]:assert sha(ROOT/ref['path'])==ref['sha256']
assert b['passed'] and b['preview_only'] is False and b.get('failure') is None and not b['fatal'] and not b['unexpected'] and b['visible'] is False and b['lifecycle']['terminated']
for k in ['canonical24_and_color_badge_label_legend','keyboard_search_empty_clear_focus','role_filter_vehicle_pairs_and_clip_links','URL_query_restored_on_reload','mobile_360_touch_and_no_overflow','failed_refresh_keeps_query_rows_expansion_and_recovers','offline_loaded_search_and_recovery','not_found_and_invalid_package_states','first_error_retry_keyboard_recovery','delayed_loading_status_and_control_feedback','latest_reload_wins','bounded_timeout_keeps_data_and_recovers','repeat_back_navigation_and_reload','no_unrequested_3D_asset_loading']:assert b['checks'][k] is True,k
assert v['passed'] and v['reviewer']=='root' and v['browser_report_sha256']==sha(BASE/'P10.3/browser/browser-checks.json')
assert len(v['images'])==len(b['frames'])==12 and {i['file'] for i in v['images']}=={f['file'] for f in b['frames']}
for i in v['images']:assert i['observation'] and sha(BASE/'P10.3/browser'/i['file'])==i['sha256']
print(json.dumps(dict(passed=True,engine_operation=False,canonical_actors=24,roles=5,accepted_clips=16,worker_clip_links=74,negative_mutations=23,reviewed_images=12,scope='Current local visual role/clip registry and read-only catalogue only; skills, warehouse assignments/joins and actual backend operation remain separate.')))
