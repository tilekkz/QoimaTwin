"""Check current single-owner storage binding/native support proofs without launching a browser."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'assets/v3/iterations/warehouse/W04.2'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(hashes):
    for path,digest in hashes.items():
        assert sha(ROOT/path)==digest,('Stale cargo evidence',path)


state=read(ROOT/'docs/adaptive-v3/evidence/W04.1-checks.json')
independent=read(ROOT/'docs/adaptive-v3/evidence/W04.1-independent.json')
calibrations=read(ROOT/'docs/adaptive-v3/evidence/W04.2-geometry-calibrations.json')
browser=read(BASE/'browser/browser-checks.json')
review=read(BASE/'visual-review.json')
for report in [state,independent,calibrations,browser,review]:
    assert report['passed'] and report['source_kind']=='visual_fixture' and report['engine_operation'] is False
    current(report.get('input_hashes',{}))
assert state['initial_HUs']==independent['independently_checked_initial_HUs']==530
assert len(state['negative_cases'])==24 and all(c['rejected'] for c in state['negative_cases'])
assert len(state['compatible_free_relocations'])==independent['independently_checked_free_relocations']==8
assert calibrations['geometry_calibrations']==14 and all(c['passed'] for c in calibrations['tests'])
assert calibrations['source_unchanged_during_check'] and calibrations['browser_launched'] is False
assert len(browser['checks'])==12 and all(browser['checks'].values())
assert browser['visible'] is False and browser['lifecycle']['terminated'] and not browser.get('failure')
assert not browser['native_failures'] and not browser['fatal'] and not browser['unexpected']
assert len(browser['initial_native'])==530 and len(browser['relocations'])==8 and len(browser['negative_cases'])==9
assert browser['maximum_dimension_error_m']<=2e-6 and browser['maximum_local_bound_error_m']<=2e-6
assert browser['maximum_bottom_gap_m']<=2e-6 and browser['maximum_contact_gap_m']<=2e-6
assert review['reviewer']=='root' and review['browser_report_sha256']==sha(BASE/'browser/browser-checks.json')
assert len(review['images'])==len(browser['frames'])==11
assert {i['file'] for i in review['images']}=={f['file'] for f in browser['frames']}
for item in review['images']:
    assert item['observation'] and sha(BASE/'browser'/item['file'])==item['sha256']
for task in ['W04.1','W04.2']:
    evidence=read(ROOT/f'docs/adaptive-v3/evidence/{task}.json')
    assert evidence['passed'] and evidence['engine_operation'] is False
    current(evidence.get('input_hashes',{}));current(evidence.get('artifacts',{}))
print(json.dumps(dict(passed=True,source_kind='visual_fixture',engine_operation=False,
                     native_HUs=530,storage_negative_cases=24,browser_negative_cases=9,
                     family_relocations=8,browser_checks=12,reviewed_images=11,
                     scope='Current one-owner shared storage instances/native horizontal contact and footprint-centre proxy. Carrier holders, physical transfers and jobs remain W04.3/W05.')))
