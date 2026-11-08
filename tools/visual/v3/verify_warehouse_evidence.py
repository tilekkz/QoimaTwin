"""Check current W01/W02 source agreement without launching a browser or regenerating proof."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/warehouse/W02.2'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(hashes):
    for path, digest in hashes.items():
        assert sha(ROOT / path) == digest, ('Stale warehouse proof', path)


w01 = read(ROOT / 'docs/adaptive-v3/evidence/W01-checks.json')
adapter = read(ROOT / 'docs/adaptive-v3/evidence/W02.1-checks.json')
browser = read(BASE / 'browser/browser-checks.json')
review = read(BASE / 'visual-review.json')
for report in [w01, adapter, browser, review]:
    assert report['passed'] and report['source_kind'] == 'visual_fixture' and report['engine_operation'] is False
for report in [w01, adapter, browser]:
    current(report['input_hashes'])
assert w01['initial_HUs_checked'] == adapter['full_stock_HUs'] == 530
assert len(w01['negatives']) == 21 and len(adapter['negatives']) == 28
assert all(n['rejected'] for n in w01['negatives'] + adapter['negatives'])
assert adapter['walk_arcs'] == 4000 and adapter['vehicle_arcs'] == 1316
assert browser['preview_only'] is False and browser['visible'] is False
assert not browser.get('failure') and not browser['fatal'] and not browser['unexpected']
assert len(browser['checks']) == 20 and all(browser['checks'].values())
assert browser['lifecycle']['terminated']
assert review['reviewer'] == 'root' and review['browser_report_sha256'] == sha(BASE / 'browser/browser-checks.json')
assert len(review['images']) == len(browser['frames']) == 20
assert {i['file'] for i in review['images']} == {f['file'] for f in browser['frames']}
for i in review['images']:
    assert i['observation'] and sha(BASE / 'browser' / i['file']) == i['sha256']
bindings = read(ROOT / 'frontend/src/adaptive-v3/warehouseAssetBindings.json')
assert len(bindings) == 21  # 20 accepted GLBs and one accepted seated pose.
for name, item in bindings.items():
    path = ROOT / 'frontend/public' / (item['path'] if name == 'seated-driver-pose' else f'models/v3/{name}.glb')
    assert sha(path) == item['sha256']
for task in ['W01', 'W02.1', 'W02.2', 'W02']:
    evidence = read(ROOT / f'docs/adaptive-v3/evidence/{task}.json')
    assert evidence['passed'] and evidence['engine_operation'] is False
    current(evidence.get('input_hashes', {}))
    current(evidence.get('artifacts', {}))
    for child in evidence.get('children', {}).values():
        assert sha(ROOT / child['path']) == child['sha256']
print(json.dumps(dict(passed=True, engine_operation=False, initial_HUs=530, workers=24,
                      decoded_arcs=5316, negative_cases=49, reviewed_images=20,
                      scope='Registered source-bound initial visual warehouse and loading/recovery only; W03+ movement/cargo/action execution, final composition, scenarios/Q/H and backend remain separate.')))
