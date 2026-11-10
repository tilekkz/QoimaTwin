"""C12 offline validation of the additive, source-labelled proposal handoff."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/v3/contract-proposals/handoff'
LAYOUT = 'docs/v3/contract-proposals/layout-manifest-v3.json'
POLICY = 'docs/v3/contract-proposals/port-resource-policy-v3.json'


def require(condition, reason):
    if not condition: raise ValueError(reason)


def finite(value):
    if isinstance(value, float): require(math.isfinite(value), 'NONFINITE_NUMBER')
    elif isinstance(value, dict):
        for child in value.values(): finite(child)
    elif isinstance(value, list):
        for child in value: finite(child)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def read(path):
    def invalid_constant(value): raise ValueError('NONFINITE_NUMBER ' + value)
    data = json.loads(Path(path).read_text(encoding='utf8'), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    finite(data)
    return data


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_ref(reference):
    path = reference.get('path', '')
    require(isinstance(path, str) and '\\' not in path and ':' not in path and not path.startswith('/'), 'INVALID_REPOSITORY_PATH')
    resolved = (ROOT / path).resolve()
    require(resolved.is_relative_to(ROOT.resolve()), 'OUTSIDE_REPOSITORY')
    require(resolved.is_file(), 'MISSING_ARTIFACT')
    require(digest(resolved) == reference.get('sha256'), 'ARTIFACT_HASH_MISMATCH')
    require(resolved.stat().st_size == reference.get('bytes'), 'ARTIFACT_BYTES_MISMATCH')
    return resolved


def read_ref(reference):
    return read(resolve_ref(reference))


def no_network(uri):
    raise NoSuchResource(ref=uri)


def validators():
    paths = sorted((BASE / 'schemas').glob('*.schema.json')) + [
        ROOT / 'docs/v3/contract-proposals/cargo-archetype-v3.schema.json',
        ROOT / 'docs/v3/contract-proposals/storage-slot-v3.schema.json']
    schemas = [read(p) for p in paths]
    for s in schemas: Draft202012Validator.check_schema(s)
    require(len({s['$id'] for s in schemas}) == len(schemas), 'DUPLICATE_SCHEMA_ID')
    registry = Registry(retrieve=no_network).with_resources((s['$id'], Resource.from_contents(s)) for s in schemas)
    return {p.stem.replace('.schema', ''): Draft202012Validator(s, registry=registry) for p, s in zip(paths, schemas)}


def shape(data, validator):
    finite(data)
    errors = list(validator.iter_errors(data))
    if errors:
        e = sorted(errors, key=lambda e: list(map(str, e.path)))[0]
        raise ValueError('SCHEMA_FIELD_ERROR /' + '/'.join(map(str, e.path)) + ': ' + e.message[:180])


def validate_layout_binding(data):
    layout = read_ref(data['layout_ref'])
    require(data['layout_ref']['path'] == LAYOUT, 'WRONG_LAYOUT_REFERENCE')
    require(layout['layout_version'] == 'qoima-144x72-v3-proposal', 'WRONG_LAYOUT_VERSION')
    require(data['layout_content_hash'] == layout['layout_content_hash'], 'LAYOUT_BINDING_MISMATCH')
    require(layout['envelope']['bounds'] == {'min': [0, 0, 0], 'max': [144, 8, 72]}, 'ENVELOPE_CHANGED')
    return layout


def validate_source(data, vv):
    require(data.get('source_kind') != 'actual_engine_run', 'ACTUAL_V3_UNSUPPORTED')
    shape(data, vv['source-labelled-input'])
    validate_layout_binding(data)
    supported_paths = {'visual_fixture': 'frontend/public/data/v3/packer-seam-end.json',
                       'geometry_proposal': 'frontend/public/data/adaptive-v3/layout-manifest.json',
                       'analytical_fixture': 'docs/v3/contract-proposals/adapted-assignment-v3.json'}
    require(data['payload_ref']['path'] == supported_paths[data['source_kind']], 'UNSUPPORTED_PAYLOAD_REFERENCE')
    payload = read_ref(data['payload_ref'])
    require(payload.get('schema_id') == data['payload_schema_id'], 'PAYLOAD_NAMESPACE_MISMATCH')
    if data['source_kind'] == 'visual_fixture':
        require(payload.get('source_kind') == 'visual_fixture' and payload.get('engine_operation') is False, 'PAYLOAD_SOURCE_CONFLICT')
        require(payload['duration_s'] == data['clock']['duration_s'], 'CLOCK_MISMATCH')
    elif data['source_kind'] == 'analytical_fixture':
        require(payload.get('source_kind') == 'synthetic_planning_fixture' and payload.get('actual_engine_run') is False and payload.get('operational_admission') is False, 'PAYLOAD_SOURCE_CONFLICT')
        require(payload['summary']['evaluation_horizon_periods'] == data['clock']['horizon_periods'], 'CLOCK_MISMATCH')
    else:
        require(payload.get('data_kind') == 'geometry_proposal' and payload.get('backend_integration_complete') is False and payload.get('scheduling_implemented') is False, 'PAYLOAD_SOURCE_CONFLICT')
        require(payload['layout_content_hash'] == data['layout_content_hash'], 'LAYOUT_BINDING_MISMATCH')


def validate_ports(data, vv):
    shape(data, vv['port-view']); validate_layout_binding(data)
    policy = read_ref(data['resource_policy_ref'])
    require(data['resource_policy_ref']['path'] == POLICY and policy['actor_count'] == 24, 'RESOURCE_POLICY_MISMATCH')
    ids = [p['port_id'] for p in data['ports']]
    require(len(set(ids)) == 6, 'DUPLICATE_PORT_ID')
    for p in data['ports']:
        require(sum(abs(v) for v in p['outward_normal']) == 1 and p['outward_normal'][1] == 0, 'PORT_NORMAL_CONFLICT')
        require(p['inward_facing'] == [-v for v in p['outward_normal']], 'PORT_NORMAL_CONFLICT')
        require(p['world_pos'][1] == 0 and (p['world_pos'][0] in [0, 144] or p['world_pos'][2] in [0, 72]), 'PORT_BOUNDARY_CONFLICT')
        expected_path = 'docs/v3/contract-proposals/ports-v3.' + p['direction'] + '.json'
        require(p['source_ref']['path'] == expected_path, 'PORT_SOURCE_REFERENCE_INVALID')
        source = read_ref(p['source_ref'])['ports'][p['source_port_index']]
        for k in ['port_id', 'direction', 'world_pos', 'outward_normal', 'inward_facing', 'service_node_id', 'service_node_world_pos', 'allowed_cargo_archetype_ids', 'clear_width_m', 'clear_height_m']:
            require(p[k] == source[k], 'PORT_SOURCE_MISMATCH ' + k)


def validate_worker(data, vv):
    shape(data, vv['worker-profile'])
    registry = read_ref(data['registry_ref'])
    require(data['registry_ref']['path'] == 'contracts/actors.example.json', 'WRONG_ACTOR_REGISTRY')
    actors = {a['actor_id']: a for a in registry['actors']}
    require(len(registry['actors']) == len(actors) == 24, 'ACTOR_IDENTITY_COUNT_MISMATCH')
    require(data['worker_id'] in actors, 'UNKNOWN_WORKER_ID')
    actor = actors[data['worker_id']]
    require(data['baseline_role'] == actor['role'], 'BASELINE_ROLE_MISMATCH')
    require(data['current_role'] in data['allowed_roles'] and data['baseline_role'] in data['allowed_roles'], 'ROLE_NOT_ALLOWED')
    require(set(data['skill_levels']) == set(data['allowed_roles']), 'SKILL_ROLE_MISMATCH')
    if 'forklift_driver' in data['allowed_roles']:
        require(actor['role'] == 'forklift_driver' and actor.get('vehicle_id'), 'FORKLIFT_QUALIFICATION_UNDECLARED')
        require(data['allowed_vehicle_ids'] == [actor['vehicle_id']], 'VEHICLE_QUALIFICATION_MISMATCH')


def compare_stock(base, candidate):
    fields = ['handling_unit_id', 'sku_id', 'lot_id', 'archetype_id', 'quantity_units', 'model_scale_factor', 'orientation_id']
    identity = lambda rows: sorted(tuple(a[k] for k in fields) for a in rows)
    require(identity(base['assignments']) == identity(candidate['assignments']), 'STOCK_IDENTITY_MISMATCH')
    require(len(candidate['assignments']) == len({a['handling_unit_id'] for a in candidate['assignments']}) == 530, 'HU_IDENTITY_COUNT_MISMATCH')
    require(len({a['slot_id'] for a in candidate['assignments']}) == 530, 'DUPLICATE_OCCUPIED_SLOT')


def validate_comparison(data, vv):
    shape(data, vv['slotting-comparison']); validate_layout_binding(data)
    scenario = read_ref(data['scenario_ref']); evaluation = read_ref(data['evaluation_ref']); base = read_ref(data['baseline_placement_ref'])
    require(data['baseline_placement_ref']['path'] == 'docs/v3/contract-proposals/baseline-assignment-v3.json' and data['baseline_placement_ref']['sha256'] == scenario['baseline_assignment_sha256'], 'BASELINE_REFERENCE_MISMATCH')
    require(data['scenario_ref']['path'] == 'docs/v3/contract-proposals/adaptation-input-v3.json' and data['evaluation_ref']['path'] == 'docs/v3/contract-proposals/adaptation-evaluation-v3.json', 'SCENARIO_REFERENCE_MISMATCH')
    require(scenario.get('actual_engine_run') is False and scenario['operational_admission'] is False, 'SCENARIO_SOURCE_CONFLICT')
    require(data['scenario_ref']['sha256'] == evaluation['frozen_inputs_sha256'], 'FROZEN_SCENARIO_MISMATCH')
    require([c['horizon_periods'] for c in data['cases']] == evaluation['horizons_periods'] == [1, 2, 4, 8], 'HORIZON_SET_MISMATCH')
    for c in data['cases']:
        expected_path = 'docs/v3/contract-proposals/' + ('adapted-assignment-v3.json' if c['horizon_periods'] == 1 else f'adapted-assignment-horizon{c["horizon_periods"]}-v3.json')
        require(c['candidate_ref']['path'] == expected_path, 'CANDIDATE_REFERENCE_MISMATCH')
        result = read_ref(c['candidate_ref']); s = result['summary']
        require(result['actual_engine_run'] is False and result['operational_admission'] is False, 'CANDIDATE_SOURCE_CONFLICT')
        require(result['baseline_comparison_inputs_sha256'] == result['adapted_comparison_inputs_sha256'] == result['comparison_inputs_sha256'] == c['comparison_inputs_sha256'], 'UNEQUAL_COMPARISON_INPUTS')
        require(result['inventory_sha256'] == result['baseline_inventory_sha256'], 'STOCK_IDENTITY_MISMATCH')
        compare_stock(base, result)
        require(result['staffing'] == {'allocation_changes_allowed': False, 'availability_simulated': False, 'headcount': 24}, 'STAFFING_CHANGED')
        require(c['horizon_periods'] == s['evaluation_horizon_periods'], 'COMPARISON_HORIZON_MISMATCH')
        values = {'baseline_proxy_cost_s': 'baseline_under_same_shifted_flow_cost_s', 'adapted_proxy_cost_s': 'adapted_under_same_shifted_flow_cost_s',
                  'relocation_proxy_cost_s': 'one_off_relocation_cost_s', 'net_proxy_saving_s': 'net_transport_cost_reduction_s', 'transfer_count': 'relocation_count'}
        for a, b in values.items(): require(c[a] == s[b], 'COST_SOURCE_MISMATCH ' + a)
        require(math.isclose(c['baseline_proxy_cost_s'] - c['adapted_proxy_cost_s'] - c['relocation_proxy_cost_s'], c['net_proxy_saving_s'], abs_tol=1e-7), 'NET_COST_ARITHMETIC')
        require(c['transfer_count'] == len(result['transfers']), 'TRANSFER_COUNT_MISMATCH')
    require(data['cases'][0]['transfer_count'] == 0 and data['cases'][0]['net_proxy_saving_s'] == 0, 'DEFAULT_NO_OP_LOST')


def negative_cases(examples, vv):
    cases = []
    def reject(name, original, mutate, validate, expected):
        bad = copy.deepcopy(original); mutate(bad)
        try: validate(bad)
        except ValueError as e:
            require(expected in str(e), 'WRONG_REJECTION ' + name + ': ' + str(e))
            cases.append(dict(case=name, passed=True, reason=expected)); return
        raise AssertionError('INVALID_ACCEPTED ' + name)
    source = examples['visual_fixture-input']; worker = examples['worker-P01']; ports = examples['ports-view']; comparison = examples['slotting-comparison']
    reject('actual_kind_cannot_promote_visual_fixture', source, lambda d: d.update(source_kind='actual_engine_run'), lambda d: validate_source(d, vv), 'ACTUAL_V3_UNSUPPORTED')
    reject('engine_flag_conflicts_with_fixture', source, lambda d: d.update(engine_operation=True), lambda d: validate_source(d, vv), 'SCHEMA_FIELD_ERROR')
    reject('unknown_schema_version', source, lambda d: d.update(schema_version='9.0.0'), lambda d: validate_source(d, vv), 'SCHEMA_FIELD_ERROR')
    reject('wrong_layout_hash', source, lambda d: d.update(layout_content_hash='0' * 64), lambda d: validate_source(d, vv), 'LAYOUT_BINDING_MISMATCH')
    reject('changed_payload_bytes', source, lambda d: d['payload_ref'].update(sha256='0' * 64), lambda d: validate_source(d, vv), 'ARTIFACT_HASH_MISMATCH')
    reject('unregistered_payload_reference', source, lambda d: d.update(payload_ref=examples['geometry_proposal-input']['payload_ref']), lambda d: validate_source(d, vv), 'UNSUPPORTED_PAYLOAD_REFERENCE')
    reject('wrong_visual_clock', source, lambda d: d['clock'].update(duration_s=30), lambda d: validate_source(d, vv), 'CLOCK_MISMATCH')
    reject('analytical_period_is_not_elapsed_clock', examples['analytical_fixture-input'], lambda d: d.update(clock={'kind': 'absolute_visual_seconds', 'duration_s': 28800}), lambda d: validate_source(d, vv), 'SCHEMA_FIELD_ERROR')
    reject('unknown_or_cloned_worker', worker, lambda d: d.update(worker_id='P99'), lambda d: validate_worker(d, vv), 'UNKNOWN_WORKER_ID')
    reject('role_outside_capabilities', worker, lambda d: d.update(current_role='shipper'), lambda d: validate_worker(d, vv), 'ROLE_NOT_ALLOWED')
    reject('skill_missing_for_allowed_role', worker, lambda d: d['skill_levels'].pop('packer'), lambda d: validate_worker(d, vv), 'SKILL_ROLE_MISMATCH')
    def false_driver(d):
        d['allowed_roles'].append('forklift_driver'); d['skill_levels']['forklift_driver'] = 1; d['allowed_vehicle_ids'] = ['FL01']
    reject('picker_not_automatically_a_forklift_driver', worker, false_driver, lambda d: validate_worker(d, vv), 'FORKLIFT_QUALIFICATION_UNDECLARED')
    reject('wrong_driver_vehicle', examples['worker-F01'], lambda d: d.update(allowed_vehicle_ids=['FL02']), lambda d: validate_worker(d, vv), 'VEHICLE_QUALIFICATION_MISMATCH')
    reject('nonfinite_speed', worker, lambda d: d.update(walk_speed_m_s=float('nan')), lambda d: validate_worker(d, vv), 'NONFINITE_NUMBER')
    reject('port_normal_conflict', ports, lambda d: d['ports'][0].update(outward_normal=[1, 0, 0]), lambda d: validate_ports(d, vv), 'PORT_NORMAL_CONFLICT')
    reject('duplicate_port_identity', ports, lambda d: d['ports'][1].update(port_id=d['ports'][0]['port_id']), lambda d: validate_ports(d, vv), 'DUPLICATE_PORT_ID')
    reject('port_bound_to_opposite_source_document', ports, lambda d: d['ports'][0].update(source_ref=d['ports'][3]['source_ref']), lambda d: validate_ports(d, vv), 'PORT_SOURCE_REFERENCE_INVALID')
    reject('cherry_picked_horizon', comparison, lambda d: d['cases'][0].update(horizon_periods=2), lambda d: validate_comparison(d, vv), 'HORIZON_SET_MISMATCH')
    reject('relocation_cost_ignored', comparison, lambda d: d['cases'][1].update(relocation_proxy_cost_s=0), lambda d: validate_comparison(d, vv), 'COST_SOURCE_MISMATCH')
    reject('candidate_used_as_different_baseline', comparison, lambda d: d.update(baseline_placement_ref=d['cases'][1]['candidate_ref']), lambda d: validate_comparison(d, vv), 'BASELINE_REFERENCE_MISMATCH')
    reject('invented_throughput_metric', comparison, lambda d: d.update(throughput_gain_percent=20), lambda d: validate_comparison(d, vv), 'SCHEMA_FIELD_ERROR')
    base = read_ref(comparison['baseline_placement_ref']); candidate = read_ref(comparison['cases'][0]['candidate_ref'])
    reject('quantity_changed_between_alternatives', candidate, lambda d: d['assignments'][0].update(quantity_units=d['assignments'][0]['quantity_units'] + 1), lambda d: compare_stock(base, d), 'STOCK_IDENTITY_MISMATCH')
    reject('reference_cannot_escape_repository', source['payload_ref'], lambda d: d.update(path='../outside.json'), resolve_ref, 'OUTSIDE_REPOSITORY')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check-only', action='store_true'); args = parser.parse_args()
    vv = validators(); manifest = read(BASE / 'manifest.json'); shape(manifest, vv['bundle'])
    all_refs = manifest['source_artifacts'] + manifest['handoff_artifacts'] + manifest['extra_inputs'] + manifest['canonical_contracts_snapshot']
    paths = [r['path'] for r in all_refs]
    require(len(paths) == len(set(paths)), 'DUPLICATE_ARTIFACT_PATH')
    before = {r['path']: digest(resolve_ref(r)) for r in all_refs}
    declared_package = {r['path'] for r in manifest['handoff_artifacts']}
    actual_package = {p.relative_to(ROOT).as_posix() for p in BASE.rglob('*') if p.is_file() and p != BASE / 'manifest.json'}
    require(actual_package == declared_package, 'UNLISTED_HANDOFF_ARTIFACT')
    require(len(manifest['source_artifacts']) == 33 and len(manifest['canonical_contracts_snapshot']) == 21, 'SOURCE_SNAPSHOT_COUNT_MISMATCH')
    cargo = read(ROOT / 'docs/v3/contract-proposals/cargo-catalog-v3.json'); slots = read(ROOT / 'docs/v3/contract-proposals/storage-slots-v3.json')
    for record in cargo['records']: shape(record, vv['cargo-archetype-v3'])
    shape(read(ROOT / 'docs/v3/contract-proposals/cargo-archetype-v3.example.json'), vv['cargo-archetype-v3'])
    shape(slots, vv['storage-slot-v3'])
    require(len(cargo['records']) == 8 and len(slots['modules']) == 132 and len(slots['slots']) == 776, 'DESIGN_COUNTS_CHANGED')
    actors = read(ROOT / 'contracts/actors.example.json')['actors']; policy = read(ROOT / POLICY)
    require(len(actors) == len({a['actor_id'] for a in actors}) == 24 and set(policy['actor_ids']) == {a['actor_id'] for a in actors}, 'ACTOR_IDENTITY_COUNT_MISMATCH')
    baseline = read(ROOT / 'docs/v3/contract-proposals/baseline-assignment-v3.json')['assignments']
    by_archetype = {a['archetype_id']: a for a in cargo['records']}
    actual_facts = dict(actors=len(actors), ports=6, handling_units=len(baseline), skus=len({a['sku_id'] for a in baseline}),
                        quantity_units=sum(a['quantity_units'] for a in baseline),
                        gross_mass_kg=round(sum(by_archetype[a['archetype_id']]['handling_unit']['gross_mass_kg'] for a in baseline), 8))
    require(actual_facts == manifest['inventory_facts'], 'INVENTORY_FACTS_MISMATCH')
    examples = {p.stem: read(p) for p in sorted((BASE / 'examples').glob('*.json'))}
    require(len(examples) == 7, 'EXAMPLE_COUNT_MISMATCH')
    for name, example in examples.items():
        if name.endswith('-input'): validate_source(example, vv)
        elif name.startswith('worker-'):
            validate_worker(example, vv); require(example['example_only'] is True, 'EXAMPLE_ACTIVATES_REGISTRY')
        elif name == 'ports-view': validate_ports(example, vv)
        elif name == 'slotting-comparison': validate_comparison(example, vv)
        else: raise ValueError('UNKNOWN_EXAMPLE ' + name)
    negative = negative_cases(examples, vv)
    require(before == {r['path']: digest(resolve_ref(r)) for r in all_refs}, 'READ_ONLY_INPUT_CHANGED')
    report = dict(task_id='C12', passed=True, source_kind='contract_proposal_handoff', engine_operation=False,
        backend_integration_complete=False, actual_v3_run_supported=False, worker_registry_materialized=False,
        source_checkpoint_commit=manifest['source_checkpoint_commit'], manifest_sha256=digest(BASE / 'manifest.json'),
        tool_sha256={p: digest(ROOT / p) for p in ['tools/visual/v3/build_contract_handoff_v3.py', 'tools/visual/v3/validate_contract_handoff_v3.py']},
        jsonschema_version=importlib.metadata.version('jsonschema'), offline_local_reference_registry=True,
        schemas_checked=len(vv), examples_checked=len(examples), cargo_records_checked=8, slot_modules_checked=132,
        slots_checked=776, port_views_checked=6, preserved_source_artifacts=33, unchanged_canonical_contracts=21,
        referenced_files_checked=len(all_refs), negative_cases=negative,
        original_source_fingerprints=manifest['source_artifacts'], scope=manifest['scope'])
    if not args.check_only:
        (ROOT / 'docs/adaptive-v3/evidence/C12-validator.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['negative_cases', 'original_source_fingerprints', 'scope']} | {'negative_mutations_rejected': len(negative)}))


if __name__ == '__main__': main()
