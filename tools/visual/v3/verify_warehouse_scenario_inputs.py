"""Independent semantic/source checks for preregistered W09/W10 input-only fixtures."""
import argparse
import copy
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / 'docs/adaptive-v3/fixtures/scenarios'
BASE_PATH = 'frontend/public/data/v3/warehouse-fixture-v3.json'
BASE_SHA = '52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91'
REPORT = ROOT / 'docs/adaptive-v3/evidence/scenario-inputs-checks.json'
FILES = {'W09': 'W09-normal-input-v3.json', 'W10': 'W10-port-mix-input-v3.json'}
EXPECTED_SCENARIOS = {'W09': 'v3:scenario:N0_NORMAL:001', 'W10': 'v3:scenario:N1_OUTBOUND_SHIFT:001'}
SHIFT_TARGETS = {
    ('inbound', 'STANDARD_CARTON'): 'IN_E_PARCEL',
    ('outbound', 'STANDARD_CARTON'): 'OUT_S_EXPRESS',
    ('outbound', 'PALLET_LOAD'): 'OUT_E_B2B',
    ('outbound', 'DRUM'): 'OUT_E_B2B',
}
DIFFERENCES = ['admitted_HU_slot_placement', 'explicit_relocation_sequence_and_cost']
PREREQUISITES = ['registered_W05_action_and_timing_source', 'admitted_cargo_and_handler_actions',
    'finite_buffer_and_exclusive_resource_intervals', 'same_frozen_workflow_implementation_for_both_runs',
    'reviewed_W09_or_W10_scene_and_replay_evidence']
TOP_FIELDS = {'schema_id', 'schema_version', 'scenario_id', 'task_id', 'namespace', 'source_kind',
    'engine_operation', 'operational_admission', 'actual_v3_run_supported', 'visual_complete',
    'backend_integration_complete', 'execution_ready', 'execution_state', 'metrics_scope',
    'base_fixture_ref', 'clock', 'layout_ref', 'registry_ref', 'profiles_ref', 'source_hashes',
    'inputs', 'input_hashes', 'control', 'comparison_policy', 'required_before_execution',
    'assumptions', 'actions', 'completion_events', 'frozen_payload_sha256'}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


def payload_hash(d):
    return digest({key: d[key] for key in ['clock', 'layout_ref', 'registry_ref', 'profiles_ref', 'inputs']})


def require(value, reason):
    if not value:
        raise ValueError(reason)


def counts(requests):
    return {direction: dict(sorted(Counter(r['port_id'] for r in requests if r['direction'] == direction).items()))
            for direction in ['inbound', 'outbound']}


def source_scope(d):
    require(d['source_kind'] == 'visual_fixture' and d['engine_operation'] is False and
            d['operational_admission'] is False and d['actual_v3_run_supported'] is False and
            d['visual_complete'] is False and d['backend_integration_complete'] is False and
            d['execution_ready'] is False and d['metrics_scope'] == 'none', 'SOURCE_SCOPE_MISMATCH')
    require(d['execution_state'] == 'not_scheduled' and d['actions'] == [] and d['completion_events'] == [],
            'FABRICATED_EXECUTION')


def verify_scenario(d, task, base):
    require(set(d) == TOP_FIELDS, 'UNDECLARED_SCENARIO_FIELD')
    require(d['schema_id'] == 'qoima.warehouse-scenario-input.v3' and d['schema_version'] == '0.1.0' and
            d['namespace'] == 'v3' and d['task_id'] == task and d['scenario_id'] == EXPECTED_SCENARIOS[task], 'SCENARIO_IDENTITY_MISMATCH')
    source_scope(d)
    require(d['base_fixture_ref'] == dict(path=BASE_PATH, sha256=BASE_SHA, fixture_id=base['fixture_id']), 'BASE_SOURCE_MISMATCH')
    require(d['source_hashes'] == {**base['source_hashes'], BASE_PATH: BASE_SHA}, 'SOURCE_SET_MISMATCH')
    for path, expected in d['source_hashes'].items():
        require(sha(ROOT / path) == expected, 'SOURCE_HASH_MISMATCH')
    require(d['clock'] == base['clock'], 'CLOCK_CHANGED')
    for field in ['layout_ref', 'registry_ref', 'profiles_ref']:
        require(d[field] == base[field] and sha(ROOT / d[field]['path']) == d[field]['sha256'], 'SHARED_REFERENCE_CHANGED')
    inputs = d['inputs']
    require(set(inputs) == set(base['inputs']), 'INPUT_FIELDS_CHANGED')
    catalog = {a['archetype_id']: a for a in base['inputs']['archetypes']}
    original_stock = {h['handling_unit_id']: h for h in base['inputs']['initial_stock']}
    stock = {h['handling_unit_id']: h for h in inputs['initial_stock']}
    require(len(stock) == len(inputs['initial_stock']) == 530 and set(stock) == set(original_stock), 'STOCK_IDENTITY_CHANGED')
    for hu in stock.values():
        source = original_stock[hu['handling_unit_id']]
        require(all(hu.get(key) == source[key] for key in ['lot_id', 'sku_id', 'archetype_id', 'quantity_units', 'orientation_id']), 'STOCK_CONTENT_CHANGED')
        template = catalog[hu['archetype_id']]['handling_unit']
        require(hu['dimensions_xyz_m'] == template['dimensions_xyz_m'] and hu['gross_mass_kg'] == template['gross_mass_kg'] and
                hu['model_scale_factor'] == 1, 'CARGO_DIMENSION_MASS_SCALE_CHANGED')
    require(inputs['initial_stock'] == base['inputs']['initial_stock'], 'INITIAL_STOCK_PLACEMENT_CHANGED')
    require(sum(h['quantity_units'] for h in stock.values()) == 12256 and
            sum(Decimal(str(h['gross_mass_kg'])) for h in stock.values()) == Decimal('9403.85') and
            len({h['sku_id'] for h in stock.values()}) == 200, 'STOCK_CONSERVATION')
    for key, reason in [('workers', 'WORKER_INPUT_CHANGED'), ('vehicles', 'VEHICLE_INPUT_CHANGED'),
                        ('ports', 'PORT_CONFIGURATION_CHANGED'), ('archetypes', 'ARCHETYPE_INPUT_CHANGED'), ('skus', 'SKU_INPUT_CHANGED')]:
        require(inputs[key] == base['inputs'][key], reason)
    original = {r['request_id']: r for r in base['inputs']['requests']}
    requests = inputs['requests']
    require(len(requests) == 16 and len({r['request_id'] for r in requests}) == 16 and
            {r['request_id'] for r in requests} == set(original) and len({r['handling_unit_id'] for r in requests}) == 16,
            'REQUEST_IDENTITY_CHANGED')
    require(requests == sorted(requests, key=lambda r: (r['requested_at_s'], r['request_id'])), 'REQUEST_ORDER_CHANGED')
    ports = {p['port_id']: p for p in inputs['ports']}
    declared = []
    for request in requests:
        source = original[request['request_id']]
        require(set(request) == set(source), 'REQUEST_FIELDS_CHANGED')
        require(request['port_id'] in ports, 'UNKNOWN_PORT')
        port = ports[request['port_id']]
        require(request['direction'] == port['direction'] and request['kind'] == ('receipt_request' if request['direction'] == 'inbound' else 'order_request'), 'PORT_DIRECTION_MISMATCH')
        require(request['archetype_id'] in port['allowed_cargo_archetype_ids'], 'PORT_CARGO_FORBIDDEN')
        require(request['quantity_handling_units'] == 1 and request['quantity_units'] == catalog[request['archetype_id']]['handling_unit']['units_per_handling_unit'], 'REQUEST_QUANTITY_CHANGED')
        at, deadline = request['requested_at_s'], request['deadline_at_s']
        require(all(type(v) in [int, float] and math.isfinite(v) for v in [at, deadline]) and 0 <= at < deadline <= 1800, 'REQUEST_TIME_INVALID')
        require(any(start <= at < end for start, end in port['open_windows']), 'PORT_CLOSED')
        incoming = request['direction'] == 'inbound'
        require(request['included_in_initial_stock'] is (not incoming) and request['initial_location_kind'] == ('upstream' if incoming else 'storage_slot'), 'UPSTREAM_STOCK_CONFUSION')
        if incoming:
            require(request['handling_unit_id'] not in stock, 'UPSTREAM_HU_COLLISION')
        else:
            require(request['handling_unit_id'] in stock, 'OUTBOUND_STOCK_MISSING')
        require({k: v for k, v in request.items() if k != 'port_id'} == {k: v for k, v in source.items() if k != 'port_id'}, 'FROZEN_REQUEST_FIELD_CHANGED')
        target = SHIFT_TARGETS.get((request['direction'], request['archetype_id']), source['port_id']) if task == 'W10' else source['port_id']
        require(request['port_id'] == target, 'PREREGISTERED_PORT_ASSIGNMENT_CHANGED')
        if target != source['port_id']:
            declared.append(dict(request_id=request['request_id'], archetype_id=request['archetype_id'], direction=request['direction'], from_port_id=source['port_id'], to_port_id=target))
    require(len(declared) == (4 if task == 'W10' else 0), 'PORT_CHANGE_COUNT')
    for direction in ['inbound', 'outbound']:
        rows = [r for r in requests if r['direction'] == direction]
        require(len(rows) == 8 and {r['archetype_id'] for r in rows} == set(catalog), 'REQUEST_FAMILY_COVERAGE')
    control = d['control']
    require(set(control) == {'base_request_stream_ref', 'allowed_input_differences_from_W01', 'declared_port_changes',
                            'normal_port_counts', 'scenario_port_counts', 'request_time_policy'}, 'CONTROL_DECLARATION_CHANGED')
    require(control['declared_port_changes'] == declared and control['allowed_input_differences_from_W01'] == (['requests.port_id'] if task == 'W10' else []) and
            control['normal_port_counts'] == counts(base['inputs']['requests']) and control['scenario_port_counts'] == counts(requests), 'CONTROL_DECLARATION_CHANGED')
    require(control['base_request_stream_ref'] == dict(path='docs/adaptive-v3/fixtures/warehouse-request-stream-v3.json', sha256=sha(ROOT / 'docs/adaptive-v3/fixtures/warehouse-request-stream-v3.json')), 'BASE_STREAM_CHANGED')
    policy = d['comparison_policy']
    require(set(policy) == {'kind', 'same_input_file_required', 'allowed_output_differences', 'role_assignment_changes_allowed',
            'staff_count_changes_allowed', 'port_assignment_changes_within_pair_allowed', 'start_stock',
            'no_op_allowed', 'force_improvement', 'decision_state', 'no_op_rule'}, 'PAIRED_NONPLACEMENT_DIFFERENCE')
    require(policy['kind'] == 'slotting_only' and policy['same_input_file_required'] is True and
            policy['allowed_output_differences'] == DIFFERENCES and policy['role_assignment_changes_allowed'] is False and
            policy['staff_count_changes_allowed'] is False and policy['port_assignment_changes_within_pair_allowed'] is False,
            'PAIRED_NONPLACEMENT_DIFFERENCE')
    require(policy['no_op_allowed'] is True and policy['force_improvement'] is False and policy['decision_state'] == 'not_evaluated', 'FABRICATED_ADAPTATION_DECISION')
    require(policy['start_stock'] == 'same_original_W01_state_before_any_priced_admitted_relocation', 'INITIAL_STOCK_PLACEMENT_CHANGED')
    require(d['required_before_execution'] == PREREQUISITES and len(d['assumptions']) == 6, 'EXECUTION_PREREQUISITES_CHANGED')
    require(d['input_hashes'] == {k: digest(v) for k, v in inputs.items()} and d['frozen_payload_sha256'] == payload_hash(d), 'CONTENT_HASH_MISMATCH')
    return dict(task_id=task, scenario_id=d['scenario_id'], initial_HUs=530, SKUs=200, quantity_units=12256,
                gross_mass_kg=9403.85, workers=24, vehicles=2, configured_ports=6, requests=16,
                upstream_HUs=8, outbound_existing_HUs=8, declared_port_changes=len(declared), port_counts=counts(requests))


def verify_manifest(manifest, documents):
    require(set(manifest) == {'schema_id', 'schema_version', 'source_kind', 'engine_operation', 'operational_admission',
        'actual_v3_run_supported', 'visual_complete', 'backend_integration_complete', 'execution_ready', 'execution_state',
        'metrics_scope', 'base_fixture_ref', 'scenarios', 'actions', 'completion_events', 'scope'}, 'UNDECLARED_MANIFEST_FIELD')
    require(manifest['schema_id'] == 'qoima.warehouse-scenario-input-manifest.v3' and manifest['schema_version'] == '0.1.0', 'MANIFEST_SCHEMA_MISMATCH')
    source_scope(manifest)
    require(manifest['base_fixture_ref'] == dict(path=BASE_PATH, sha256=BASE_SHA), 'BASE_SOURCE_MISMATCH')
    rows = manifest['scenarios']
    require(len(rows) == 2 and {r['task_id'] for r in rows} == set(FILES), 'MANIFEST_SCENARIOS_CHANGED')
    for row in rows:
        require(set(row) == {'task_id', 'scenario_id', 'input_ref', 'comparison_kind', 'execution_ready', 'paired_runs',
                            'allowed_output_differences', 'pending'}, 'PAIRED_RUN_OVERRIDE')
        task = row['task_id']
        require(row['scenario_id'] == EXPECTED_SCENARIOS[task] and row['comparison_kind'] == 'slotting_only' and row['execution_ready'] is False and row['allowed_output_differences'] == DIFFERENCES, 'PAIRED_NONPLACEMENT_DIFFERENCE')
        runs = row['paired_runs']
        require(len(runs) == 2 and [r.get('variant') for r in runs] == ['baseline', 'adaptive'] and all(set(r) == {'variant', 'input_ref'} for r in runs), 'PAIRED_RUN_OVERRIDE')
        require(runs[0]['input_ref'] == runs[1]['input_ref'] == row['input_ref'], 'PAIRED_INPUTS_DIFFER')
        reference = row['input_ref']
        path = DIRECTORY / FILES[task]
        require(reference == dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), frozen_payload_sha256=documents[task]['frozen_payload_sha256']), 'MANIFEST_REFERENCE_CHANGED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    require(sha(ROOT / BASE_PATH) == BASE_SHA, 'ACCEPTED_W01_SOURCE_CHANGED')
    base = read(ROOT / BASE_PATH)
    documents = {task: read(DIRECTORY / filename) for task, filename in FILES.items()}
    manifest = read(DIRECTORY / 'scenario-inputs-manifest-v3.json')
    summaries = [verify_scenario(documents[task], task, base) for task in FILES]
    verify_manifest(manifest, documents)
    cases = []

    def reject(name, task, mutation, expected):
        changed = copy.deepcopy(documents[task])
        mutation(changed)
        # Recomputed generic hashes must not turn semantically altered inputs into accepted scenarios.
        changed['input_hashes'] = {key: digest(value) for key, value in changed['inputs'].items()}
        changed['frozen_payload_sha256'] = payload_hash(changed)
        try:
            verify_scenario(changed, task, base)
        except ValueError as error:
            require(str(error) == expected, f'Unexpected rejection for {name}: {error}')
            cases.append(dict(case=name, task_id=task, rejected=True, reason=str(error), generic_hashes_recomputed=True))
        else:
            raise AssertionError('Invalid scenario accepted: ' + name)

    reject('actual_engine_label', 'W09', lambda d: d.update(source_kind='actual_engine_run'), 'SOURCE_SCOPE_MISMATCH')
    reject('invented_engine_operation', 'W09', lambda d: d.update(engine_operation=True), 'SOURCE_SCOPE_MISMATCH')
    reject('invented_execution_ready', 'W09', lambda d: d.update(execution_ready=True), 'SOURCE_SCOPE_MISMATCH')
    reject('invented_action', 'W09', lambda d: d['actions'].append(dict(start_s=0, end_s=1)), 'FABRICATED_EXECUTION')
    reject('invented_completion', 'W10', lambda d: d['completion_events'].append(dict(at_s=10)), 'FABRICATED_EXECUTION')
    reject('invented_throughput', 'W10', lambda d: d.update(throughput_HUs_per_hour=1000), 'UNDECLARED_SCENARIO_FIELD')
    reject('extra_worker', 'W09', lambda d: d['inputs']['workers'].append(dict(d['inputs']['workers'][0], actor_id='PK01')), 'WORKER_INPUT_CHANGED')
    reject('changed_worker_role', 'W10', lambda d: d['inputs']['workers'][0].update(initial_role='packer'), 'WORKER_INPUT_CHANGED')
    reject('wrong_vehicle_pair', 'W09', lambda d: d['inputs']['vehicles'][0].update(driver_actor_id='F02'), 'VEHICLE_INPUT_CHANGED')
    reject('port_buffer_increased', 'W10', lambda d: d['inputs']['ports'][0].update(finite_buffer_capacity=999), 'PORT_CONFIGURATION_CHANGED')
    reject('port_service_rule_changed', 'W10', lambda d: d['inputs']['ports'][0].update(service_time_rule='free'), 'PORT_CONFIGURATION_CHANGED')
    reject('port_dimensions_widened', 'W10', lambda d: d['inputs']['ports'][0].update(clear_width_m=99), 'PORT_CONFIGURATION_CHANGED')
    reject('duplicate_initial_HU', 'W09', lambda d: d['inputs']['initial_stock'].append(copy.deepcopy(d['inputs']['initial_stock'][0])), 'STOCK_IDENTITY_CHANGED')
    reject('changed_stock_quantity', 'W10', lambda d: d['inputs']['initial_stock'][0].update(quantity_units=1), 'STOCK_CONTENT_CHANGED')
    reject('changed_HU_mass', 'W09', lambda d: d['inputs']['initial_stock'][0].update(gross_mass_kg=.01), 'CARGO_DIMENSION_MASS_SCALE_CHANGED')
    reject('changed_HU_dimensions', 'W09', lambda d: d['inputs']['initial_stock'][0].update(dimensions_xyz_m=[.01,.01,.01]), 'CARGO_DIMENSION_MASS_SCALE_CHANGED')
    reject('shrunk_HU_scale', 'W10', lambda d: d['inputs']['initial_stock'][0].update(model_scale_factor=.5), 'CARGO_DIMENSION_MASS_SCALE_CHANGED')
    reject('unpriced_initial_relocation', 'W10', lambda d: d['inputs']['initial_stock'][0]['location']['placement'].update(bottom_y_m=99), 'INITIAL_STOCK_PLACEMENT_CHANGED')
    reject('unknown_port', 'W10', lambda d: d['inputs']['requests'][0].update(port_id='IN_UNKNOWN'), 'UNKNOWN_PORT')
    reject('wrong_port_direction', 'W10', lambda d: d['inputs']['requests'][0].update(port_id='OUT_S_EXPRESS'), 'PORT_DIRECTION_MISMATCH')
    reject('heavy_at_small_port', 'W10', lambda d: d['inputs']['requests'][4].update(port_id='IN_E_PARCEL'), 'PORT_CARGO_FORBIDDEN')
    reject('long_at_express_gate', 'W10', lambda d: d['inputs']['requests'][11].update(port_id='OUT_S_EXPRESS'), 'PORT_CARGO_FORBIDDEN')
    reject('missing_request', 'W09', lambda d: d['inputs']['requests'].pop(), 'REQUEST_IDENTITY_CHANGED')
    reject('extra_request', 'W10', lambda d: d['inputs']['requests'].append(copy.deepcopy(d['inputs']['requests'][0])), 'REQUEST_IDENTITY_CHANGED')
    reject('duplicate_request_ID', 'W10', lambda d: d['inputs']['requests'][1].update(request_id=d['inputs']['requests'][0]['request_id']), 'REQUEST_IDENTITY_CHANGED')
    reject('extra_HU_per_request', 'W10', lambda d: d['inputs']['requests'][0].update(quantity_handling_units=2), 'REQUEST_QUANTITY_CHANGED')
    reject('changed_request_units', 'W09', lambda d: d['inputs']['requests'][0].update(quantity_units=1), 'REQUEST_QUANTITY_CHANGED')
    reject('request_scale_override', 'W09', lambda d: d['inputs']['requests'][0].update(model_scale_factor=.5), 'REQUEST_FIELDS_CHANGED')
    reject('deadline_before_release', 'W10', lambda d: d['inputs']['requests'][0].update(deadline_at_s=1), 'REQUEST_TIME_INVALID')
    reject('nonfinite_request_time', 'W10', lambda d: d['inputs']['requests'][0].update(deadline_at_s=float('nan')), 'REQUEST_TIME_INVALID')
    reject('changed_release_time', 'W10', lambda d: d['inputs']['requests'][0].update(requested_at_s=61), 'FROZEN_REQUEST_FIELD_CHANGED')
    reject('incoming_counted_as_stock', 'W09', lambda d: d['inputs']['requests'][0].update(included_in_initial_stock=True), 'UPSTREAM_STOCK_CONFUSION')
    reject('incoming_HU_collides_with_stock', 'W09', lambda d: d['inputs']['requests'][0].update(handling_unit_id=d['inputs']['initial_stock'][-1]['handling_unit_id']), 'UPSTREAM_HU_COLLISION')
    reject('outbound_HU_missing', 'W10', lambda d: d['inputs']['requests'][1].update(handling_unit_id='v3:HU:missing'), 'OUTBOUND_STOCK_MISSING')
    reject('normal_forced_port_shift', 'W09', lambda d: d['inputs']['requests'][3].update(port_id='OUT_S_EXPRESS'), 'PREREGISTERED_PORT_ASSIGNMENT_CHANGED')
    reject('shift_undeclared_but_compatible_port', 'W10', lambda d: d['inputs']['requests'][5].update(port_id='OUT_W_RETAIL'), 'PREREGISTERED_PORT_ASSIGNMENT_CHANGED')
    reject('changed_clock_horizon', 'W09', lambda d: d['clock'].update(duration_s=3600), 'CLOCK_CHANGED')
    reject('staffing_mixed_with_slotting', 'W10', lambda d: d['comparison_policy'].update(role_assignment_changes_allowed=True), 'PAIRED_NONPLACEMENT_DIFFERENCE')
    reject('port_changes_inside_pair', 'W10', lambda d: d['comparison_policy'].update(port_assignment_changes_within_pair_allowed=True), 'PAIRED_NONPLACEMENT_DIFFERENCE')
    reject('force_fake_improvement', 'W09', lambda d: d['comparison_policy'].update(force_improvement=True), 'FABRICATED_ADAPTATION_DECISION')
    reject('invented_noop_result', 'W09', lambda d: d['comparison_policy'].update(decision_state='no_op_verified'), 'FABRICATED_ADAPTATION_DECISION')
    reject('hidden_service_override', 'W10', lambda d: d['comparison_policy'].update(service_time_multiplier=.1), 'PAIRED_NONPLACEMENT_DIFFERENCE')
    reject('different_adaptive_start_stock', 'W10', lambda d: d['comparison_policy'].update(start_stock='adapted_free_relocation'), 'INITIAL_STOCK_PLACEMENT_CHANGED')
    reject('removed_resource_prerequisites', 'W10', lambda d: d.update(required_before_execution=['none']*5), 'EXECUTION_PREREQUISITES_CHANGED')

    def reject_pair(name, mutation, expected):
        changed = copy.deepcopy(manifest)
        mutation(changed)
        try:
            verify_manifest(changed, documents)
        except ValueError as error:
            require(str(error) == expected, f'Unexpected pair rejection for {name}: {error}')
            cases.append(dict(case=name, task_id='pair', rejected=True, reason=str(error)))
        else:
            raise AssertionError('Invalid paired inputs accepted: ' + name)

    reject_pair('adaptive_different_input_file', lambda d: d['scenarios'][1]['paired_runs'][1]['input_ref'].update(path=d['scenarios'][0]['input_ref']['path']), 'PAIRED_INPUTS_DIFFER')
    reject_pair('adaptive_different_input_hash', lambda d: d['scenarios'][1]['paired_runs'][1]['input_ref'].update(sha256='0'*64), 'PAIRED_INPUTS_DIFFER')
    reject_pair('adaptive_request_override', lambda d: d['scenarios'][1]['paired_runs'][1].update(request_overrides=[dict(request_id='x', port_id='y')]), 'PAIRED_RUN_OVERRIDE')
    reject_pair('adaptive_staff_override', lambda d: d['scenarios'][0]['paired_runs'][1].update(worker_overrides=[dict(actor_id='P01', initial_role='packer')]), 'PAIRED_RUN_OVERRIDE')
    reject_pair('mixed_plan_difference_allowed', lambda d: d['scenarios'][1]['allowed_output_differences'].append('extra_workers'), 'PAIRED_NONPLACEMENT_DIFFERENCE')
    reject_pair('manifest_invented_metrics', lambda d: d.update(throughput_HUs_per_hour=1000), 'UNDECLARED_MANIFEST_FIELD')
    paths = [*base['source_hashes'], BASE_PATH,
             *[(DIRECTORY / filename).relative_to(ROOT).as_posix() for filename in [*FILES.values(), 'scenario-inputs-manifest-v3.json']],
             'tools/visual/v3/build_warehouse_scenario_inputs.py', 'tools/visual/v3/verify_warehouse_scenario_inputs.py']
    report = dict(passed=True, reviewer='scenario_inputs', source_kind='visual_fixture', engine_operation=False,
        execution_ready=False, scenario_inputs_verified=summaries, paired_inputs_identical=True,
        normal_requests_identical_to_W01=True, shift_preserves_all_non_port_request_fields=True,
        initial_530HUs_and_24workers_preserved=True, incoming8HUs_excluded_from_initial_stock=True,
        no_C11_period_to_seconds_conversion=True, no_actions_completions_or_metrics_generated=True,
        negatives=cases, input_hashes={path: sha(ROOT / path) for path in sorted(set(paths))},
        scope='Preregistered input-only preparation for W09/W10. No runtime registration, admitted workflow, no-op decision, comparison outcome or parent task acceptance.')
    data = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if args.check_only:
        require(REPORT.read_bytes() == data, 'STALE_SCENARIO_INPUT_REPORT')
    else:
        REPORT.write_bytes(data)
    print(json.dumps(dict(passed=True, source_kind='visual_fixture', engine_operation=False, execution_ready=False,
        scenarios=2, requests_per_scenario=16, changed_port_assignments=4, negative_cases=len(cases), check_only=args.check_only)))


if __name__ == '__main__':
    main()
