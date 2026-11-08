"""Independent W11.1.1 source/semantic audit; imports no scenario builder."""
import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from storage_eligibility import evaluate
from verify_heavy_inbound_scenario import handling_check

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = 'docs/adaptive-v3/fixtures/scenarios/heavy-inbound'
INPUT = DIRECTORY + '/current-input-v3.json'
PAIR = DIRECTORY + '/current-pair-v3.json'
MIGRATION = DIRECTORY + '/source-migration-v3.json'
REPORT = 'docs/adaptive-v3/evidence/W11.1.1.json'
BASE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
HISTORICAL = 'docs/adaptive-v3/fixtures/scenarios/W11-heavy-inbound-input-v3.json'
REGISTRY = 'frontend/public/data/v3/worker-registry-v3.json'
PROFILES = 'frontend/public/data/v3/worker-profiles-v3.json'
C08 = 'docs/v3/contract-proposals/vehicle-handling-v3.json'
C07 = 'docs/v3/contract-proposals/cargo-mass-cases-v3.json'
PINS = {
    BASE: '81d0caad4898a68a41f9c647141e7290df480900599e82b81739809cab0f9579',
    REGISTRY: 'b21c2754fd2abec813adc1d9d1c24cf7f338f6a8a83efa051f70ef7982597e82',
    PROFILES: 'f30eb892ccc75ae5d2e6650e1a41b58acecbecd1a7c5cbcaf9b5836d8b7a8dc5',
    HISTORICAL: '44022f72105fb2252a8cd8b8b950e10f7590e5f732d86caa30178edbfcaa4393',
    C08: '22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4',
    C07: '3d4e15a4941f4692d14238f4891a1ca24bdd46858e327d4e1e0682fb2b4e25ce',
    DIRECTORY + '/historical-worker-registry-v3.json': 'fef5502f82d6cc624c9d6713d8e6e744bdc75c10a4992c4b1dc530044e0fef30',
    DIRECTORY + '/historical-worker-profiles-v3.json': 'c046dfcfe36eb1dcddcc5e70954384d005b7393c60d21ae9b5ad950ca198b8a0',
    'tools/visual/v3/verify_heavy_inbound_scenario.py': '5f681688668c6b8346b1a51f875dc01a7a0164056b41a6147447096f2f7eca67',
    'tools/visual/v3/storage_eligibility.py': '4b3fef1f4d29f0ad9954b9937a800462582b4302f3219cb02bc52626603cc646',
    'tools/visual/v3/build_storage_contract.py': '8169fc3dde18711398c7cb28163aee310e1a858db8e9b65f529264f4df96bcd4',
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')


def same(a, b):
    return encode(a) == encode(b)


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ref(path):
    data = (ROOT / path).read_bytes()
    return dict(path=path, sha256=sha(data), bytes=len(data))


def check_pin(data, expected):
    require(sha(data) == expected, 'PINNED_SOURCE_DRIFT')


def context():
    for path, expected in PINS.items():
        check_pin((ROOT / path).read_bytes(), expected)
    base, old, c08, c07 = [read(p) for p in [BASE, HISTORICAL, C08, C07]]
    pins = dict(base['source_hashes'])
    pins.update(PINS)
    rows = [r for document in [c08, c07] for r in document['source_fingerprints']]
    rows += [dict(path=p, sha256=h) for source in [REGISTRY, PROFILES] for p, h in read(source)['source_hashes'].items()]
    for row in rows:
        require(row['path'] not in pins or pins[row['path']] == row['sha256'], 'CONFLICTING_SOURCE_AUTHORITY')
        pins[row['path']] = row['sha256']
    for path, expected in pins.items():
        check_pin((ROOT / path).read_bytes(), expected)
    return base, old, c08, c07, pins


def flatten(value, prefix=''):
    if isinstance(value, dict):
        return {p: v for key, child in value.items() for p, v in flatten(child,
            prefix + '/' + key.replace('~', '~0').replace('/', '~1')).items()}
    if isinstance(value, list):
        return {p: v for index, child in enumerate(value) for p, v in flatten(child, prefix + '/' + str(index)).items()}
    return {prefix: value}


def fingerprint_free(value):
    if isinstance(value, dict):
        return {k: fingerprint_free(v) for k, v in value.items() if k not in ['sha256', 'source_hashes']}
    if isinstance(value, list):
        return [fingerprint_free(v) for v in value]
    return value


def capabilities_unchanged(before, after):
    require(same(before['profiles'], after['profiles']), 'WORKER_CAPABILITIES_CHANGED')
    require(same(fingerprint_free(before), fingerprint_free(after)), 'PROFILE_SEMANTICS_CHANGED')


def verify_migration(migration):
    require(set(migration) == set('schema_id task_id source_kind engine_operation operational_admission historical_input_ref current_fixture_ref sources original_workload_preserved all_28_heavy_scenario_requests_preserved scope'.split()), 'MIGRATION_FIELDS')
    require(migration['schema_id'] == 'qoima.heavy-inbound-source-migration.v3' and migration['task_id'] == 'W11.1.1' and
        migration['source_kind'] == 'visual_fixture' and migration['engine_operation'] is False and
        migration['operational_admission'] is False and migration['original_workload_preserved'] is True and
        migration['all_28_heavy_scenario_requests_preserved'] is True, 'MIGRATION_SCOPE')
    require(same(migration['historical_input_ref'], ref(HISTORICAL)) and same(migration['current_fixture_ref'], ref(BASE)), 'MIGRATION_REFERENCE')
    require(migration['scope'] == 'Reference/fingerprint migration only. No changed worker capabilities, clip timing, workload or runtime admission.', 'MIGRATION_CLAIM')
    rows = migration['sources']
    require(len(rows) == 2 and [r['source_path'] for r in rows] == [REGISTRY, PROFILES], 'MIGRATION_SOURCES')
    for row, commit in zip(rows, ['0d3a57bb9e35c8dbb43c070b6967e9aee0857e3f', '8a1687737e53b4844ce68673c54bf5c41bdaf869']):
        path = row['source_path']
        snapshot = DIRECTORY + '/historical-' + Path(path).name
        require(set(row) == set('source_path historical_snapshot_ref historical_git_commit current_ref changes'.split()) and
            row['historical_git_commit'] == commit and same(row['historical_snapshot_ref'], ref(snapshot)) and
            same(row['current_ref'], ref(path)), 'MIGRATION_SOURCE_REFERENCE')
        before, after = read(snapshot), read(path)
        require(same(fingerprint_free(before), fingerprint_free(after)), 'WORKER_OR_CLIP_SEMANTICS_CHANGED')
        if path == PROFILES:
            capabilities_unchanged(before, after)
        a, b = flatten(before), flatten(after)
        require(a.keys() == b.keys(), 'MIGRATION_SHAPE_CHANGED')
        expected = [dict(pointer=p, before=a[p], after=b[p]) for p in sorted(a) if not same(a[p], b[p])]
        require(same(sorted(row['changes'], key=lambda x: x['pointer']), expected), 'MIGRATION_DIFF_CHANGED')
        require(all('/source_hashes/' in x['pointer'] or x['pointer'].endswith('/sha256') for x in expected), 'MIGRATION_NONFINGERPRINT_CHANGE')
    return dict(registry_changed_leaves=len(rows[0]['changes']), profile_changed_leaves=len(rows[1]['changes']),
        profile_capability_rows_unchanged=24, worker_and_clip_semantics_unchanged=True)


def verify_document(d, migration, ctx):
    base, old, c08, c07, pins = ctx
    changed_keys = set('schema_id task_id scenario_id status base_fixture_ref source_hashes registry_ref profiles_ref historical_input_ref migration_ref'.split())
    require(set(d) == set(old) | {'historical_input_ref', 'migration_ref'}, 'INPUT_DOCUMENT_FIELDS')
    for key in set(old) - changed_keys:
        require(same(d[key], old[key]), 'FROZEN_HEAVY_WORKLOAD_OR_POLICY')
    require((d['schema_id'], d['task_id'], d['scenario_id'], d['status']) ==
        ('qoima.heavy-inbound-current-input.v3', 'W11.1.1', 'v3:scenario:N2_HEAVY_INBOUND:current:001',
         'input_only_current_source_candidate_pending_root_review'), 'CURRENT_SCENARIO_IDENTITY')
    require(same(d['base_fixture_ref'], dict(path=BASE, sha256=PINS[BASE])) and
        same(d['historical_input_ref'], ref(HISTORICAL)) and same(d['migration_ref'], ref(MIGRATION)), 'CURRENT_SOURCE_REFERENCE')
    require(same(d['source_hashes'], pins), 'CURRENT_SOURCE_HASHES')
    require(same(d['registry_ref'], base['registry_ref']) and same(d['profiles_ref'], base['profiles_ref']), 'CURRENT_WORKER_REFERENCE')
    for key in set(base['inputs']) - {'requests'}:
        require(same(d['inputs'][key], base['inputs'][key]), 'ORIGINAL_WORKLOAD_CHANGED')
    requests = {r['request_id']: r for r in d['inputs']['requests']}
    require(len(requests) == 28 and all(same(requests.get(r['request_id']), r) for r in base['inputs']['requests']), 'ORIGINAL_REQUESTS_CHANGED')
    require(d['inputs_sha256'] == sha(encode(d['inputs'])), 'INPUT_PAYLOAD_HASH')
    policy = read('docs/v3/contract-proposals/port-resource-policy-v3.json')
    catalog = {a['archetype_id']: a for a in read('docs/v3/contract-proposals/cargo-catalog-v3.json')['records']}
    ports = {p['port_id']: p for p in d['inputs']['ports']}
    profiles = read(PROFILES)
    require(profiles['handling_policy']['manual_mass_limit_kg'] == c07['manual_boundary_fixture']['synthetic_manual_limit_kg'] == 15, 'MANUAL_LIMIT')
    for pair in policy['forklift_pairs']:
        profile = next(p for p in profiles['profiles'] if p['worker_id'] == pair['actor_id'])
        require('forklift' in profile['allowed_handlers'] and 'forklift' in profile['allowed_equipment'] and
            pair['vehicle_id'] in profile['allowed_vehicle_ids'] and dict(driver_actor_id=pair['actor_id'], vehicle_id=pair['vehicle_id'])
            in d['inputs']['vehicles'], 'CURRENT_DRIVER_CAPABILITY')
    for request, handling in zip(d['inputs']['requests'], d['handling_requirements']):
        require(request['request_id'] == handling['request_id'], 'REQUEST_HANDLING_IDENTITY')
        handling_check(request, handling, catalog[request['archetype_id']], ports[request['port_id']], c08, policy)
    storage = read('docs/v3/contract-proposals/storage-slots-v3.json')
    slots, modules = [{row[key]: row for row in storage[collection]} for key, collection in [('slot_id', 'slots'), ('module_id', 'modules')]]
    stock = d['inputs']['initial_stock']
    occupied = Counter(hu['location']['slot_id'] for hu in stock)
    module_mass = defaultdict(lambda: Decimal(0))
    for hu in stock:
        module_mass[hu['location']['module_id']] += Decimal(str(hu['gross_mass_kg']))
    for hu in stock:
        slot = slots[hu['location']['slot_id']]
        require(hu['location']['module_id'] == slot['module_id'], 'STORAGE_MODULE_MISMATCH')
        verdict = evaluate(catalog[hu['archetype_id']], slot, modules[slot['module_id']], orientation_id=hu['orientation_id'],
            occupied_units=occupied[slot['slot_id']] - 1,
            module_mass_kg=float(module_mass[slot['module_id']] - Decimal(str(hu['gross_mass_kg']))))
        require(verdict['design_eligible'] and same(verdict['details']['placement'], hu['location']['placement']), 'INITIAL_STORAGE_INELIGIBLE')
    return dict(original_stock_HUs=530, original_stock_units=12256, original_stock_mass_kg='9403.85',
        SKUs=200, workers=24, vehicles=2, ports=6, original_requests=16, total_requests=28,
        original_upstream_HUs=8, added_external_HUs=12, added_external_units=132, added_external_mass_kg='5236.0',
        current_handling_checks=28, original_design_eligible_placements=530,
        same_original_initial_state_for_both_pair_references=True, adaptive_placement_decision='not_evaluated')


def verify_pair(pair, d):
    reference = {**ref(INPUT), 'inputs_sha256': d['inputs_sha256']}
    expected = dict(schema_id='qoima.heavy-inbound-current-pair.v3', task_id='W11.1.1', source_kind='visual_fixture',
        engine_operation=False, operational_admission=False, execution_ready=False,
        paired_runs=[dict(variant=v, input_ref=reference) for v in ['baseline', 'adaptive']],
        comparison_policy=d['comparison_policy'],
        scope='Identical current input bytes. Same original initial placement; no adaptive placement decision or relocation/run result.')
    require(same(pair, expected), 'PAIRED_INPUT_OR_OVERRIDE')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    ctx = context()
    d, pair, migration = [read(p) for p in [INPUT, PAIR, MIGRATION]]
    for path, value in [(INPUT, d), (PAIR, pair), (MIGRATION, migration)]:
        require((ROOT / path).read_bytes() == encode(value), 'NONCANONICAL_OUTPUT_BYTES')
    migration_summary = verify_migration(migration)
    summary = verify_document(d, migration, ctx)
    verify_pair(pair, d)
    negatives = []

    def reject(name, action, expected):
        try:
            action()
        except ValueError as error:
            require(str(error) == expected, name + ': ' + str(error))
            negatives.append(dict(case=name, rejected=True, reason=str(error)))
        else:
            raise ValueError('NEGATIVE_ACCEPTED: ' + name)

    def input_attack(name, mutate, expected):
        changed = copy.deepcopy(d)
        mutate(changed)
        changed['inputs_sha256'] = sha(encode(changed['inputs']))
        reject(name, lambda: verify_document(changed, migration, ctx), expected)

    input_attack('stale_current_source', lambda x: x['source_hashes'].update({BASE: '0' * 64}), 'CURRENT_SOURCE_HASHES')
    input_attack('partial_four_unit_pallet', lambda x: next(r for r in x['inputs']['requests'] if r['request_id'] == 'v3:request:W11:external:01').update(quantity_units=4), 'FROZEN_HEAVY_WORKLOAD_OR_POLICY')
    input_attack('dimensional_mass_shrink', lambda x: x['external_receipts'][0].update(dimensions_xyz_m=[.1, .1, .1], gross_mass_kg=1), 'FROZEN_HEAVY_WORKLOAD_OR_POLICY')
    input_attack('heavy_manual_mode', lambda x: next(h for h in x['handling_requirements'] if h['request_id'] == 'v3:request:W11:external:01').update(handling_mode='manual_within_worker_and_handling_unit_limits'), 'FROZEN_HEAVY_WORKLOAD_OR_POLICY')
    changed_pair = copy.deepcopy(pair)
    changed_pair['paired_runs'][1]['input_ref']['sha256'] = '0' * 64
    reject('adaptive_source_mutation', lambda: verify_pair(changed_pair, d), 'PAIRED_INPUT_OR_OVERRIDE')
    changed_profiles = copy.deepcopy(read(PROFILES))
    changed_profiles['profiles'][0]['allowed_handlers'] = []
    reject('worker_capability_mutation', lambda: capabilities_unchanged(read(PROFILES), changed_profiles), 'WORKER_CAPABILITIES_CHANGED')
    reject('wrong_authority_bytes', lambda: check_pin(b'invented', PINS[BASE]), 'PINNED_SOURCE_DRIFT')
    storage = read('docs/v3/contract-proposals/storage-slots-v3.json')
    cargo = next(a for a in read('docs/v3/contract-proposals/cargo-catalog-v3.json')['records'] if a['archetype_id'] == 'IBC')
    slot = next(s for s in storage['slots'] if s['storage_type'] == 'HEAVY' and not s['retrieval_blocked'])
    module = next(m for m in storage['modules'] if m['module_id'] == slot['module_id'])

    def storage_attack(**kwargs):
        verdict = evaluate(kwargs.pop('cargo', cargo), kwargs.pop('slot', slot), module, **kwargs)
        require(verdict['design_eligible'], verdict['reason'])

    reject('IBC_manual_handler', lambda: storage_attack(transport_tag='manual_hand_carry'), 'HANDLER_UNAVAILABLE')
    reject('missing_forklift_handler', lambda: storage_attack(handler_available=False), 'HANDLER_UNAVAILABLE')
    light_slot = copy.deepcopy(slot)
    light_slot['max_payload_kg'] = 500
    reject('654kg_IBC_over_500kg_isolated_slot', lambda: storage_attack(slot=light_slot), 'OVERWEIGHT')
    wide_cargo = copy.deepcopy(cargo)
    wide_cargo['handling_unit']['dimensions_xyz_m'] = [99, 1.16, 1]
    reject('invalid_HU_dimensions', lambda: storage_attack(cargo=wide_cargo), 'DIMENSION_MISMATCH')
    require(verify_document(d, migration, ctx) == summary, 'NONREPRODUCIBLE_AUDIT')
    artifact_paths = [INPUT, PAIR, MIGRATION, 'docs/adaptive-v3/specs/W11.1.1.md',
        'tools/visual/v3/build_heavy_inbound_current_scenario.py', 'tools/visual/v3/verify_heavy_inbound_current_scenario.py']
    report = dict(task_id='W11.1.1', status='input_only_current_source_candidate_pending_root_review',
        source_kind='visual_fixture', engine_operation=False, operational_admission=False, execution_ready=False,
        input_compatibility_verified=True, summary=summary, migration=migration_summary,
        current_base_fixture_ref=ref(BASE), historical_input_ref=ref(HISTORICAL),
        paired_inputs_identical=True, canonical_storage_eligibility_includes_occupancy_and_module_mass=True,
        targeted_negative_cases=negatives, source_hashes=ctx[4], artifacts={p: ref(p) for p in artifact_paths},
        graph_scope='Tier2 qoima-twin generation2026-11-08T05:55:56Z; changed/untracked evidence read directly, no graph refresh.',
        scope='Source/input compatibility and design eligibility only. Historical W11.1 unchanged. No admitted placement, actual route, queue, resources, adaptive result, metrics, engine or W11 acceptance.')
    data = encode(report)
    if args.check_only:
        require((ROOT / REPORT).read_bytes() == data, 'STALE_COMPATIBILITY_REPORT')
    else:
        (ROOT / REPORT).write_bytes(data)
    print(json.dumps(dict(input_compatibility_verified=True, paired_inputs_identical=True,
        original_placements=530, request_handling_checks=28, targeted_negatives=len(negatives),
        migration=migration_summary, check_only=args.check_only)))


if __name__ == '__main__':
    main()
