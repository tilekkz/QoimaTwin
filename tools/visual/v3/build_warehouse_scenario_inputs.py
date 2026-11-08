"""Freeze preregistered W09/W10 visual inputs, never execution or comparison results."""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE_FIXTURE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
BASE_SHA256 = '52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91'
OUT = ROOT / 'docs/adaptive-v3/fixtures/scenarios'
SCENARIOS = [
    ('W09', 'N0_NORMAL', 'W09-normal-input-v3.json'),
    ('W10', 'N1_OUTBOUND_SHIFT', 'W10-port-mix-input-v3.json'),
]
# These four assignments are declared before either comparison run. They are
# illustrative choices, not a timestamped conversion of C11 expected weights.
SHIFT = {
    'v3:request:base:inbound:02': 'IN_E_PARCEL',
    'v3:request:base:outbound:02': 'OUT_S_EXPRESS',
    'v3:request:base:outbound:04': 'OUT_E_B2B',
    'v3:request:base:outbound:07': 'OUT_E_B2B',
}
ALLOWED_OUTPUT_DIFFERENCES = ['admitted_HU_slot_placement', 'explicit_relocation_sequence_and_cost']


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf8')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


def payload_hash(document):
    return digest({key: document[key] for key in ['clock', 'layout_ref', 'registry_ref', 'profiles_ref', 'inputs']})


def port_counts(requests):
    return {direction: dict(sorted(Counter(r['port_id'] for r in requests if r['direction'] == direction).items()))
            for direction in ['inbound', 'outbound']}


def scenario_document(base, task, name):
    inputs = copy.deepcopy(base['inputs'])
    changes = []
    if task == 'W10':
        for request in inputs['requests']:
            if request['request_id'] in SHIFT:
                target = SHIFT[request['request_id']]
                changes.append(dict(request_id=request['request_id'], archetype_id=request['archetype_id'],
                                    direction=request['direction'], from_port_id=request['port_id'], to_port_id=target))
                request['port_id'] = target
    document = dict(
        schema_id='qoima.warehouse-scenario-input.v3', schema_version='0.1.0',
        scenario_id=f'v3:scenario:{name}:001', task_id=task, namespace='v3',
        source_kind='visual_fixture', engine_operation=False, operational_admission=False,
        actual_v3_run_supported=False, visual_complete=False, backend_integration_complete=False,
        execution_ready=False, execution_state='not_scheduled', metrics_scope='none',
        base_fixture_ref=dict(path=BASE_FIXTURE, sha256=BASE_SHA256, fixture_id=base['fixture_id']),
        clock=copy.deepcopy(base['clock']), layout_ref=copy.deepcopy(base['layout_ref']),
        registry_ref=copy.deepcopy(base['registry_ref']), profiles_ref=copy.deepcopy(base['profiles_ref']),
        source_hashes={**base['source_hashes'], BASE_FIXTURE: BASE_SHA256},
        inputs=inputs, input_hashes={key: digest(value) for key, value in inputs.items()},
        control=dict(base_request_stream_ref=dict(path='docs/adaptive-v3/fixtures/warehouse-request-stream-v3.json',
                        sha256=sha('docs/adaptive-v3/fixtures/warehouse-request-stream-v3.json')),
                     allowed_input_differences_from_W01=['requests.port_id'] if task == 'W10' else [],
                     declared_port_changes=changes, normal_port_counts=port_counts(base['inputs']['requests']),
                     scenario_port_counts=port_counts(inputs['requests']),
                     request_time_policy='Preserve every W01 absolute illustrative release/deadline second and request/HU identity. No C10/C11 period conversion.'),
        comparison_policy=dict(kind='slotting_only', same_input_file_required=True,
             allowed_output_differences=ALLOWED_OUTPUT_DIFFERENCES,
             role_assignment_changes_allowed=False, staff_count_changes_allowed=False,
             port_assignment_changes_within_pair_allowed=False,
             start_stock='same_original_W01_state_before_any_priced_admitted_relocation',
             no_op_allowed=True, force_improvement=False,
             decision_state='not_evaluated',
             no_op_rule='Keep the original placement whenever no admitted net improvement including explicit relocation cost is justified. Input preparation does not establish that decision.'),
        required_before_execution=['registered_W05_action_and_timing_source', 'admitted_cargo_and_handler_actions',
             'finite_buffer_and_exclusive_resource_intervals', 'same_frozen_workflow_implementation_for_both_runs',
             'reviewed_W09_or_W10_scene_and_replay_evidence'],
        assumptions=[
            'Materialized input-only visual fixture. No run, admitted movement, measured demand or comparison outcome is produced.',
            'All original530HUs/200SKUs/12256units/9403.85kg,24workers/2vehicles,6configuredports and physical/source policies are unchanged.',
            'The8incomingHUs remain upstream and excluded from initial stock; request release alone neither receives nor dispatches cargo.',
            'W10declares four compatible port reassignments to shift outbound retail requests toward express/easternB2B. No request quantity, identity or time changes.',
            'C11expectedHU weights and savings are unclocked analytical proxies and are not imported as actual timing or performance.',
            'The first comparison changes only admitted placement/relocations. Staffing comparisons require separate explicitly registered inputs and results.',
        ], actions=[], completion_events=[])
    document['frozen_payload_sha256'] = payload_hash(document)
    return document


def documents():
    assert sha(BASE_FIXTURE) == BASE_SHA256, 'Accepted W01 source changed; do not silently rebase frozen scenarios'
    base = read(BASE_FIXTURE)
    for path, expected in base['source_hashes'].items():
        assert sha(path) == expected, ('Stale W01 source', path)
    values = {}
    records = []
    for task, name, filename in SCENARIOS:
        document = scenario_document(base, task, name)
        values[filename] = encoded(document)
        reference = dict(path=(OUT / filename).relative_to(ROOT).as_posix(),
                         sha256=hashlib.sha256(values[filename]).hexdigest(),
                         frozen_payload_sha256=document['frozen_payload_sha256'])
        records.append(dict(task_id=task, scenario_id=document['scenario_id'], input_ref=reference,
            comparison_kind='slotting_only', execution_ready=False,
            paired_runs=[dict(variant='baseline', input_ref=copy.deepcopy(reference)),
                         dict(variant='adaptive', input_ref=copy.deepcopy(reference))],
            allowed_output_differences=ALLOWED_OUTPUT_DIFFERENCES,
            pending='W05/W14runtime registration, admissible actions/resources, actual replay and comparison acceptance'))
    values['scenario-inputs-manifest-v3.json'] = encoded(dict(
        schema_id='qoima.warehouse-scenario-input-manifest.v3', schema_version='0.1.0',
        source_kind='visual_fixture', engine_operation=False, operational_admission=False,
        actual_v3_run_supported=False, visual_complete=False, backend_integration_complete=False,
        execution_ready=False, execution_state='not_scheduled', metrics_scope='none',
        base_fixture_ref=dict(path=BASE_FIXTURE, sha256=BASE_SHA256), scenarios=records,
        actions=[], completion_events=[],
        scope='Preregistered W09/W10 requests and paired source identity only. Does not close either parent scenario, register an executable workflow or establish a no-op/improvement result.'))
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    values = documents()
    if not args.check_only:
        OUT.mkdir(parents=True, exist_ok=True)
    for filename, data in values.items():
        path = OUT / filename
        if args.check_only or path.exists():
            assert path.read_bytes() == data, f'Refuse replacing preregistered scenario input: {filename}'
        else:
            path.write_bytes(data)
    print(json.dumps(dict(passed=True, source_kind='visual_fixture', engine_operation=False,
        execution_ready=False, scenarios=2, requests_per_scenario=16,
        files={filename: hashlib.sha256(data).hexdigest() for filename, data in values.items()},
        check_only=args.check_only)))


if __name__ == '__main__':
    main()
