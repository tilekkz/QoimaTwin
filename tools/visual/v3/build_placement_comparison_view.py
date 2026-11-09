"""Expose the existing C11 analytical comparison without promoting it to an engine run."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/v3/contract-proposals'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = BASE / 'handoff/examples/slotting-comparison.json'
    example = json.loads(source.read_bytes())
    assert example['source_kind'] == 'analytical_fixture'
    assert example['engine_operation'] is False and example['operational_admission'] is False
    evidence = ROOT / 'docs/adaptive-v3/evidence/C11-independent.json'
    independent = json.loads(evidence.read_bytes())
    assert independent['passed'] and len(independent['evaluations']) == 4
    refs = {source.relative_to(ROOT).as_posix(): digest(source), evidence.relative_to(ROOT).as_posix(): digest(evidence)}
    for name in ['layout_ref', 'scenario_ref', 'baseline_placement_ref', 'evaluation_ref']:
        ref = example[name]; path = ROOT / ref['path']
        assert digest(path) == ref['sha256'] and path.stat().st_size == ref['bytes']
        refs[ref['path']] = ref['sha256']
    rows = []
    for case, verified in zip(example['cases'], independent['evaluations'], strict=True):
        ref = case['candidate_ref']; candidate_path = ROOT / ref['path']
        assert digest(candidate_path) == ref['sha256'] and candidate_path.stat().st_size == ref['bytes']
        candidate = json.loads(candidate_path.read_bytes()); summary = candidate['summary']
        assert verified['passed'] and verified['horizon_periods'] == case['horizon_periods']
        assert candidate['actual_engine_run'] is False and candidate['operational_admission'] is False
        assert candidate['comparison_inputs_sha256'] == candidate['baseline_comparison_inputs_sha256'] == candidate['adapted_comparison_inputs_sha256'] == case['comparison_inputs_sha256']
        assert len({r['handling_unit_id'] for r in candidate['assignments']}) == 530
        for pin in candidate['source_fingerprints']:
            assert digest(ROOT / pin['path']) == pin['sha256']; refs[pin['path']] = pin['sha256']
        expected = dict(baseline_proxy_cost_s=summary['baseline_under_same_shifted_flow_cost_s'], adapted_proxy_cost_s=summary['adapted_under_same_shifted_flow_cost_s'], relocation_proxy_cost_s=summary['one_off_relocation_cost_s'], net_proxy_saving_s=summary['net_transport_cost_reduction_s'], transfer_count=summary['relocation_count'])
        for key, value in expected.items():
            assert math.isclose(value, case[key], rel_tol=1e-12, abs_tol=1e-7)
        assert math.isclose(expected['baseline_proxy_cost_s']-expected['adapted_proxy_cost_s']-expected['relocation_proxy_cost_s'], expected['net_proxy_saving_s'], abs_tol=1e-7)
        refs[ref['path']] = ref['sha256']
        rows.append(dict(horizon_periods=case['horizon_periods'], comparison_inputs_sha256=case['comparison_inputs_sha256'], **expected))
    result = dict(schema_id='qoima.placement-comparison-view.v1', source_kind='analytical_fixture', engine_operation=False, operational_admission=False, default_horizon_periods=1, headcount=24, handling_units=530, queues_modelled=False, period_is_hours=False, cost_assumptions=candidate['cost_assumptions'], cases=rows, source_hashes=refs)
    target = ROOT / 'frontend/public/data/v3/placement-comparison.json'
    raw = (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    target.write_bytes(raw)
    binding = dict(url='data/v3/placement-comparison.json', sha256=hashlib.sha256(raw).hexdigest())
    (ROOT / 'frontend/src/adaptive-v3/twin/twinPlacementComparisonBinding.json').write_text(json.dumps(binding, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, cases=len(rows), source_pins=len(refs), **binding)))


if __name__ == '__main__':
    build()
