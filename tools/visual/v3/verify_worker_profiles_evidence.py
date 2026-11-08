"""Check existing skill/profile proofs against current bytes; never regenerate evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/worker-profiles'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(hashes):
    for path, digest in hashes.items():
        assert sha(ROOT / path) == digest, ('Stale worker profiles evidence', path)


profiles = read(ROOT / 'frontend/public/data/v3/worker-profiles-v3.json')
registry = read(ROOT / profiles['registry_ref']['path'])
definitions = read(BASE / 'P11.1/profile-checks.json')
capability = read(BASE / 'P11.2/capability-checks.json')
browser = read(BASE / 'P11.3/browser/browser-checks.json')
review = read(BASE / 'P11.3/visual-review.json')
for report in [profiles, definitions, capability, browser, review]:
    assert report['source_kind'] == 'visual_fixture' and report['engine_operation'] is False
for report in [definitions, capability, browser]:
    assert report['passed']
    current(report['input_hashes'])
current(profiles['source_hashes'])
assert sha(ROOT / profiles['registry_ref']['path']) == profiles['registry_ref']['sha256']
assert [p['worker_id'] for p in profiles['profiles']] == [w['actor_id'] for w in registry['workers']]
assert profiles['worker_count'] == definitions['profile_count'] == 24
assert definitions['negative_mutations_rejected'] == 23
assert profiles['cross_trained_worker_ids'] == ['P01', 'P02']
assert profiles['operational_admission'] is False
for p in profiles['profiles']:
    assert p['initial_role'] == p['baseline_role']
    assert not any(k in p for k in ['current_role', 'initial_pos', 'world_pos'])
assert all(capability['checks'].values())
assert len(capability['role_matrix']) == 120
assert len(capability['vehicle_matrix']) == 48
assert len(capability['manual_boundary_cases']) == 44
assert len(capability['explicit_cases']) == 28
assert browser['preview_only'] is False and browser['visible'] is False
assert not browser.get('failure') and not browser['fatal'] and not browser['unexpected']
assert len(browser['checks']) == 15 and all(browser['checks'].values())
assert browser['lifecycle']['terminated']
assert review['passed'] and review['reviewer'] == 'root'
assert review['browser_report_sha256'] == sha(BASE / 'P11.3/browser/browser-checks.json')
assert len(review['images']) == len(browser['frames']) == 16
assert {i['file'] for i in review['images']} == {f['file'] for f in browser['frames']}
for image in review['images']:
    assert image['observation'] and sha(BASE / 'P11.3/browser' / image['file']) == image['sha256']
for task in ['P11.1', 'P11.2', 'P11.3', 'P11']:
    evidence = read(ROOT / f'docs/adaptive-v3/evidence/{task}.json')
    assert evidence['passed'] and evidence['engine_operation'] is False
    current(evidence.get('input_hashes', {}))
    current(evidence.get('artifacts', {}))
    for child in evidence.get('children', {}).values():
        assert sha(ROOT / child['path']) == child['sha256']
print(json.dumps(dict(passed=True, engine_operation=False, profiles=24,
                      profile_negative_cases=23, capability_cases=240, reviewed_images=16,
                      scope='Declared synthetic visual capabilities and read-only inspector; independent cargo/physical/route/resource admission and W role events still required.')))
