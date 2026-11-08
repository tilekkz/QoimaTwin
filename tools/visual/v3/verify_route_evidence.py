"""Check current route geometry, scene proof and reviewed images without regenerating them."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/warehouse/W03.3'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(hashes):
    for path, digest in hashes.items():
        assert sha(ROOT / path) == digest, ('Stale route proof', path)


reports = {name: read(ROOT / f'docs/adaptive-v3/evidence/{name}.json')
           for name in ['W03.1-checks', 'W03.1-independent', 'W03.2-checks', 'W03.3-clearance']}
browser = read(BASE / 'browser/browser-checks.json')
review = read(BASE / 'visual-review.json')
for report in [*reports.values(), browser, review]:
    assert report['passed'] and report['source_kind'] == 'visual_fixture' and report['engine_operation'] is False
    current(report.get('input_hashes', {}))
assert reports['W03.1-independent']['original_ID_graph_shortest_routes_checked'] == 78
assert reports['W03.1-independent']['before_cost_negative_cases'] == 31
assert reports['W03.2-checks']['vehicle_arcs'] == 1316
assert reports['W03.2-checks']['dense_curve_samples'] == 109364
clearance = reports['W03.3-clearance']
assert clearance['storage_obstacles'] == 132 and clearance['standing_worker_obstacles'] == 22
assert clearance['clearance_padding_m'] == .25 and clearance['straight_sweep_exact']
assert clearance['inter_sample_displacement_inflation'] and len(clearance['routes']) == 2
assert sum(r['obstacle_pairs'] for r in clearance['routes']) == 505920
assert min(r['minimum_SAT_projection_gap_m'] for r in clearance['routes']) >= .05
assert browser['preview_only'] is False and browser['visible'] is False
assert not browser.get('failure') and not browser['fatal'] and not browser['unexpected']
assert len(browser['checks']) == 25 and all(browser['checks'].values()) and browser['lifecycle']['terminated']
assert browser['native_samples'] == 132
assert browser['maximum_contact_gap_m'] < 2e-6 and browser['maximum_bare_envelope_excess_m'] < 2e-6
assert review['reviewer'] == 'root' and review['browser_report_sha256'] == sha(BASE / 'browser/browser-checks.json')
assert len(review['images']) == len(browser['frames']) == 17
assert {i['file'] for i in review['images']} == {f['file'] for f in browser['frames']}
for item in review['images']:
    assert item['observation'] and sha(BASE / 'browser' / item['file']) == item['sha256']
for frame in browser['frames']:
    state = frame['state']
    if state.get('scene'):
        assert state['scene']['workers'] == 24 and state['scene']['stock_HUs'] == 530
    if state.get('route'):
        assert state['route']['completed_jobs'] == 0 and state['route']['engine_operation'] is False
for task in ['W03.1', 'W03.2', 'W03.3', 'W03']:
    evidence = read(ROOT / f'docs/adaptive-v3/evidence/{task}.json')
    assert evidence['passed'] and evidence['engine_operation'] is False
    current(evidence.get('input_hashes', {}))
    current(evidence.get('artifacts', {}))
    for child in evidence.get('children', {}).values():
        assert sha(ROOT / child['path']) == child['sha256']
print(json.dumps(dict(passed=True, source_kind='visual_fixture', engine_operation=False,
                      route_chains=78, rejected_before_cost=31, analytic_vehicle_arcs=1316,
                      browser_checks=25, reviewed_images=17, native_poses=132,
                      fixed_obstacle_pairs=505920,
                      scope='Canonical geometry and two empty-truck previews only. Cargo, human actions, traffic resources, unified jobs and final Q/H remain separate.')))
