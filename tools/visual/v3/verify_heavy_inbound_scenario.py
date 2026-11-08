"""Independent source and semantic audit. Never imports the scenario builder."""
import argparse
import copy
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
FIXTURE = 'docs/adaptive-v3/fixtures/scenarios/W11-heavy-inbound-input-v3.json'
EVIDENCE = 'docs/adaptive-v3/evidence/W11.1.json'
REPORT = 'docs/adaptive-v3/evidence/W11.1-checks.json'
C08 = 'docs/v3/contract-proposals/vehicle-handling-v3.json'
C07 = 'docs/v3/contract-proposals/cargo-mass-cases-v3.json'
POLICY = 'docs/v3/contract-proposals/port-resource-policy-v3.json'
PINS = {BASE:'52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91',
    C08:'22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4',
    C07:'3d4e15a4941f4692d14238f4891a1ca24bdd46858e327d4e1e0682fb2b4e25ce'}
TOP = set('schema_id schema_version task_id scenario_id source_kind engine_operation actual_engine_run execution_ready operational_admission actual_v3_run_supported visual_complete backend_integration_complete execution_state metrics_scope status base_fixture_ref source_hashes clock layout_ref registry_ref profiles_ref inputs original_upstream external_receipts handling_requirements preregistration comparison_policy required_before_execution actions completion_events inputs_sha256'.split())
HU_FIELDS = set('handling_unit_id lot_id request_id sku_id archetype_id source_catalogue_id source_catalogue_pointer quantity_units dimensions_xyz_m gross_mass_kg orientation_id model_scale_factor origin location_kind state included_in_initial_stock'.split())
HANDLING_FIELDS = set('request_id handling_mode equipment_pair_ref geometry_profile_id attachment_id rating_source operational_admission'.split())
SCOPE = dict(source_kind='visual_fixture',engine_operation=False,actual_engine_run=False,execution_ready=False,
    operational_admission=False,actual_v3_run_supported=False,visual_complete=False,backend_integration_complete=False,
    execution_state='not_scheduled',metrics_scope='none',status='input_only_candidate_pending_root_review')
PREREQUISITES = ['W05_unified_actions_and_clock','W11_loaded_physical_and_route_admission',
    'finite_staging_and_exclusive_original_resources','priced_relocations_and_admissible_baseline_candidate',
    'root_scene_replay_and_comparison_review','supported_backend_adapter_for_actual_engine_runs']


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf8')


def same_json(value, expected):
    # Python treats True == 1 and False == 0. Frozen JSON source identity must not.
    try:
        return encoded(value) == encoded(expected)
    except (TypeError, ValueError, OverflowError):
        return False


def finite_number(value, *, positive=False):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        return False


def positive_integer(value):
    return type(value) is int and value > 0


def positive_dimensions(value):
    return type(value) is list and len(value) == 3 and all(finite_number(v, positive=True) for v in value)


def source_cargo_numbers(cargo):
    unit, hu = cargo['unit'], cargo['handling_unit']
    require(positive_integer(hu['units_per_handling_unit']) and
        all(positive_dimensions(row['dimensions_xyz_m']) and
            finite_number(row['gross_mass_kg'], positive=True) and
            finite_number(row['packaging_tare_mass_kg']) and
            finite_number(row['bounding_volume_m3'], positive=True) for row in (unit, hu)) and
        finite_number(unit['contents_mass_kg']) and finite_number(hu['contents_gross_mass_kg']), 'SOURCE_CARGO_NUMERIC_FIELDS')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_context():
    for p, digest in PINS.items():
        require(sha((ROOT/p).read_bytes()) == digest, 'PINNED_SOURCE_DRIFT')
    b, c, m = read(BASE), read(C08), read(C07)
    fingerprints = {**b['source_hashes'], **PINS}
    for row in c['source_fingerprints']+m['source_fingerprints']:
        require(row['path'] not in fingerprints or fingerprints[row['path']] == row['sha256'], 'CONFLICTING_SOURCE_AUTHORITY')
        fingerprints[row['path']] = row['sha256']
    for path, digest in fingerprints.items():
        require(sha((ROOT/path).read_bytes()) == digest, 'CANONICAL_SOURCE_DRIFT')
    catalogue = read('docs/v3/contract-proposals/cargo-catalog-v3.json')['records']
    for a in b['inputs']['archetypes']:
        source_cargo_numbers(a)
        source = next(row for row in catalogue if row['archetype_id']==a['archetype_id'])
        require(all(same_json(a[key],source[key]) for key in a), 'W01_C02_CATALOGUE_DRIFT')
        ledger = next(row for row in m['production_ledgers'] if row['archetype_id']==a['archetype_id'])
        require(ledger['HU_gross_kg']==a['handling_unit']['gross_mass_kg'] and
            ledger['unit_count']==a['handling_unit']['units_per_handling_unit'], 'C07_CATALOGUE_DRIFT')
    profiles = read(b['profiles_ref']['path'])
    require(profiles['handling_policy']['manual_mass_limit_kg']==m['manual_boundary_fixture']['synthetic_manual_limit_kg']==15,
        'MANUAL_SOURCE_LIMIT_DRIFT')
    for pair in read(POLICY)['forklift_pairs']:
        profile = next(row for row in profiles['profiles'] if row['worker_id']==pair['actor_id'])
        require('forklift' in profile['allowed_handlers'] and 'forklift' in profile['allowed_equipment'] and
            pair['vehicle_id'] in profile['allowed_vehicle_ids'] and
            dict(driver_actor_id=pair['actor_id'],vehicle_id=pair['vehicle_id']) in b['inputs']['vehicles'], 'DRIVER_SOURCE_PROFILE')
    return b,c,m,read(POLICY),fingerprints


def handling_check(r, h, cargo, port, c, policy):
    source_cargo_numbers(cargo)
    require(set(h) == HANDLING_FIELDS and h['operational_admission'] is False, 'HANDLING_FIELDS_OR_ADMISSION')
    require(r['archetype_id'] in port['allowed_cargo_archetype_ids'] and r['direction'] == port['direction'], 'PORT_CARGO_OR_DIRECTION')
    rule = next(x for x in port['resource_requirements'] if r['archetype_id'] in x['cargo_archetype_ids'])
    require(h['handling_mode'] == rule['handling_mode'], 'HANDLING_MODE')
    require(h['equipment_pair_ref'] == rule['forklift_pair_ref'], 'HANDLER_PAIR')
    load = next((x for x in c['loads'] if x['archetype_id'] == r['archetype_id']),None)
    if not load:
        require(cargo['handling_unit']['gross_mass_kg'] <= 15 and
            h['geometry_profile_id'] is None and h['attachment_id'] is None and h['rating_source'] is None, 'MANUAL_LIMIT_OR_PROFILE')
        return
    pair = next((x for x in policy['forklift_pairs'] if x['pair_id'] == h['equipment_pair_ref']),None)
    require(pair is not None and pair['eligible_direction'] == r['direction'], 'HANDLER_DIRECTION')
    cp = next(x for x in c['ports'] if x['port_id'] == r['port_id'])
    require(r['archetype_id'] in cp['forklift_cargo_archetype_ids'] and cp['equipment_pair_ref'] == pair['pair_id'], 'C08_PORT_HANDLER')
    require(h['geometry_profile_id'] == load['local_geometry_profile_id'] and h['rating_source'] == C08, 'LOAD_PROFILE')
    attachment = c['long_cradle_design']['attachment_id'] if r['archetype_id'] == 'LONG_BUNDLE' else None
    require(h['attachment_id'] == attachment, 'REQUIRED_ATTACHMENT')
    rating = c['rating_design']
    require(all(finite_number(load[k], positive=True) for k in
        ['HU_gross_mass_kg','total_lifted_mass_kg','extended_handling_rating_arm_from_fixed_Z04_m']) and
        finite_number(load['attachment_mass_kg']) and positive_dimensions(load['handling_unit_dimensions_xyz_m']) and
        all(finite_number(rating[k], positive=True) for k in
            ['nominal_capacity_kg','moment_budget_kg_m','maximum_single_fork_share_kg']), 'SOURCE_LOAD_NUMERIC_FIELDS')
    mass = Decimal(str(cargo['handling_unit']['gross_mass_kg'])) + Decimal(str(load['attachment_mass_kg']))
    arm = Decimal(str(load['extended_handling_rating_arm_from_fixed_Z04_m']))
    require(arm > 0 and mass <= min(Decimal(str(rating['nominal_capacity_kg'])),Decimal(str(rating['moment_budget_kg_m']))/arm)
        and mass/2 <= Decimal(str(rating['maximum_single_fork_share_kg'])), 'RATING_VIOLATION')
    require(load['HU_gross_mass_kg'] == cargo['handling_unit']['gross_mass_kg'] and
        load['handling_unit_dimensions_xyz_m'] == cargo['handling_unit']['dimensions_xyz_m'], 'C08_CATALOGUE_MISMATCH')


def verify(d):
    # Reopen actual sources on every semantic invocation, including negative cases.
    b,c,m,policy,fingerprints = source_context()
    require(set(d) == TOP, 'UNAUTHORIZED_FIELD')
    require(all(type(d[k]) is type(v) and d[k] == v for k,v in SCOPE.items()), 'FABRICATED_SCOPE')
    require(d['actions'] == [] and d['completion_events'] == [], 'FABRICATED_EXECUTION')
    require((d['schema_id'],d['schema_version'],d['task_id'],d['scenario_id']) ==
        ('qoima.heavy-inbound-input.v3','0.1.0','W11.1','v3:scenario:N2_HEAVY_INBOUND:001'), 'SCENARIO_ID')
    require(d['source_hashes'] == fingerprints and d['base_fixture_ref'] == dict(path=BASE,sha256=PINS[BASE]), 'SOURCE_HASHES')
    for key in ['clock','layout_ref','registry_ref','profiles_ref']:
        require(same_json(d[key],b[key]), 'REFERENCE_OR_CLOCK')
    x = d['inputs']
    require(set(x) == set(b['inputs']), 'INPUT_FIELDS')
    for key in set(x)-{'requests'}:
        require(same_json(x[key],b['inputs'][key]), 'ORIGINAL_'+key.upper())
    catalog = {a['archetype_id']:a for a in b['inputs']['archetypes']}
    skus = {s['sku_id']:s for s in b['inputs']['skus']}
    stock = {h['handling_unit_id']:h for h in x['initial_stock']}
    original = {r['request_id']:r for r in b['inputs']['requests']}
    requests = x['requests']
    require(len(requests) == 28 and len({r['request_id'] for r in requests}) == 28 and
        len({r['handling_unit_id'] for r in requests}) == 28 and len({r['lot_id'] for r in requests}) == 28, 'REQUEST_IDENTITIES')
    req = {r['request_id']:r for r in requests}
    require(set(original) <= set(req), 'ORIGINAL_REQUEST_MISSING')
    require(all(same_json(req[k],v) for k,v in original.items()), 'ORIGINAL_REQUEST_CHANGED')
    require(requests == sorted(requests,key=lambda r:(r['requested_at_s'],r['request_id'])), 'REQUEST_ORDER')
    p = d['preregistration']
    require(set(p) == set('synthetic_design_assumption added_HUs repeating_archetypes port_id first_release_s interval_s last_release_s deadline_offset_s release_rate selection_basis'.split()), 'RATE_FIELDS')
    require(same_json(p,dict(synthetic_design_assumption=True,added_HUs=12,repeating_archetypes=['PALLET_LOAD','IBC','HEAVY_BOX'],
        port_id='IN_W_BULK',first_release_s=90,interval_s=60,last_release_s=750,deadline_offset_s=600,
        release_rate=dict(numerator_HUs=1,denominator_seconds=60,scope='added_release_schedule_only'),
        selection_basis='Mixed pallet, sealed IBC and heavy box; fixed before comparisons; no optimization result used.')), 'PREREGISTERED_RATE')
    upstream = d['original_upstream'] + d['external_receipts']
    require(len(d['original_upstream']) == 8 and len(d['external_receipts']) == 12 and
        all(len({h[k] for h in upstream}) == 20 for k in ['handling_unit_id','lot_id','request_id']), 'UPSTREAM_IDENTITIES')
    incoming = {r['request_id'] for r in requests if r['direction'] == 'inbound'}
    require({h['request_id'] for h in upstream} == incoming, 'UPSTREAM_REQUEST_LINK')
    ports = {p['port_id']:p for p in x['ports']}
    for r in requests:
        require(set(r) == set(b['inputs']['requests'][0]), 'REQUEST_FIELDS')
        require(r['sku_id'] in skus and r['archetype_id'] == skus[r['sku_id']]['archetype_id'], 'SKU_ARCHETYPE')
        a = catalog[r['archetype_id']]
        require(positive_integer(r['quantity_units']) and r['quantity_units'] == a['handling_unit']['units_per_handling_unit'] and
            positive_integer(r['quantity_handling_units']) and r['quantity_handling_units'] == 1, 'REQUEST_UNITS')
        require(r['port_id'] in ports, 'UNKNOWN_PORT')
        port = ports[r['port_id']]
        require(r['direction'] == port['direction'] and r['archetype_id'] in port['allowed_cargo_archetype_ids'], 'PORT_CARGO_OR_DIRECTION')
        at,end = r['requested_at_s'],r['deadline_at_s']
        require(finite_number(at) and finite_number(end, positive=True) and at < end <= 1800 and
            any(start <= at < stop for start,stop in port['open_windows']), 'REQUEST_TIME')
        require(r['engine_operation'] is False and r['source_kind'] == 'visual_fixture' and
            r['kind'] == ('receipt_request' if r['direction']=='inbound' else 'order_request'), 'REQUEST_SCOPE')
        incoming_hu = r['direction'] == 'inbound'
        require(r['included_in_initial_stock'] is (not incoming_hu) and r['initial_location_kind'] == ('upstream' if incoming_hu else 'storage_slot') and
            (r['handling_unit_id'] not in stock if incoming_hu else r['handling_unit_id'] in stock), 'UPSTREAM_STOCK_CONFUSION')
    for index,h in enumerate(upstream):
        require(set(h) == HU_FIELDS, 'HU_FIELDS')
        require(positive_integer(h['quantity_units']) and positive_dimensions(h['dimensions_xyz_m']) and
            finite_number(h['gross_mass_kg'], positive=True) and
            finite_number(h['model_scale_factor'], positive=True), 'HU_NUMERIC_FIELDS')
        r = req[h['request_id']]
        require(all(h[k] == r[k] for k in ['handling_unit_id','lot_id','sku_id','archetype_id','quantity_units']), 'HU_REQUEST_LINK')
        a = catalog[h['archetype_id']]
        require(h['source_catalogue_id'] == h['sku_id'] and h['source_catalogue_pointer'] == skus[h['sku_id']]['cargo_template_pointer'], 'CATALOGUE_LINK')
        require(h['dimensions_xyz_m'] == a['handling_unit']['dimensions_xyz_m'] and h['gross_mass_kg'] == a['handling_unit']['gross_mass_kg'] and
            h['orientation_id'] in [o['orientation_id'] for o in a['orientation']['permitted_orientations']] and
            type(h['model_scale_factor']) is int and h['model_scale_factor'] == 1, 'CATALOGUE_PHYSICS')
        unit = a['unit']; hu = a['handling_unit']
        require(Decimal(str(unit['contents_mass_kg']))+Decimal(str(unit['packaging_tare_mass_kg'])) == Decimal(str(unit['gross_mass_kg'])) and
            Decimal(str(unit['gross_mass_kg']))*h['quantity_units']+Decimal(str(hu['packaging_tare_mass_kg'])) == Decimal(str(h['gross_mass_kg'])), 'MASS_LEDGER')
        require(h['location_kind']=='upstream' and h['state']=='planned_input' and h['included_in_initial_stock'] is False and
            h['origin']==('original_W01_upstream' if index < 8 else 'external_synthetic_supplier'), 'RECEIPT_STATE')
        if index < 8:
            require(h['request_id'] in original and h['request_id'] == [v['request_id'] for v in b['inputs']['requests'] if v['direction']=='inbound'][index], 'ORIGINAL_UPSTREAM_CHANGED')
        else:
            n = index-7
            require(h['handling_unit_id']==f'v3:HU:W11:external:{n:02}' and h['lot_id']==f'v3:lot:W11:external:{n:02}' and
                h['request_id']==f'v3:request:W11:external:{n:02}', 'EXTERNAL_ID')
            expected_class = ('PALLET_LOAD','IBC','HEAVY_BOX')[(n-1)%3]
            source = next(v for v in original.values() if v['direction']=='inbound' and v['archetype_id']==expected_class)
            require(h['archetype_id']==expected_class and h['sku_id']==source['sku_id'], 'HEAVY_MIX')
            require(r['requested_at_s']==30+60*n and r['deadline_at_s']==630+60*n and r['port_id']=='IN_W_BULK', 'EXTERNAL_RELEASE_OR_PORT')
    hs = d['handling_requirements']
    require(len(hs)==28 and [h['request_id'] for h in hs]==[r['request_id'] for r in requests], 'HANDLING_LINK')
    for r,h in zip(requests,hs):
        handling_check(r,h,catalog[r['archetype_id']],ports[r['port_id']],c,policy)
    require(same_json(d['comparison_policy'],dict(kind='slotting_only',same_concrete_input_required=True,
        allowed_output_differences=['admitted_HU_slot_placement','explicit_relocation_sequence_and_cost'],
        decision_state='not_evaluated',no_op_allowed=True,force_improvement=False)), 'COMPARISON_OVERRIDE')
    require(d['required_before_execution'] == PREREQUISITES, 'RUNTIME_GATE_REMOVED')
    require(d['inputs_sha256']==sha(encoded(x)), 'INPUT_DIGEST')
    return dict(requests=28, original_requests=16, added_requests=12, initial_HUs=530, workers=24,vehicles=2,
        initial_units=12256,initial_mass_kg='9403.85',original_upstream_HUs=8,original_upstream_units=107,
        original_upstream_mass_kg='1784.29',added_HUs=12,added_units=132,added_mass_kg='5236.0',
        port_requests=dict(sorted(Counter(r['port_id'] for r in requests).items())),
        handling_modes=dict(sorted(Counter(h['handling_mode'] for h in hs).items())))


def verify_pair(e,d,raw):
    require(set(e)==set('task_id status source_kind engine_operation actual_engine_run execution_ready input_ref paired_runs full_identity_lists summary source_hashes scope'.split()), 'EVIDENCE_FIELDS')
    require(e['task_id']=='W11.1' and all(type(e[k]) is type(SCOPE[k]) and e[k]==SCOPE[k] for k in ['status','source_kind','engine_operation','actual_engine_run','execution_ready']), 'EVIDENCE_SCOPE')
    ref = dict(path=FIXTURE,sha256=sha(raw),bytes=len(raw))
    require(same_json(e['input_ref'],ref) and same_json(e['paired_runs'],[dict(variant=v,input_ref=ref) for v in ['baseline','adaptive']]), 'PAIRED_CONCRETE_INPUT')
    u = d['original_upstream']+d['external_receipts']
    require(e['full_identity_lists']==dict(request_ids=[r['request_id'] for r in d['inputs']['requests']],
        initial_HU_ids=[h['handling_unit_id'] for h in d['inputs']['initial_stock']],upstream_HU_ids=[h['handling_unit_id'] for h in u],
        upstream_lot_ids=[h['lot_id'] for h in u]), 'EVIDENCE_IDENTITIES')
    require(e['source_hashes']==d['source_hashes'], 'EVIDENCE_SOURCES')
    def total(rows):
        return dict(HUs=len(rows),units=sum(h['quantity_units'] for h in rows),
            gross_mass_kg=str(sum((Decimal(str(h['gross_mass_kg'])) for h in rows),Decimal(0))))
    require(same_json(e['summary'],dict(initial_stock=total(d['inputs']['initial_stock']),original_upstream=total(d['original_upstream']),
        added_external=total(d['external_receipts']),all_upstream=total(u),original_requests=16,added_requests=12,
        total_requests=28,outbound_existing_requests=8,workers=24,powered_vehicles=2)), 'EVIDENCE_SUMMARY')
    require(e['scope']=='Input integrity candidate only. No root PASS, arrival, completed receipt, queue, runtime or performance acceptance.', 'EVIDENCE_CLAIM')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    raw=(ROOT/FIXTURE).read_bytes();d=json.loads(raw);e=read(EVIDENCE)
    summary=verify(d);verify_pair(e,d,raw)
    require(raw==encoded(d), 'NONCANONICAL_BYTES')
    cases=[]
    def reject(name,mutation,reason):
        changed=copy.deepcopy(d);mutation(changed)
        try:
            changed['inputs_sha256']=sha(encoded(changed['inputs']))
            rehashed=True
        except (TypeError,ValueError,OverflowError):
            rehashed=False  # Nonfinite input is not serializable JSON; still exercise the semantic guard.
        try:
            verify(changed)
        except ValueError as error:
            require(str(error)==reason, name+': '+str(error)+' expected '+reason)
            cases.append(dict(case=name,reason=str(error),rejected=True,source_rechecked=True,superficial_hash_recomputed=rehashed))
        else:
            raise AssertionError('Accepted negative: '+name)
    for field in ['engine_operation','actual_engine_run','execution_ready','operational_admission','visual_complete','backend_integration_complete']:
        reject('fabricated_'+field,lambda x,k=field:x.update({k:True}),'FABRICATED_SCOPE')
    reject('actual_source_kind',lambda x:x.update(source_kind='actual_engine_run'),'FABRICATED_SCOPE')
    reject('completed_event',lambda x:x['completion_events'].append({'completed':True}),'FABRICATED_EXECUTION')
    reject('invented_action',lambda x:x['actions'].append({'at_s':1}),'FABRICATED_EXECUTION')
    reject('throughput',lambda x:x.update(throughput=100),'UNAUTHORIZED_FIELD')
    reject('stale_hash',lambda x:x['source_hashes'].update({C08:'0'*64}),'SOURCE_HASHES')
    for field in ['initial_stock','workers','vehicles','ports','archetypes','skus']:
        reject('changed_'+field,lambda x,k=field:x['inputs'][k].pop(),'ORIGINAL_'+field.upper())
    reject('stock_mass',lambda x:x['inputs']['initial_stock'][0].update(gross_mass_kg=0.01),'ORIGINAL_INITIAL_STOCK')
    stock_single=next(i for i,h in enumerate(d['inputs']['initial_stock']) if h['quantity_units']==1)
    cargo_ibc=next(i for i,a in enumerate(d['inputs']['archetypes']) if a['archetype_id']=='IBC')
    reject('stock_bool_as_one_unit',lambda x:x['inputs']['initial_stock'][stock_single].update(quantity_units=True),'ORIGINAL_INITIAL_STOCK')
    reject('frozen_catalogue_bool_dimension',lambda x:x['inputs']['archetypes'][cargo_ibc]['handling_unit']['dimensions_xyz_m'].__setitem__(2,True),'ORIGINAL_ARCHETYPES')
    reject('original_upstream_request',lambda x:x['inputs']['requests'][0].update(quantity_units=4),'ORIGINAL_REQUEST_CHANGED')
    reject('duplicate_request',lambda x:x['inputs']['requests'].append(copy.deepcopy(x['inputs']['requests'][0])),'REQUEST_IDENTITIES')
    reject('unknown_request_ID',lambda x:x['inputs']['requests'][0].update(request_id='unknown'),'ORIGINAL_REQUEST_MISSING')
    reject('duplicate_HU',lambda x:x['external_receipts'][1].update(handling_unit_id=x['external_receipts'][0]['handling_unit_id']),'UPSTREAM_IDENTITIES')
    reject('duplicate_lot',lambda x:x['external_receipts'][1].update(lot_id=x['external_receipts'][0]['lot_id']),'UPSTREAM_IDENTITIES')
    reject('missing_upstream',lambda x:x['original_upstream'].pop(),'UPSTREAM_IDENTITIES')
    reject('unknown_HU',lambda x:x['external_receipts'][0].update(handling_unit_id='unknown'),'HU_REQUEST_LINK')
    reject('unknown_lot',lambda x:x['external_receipts'][0].update(lot_id='unknown'),'HU_REQUEST_LINK')
    reject('unknown_receipt_request',lambda x:x['external_receipts'][0].update(request_id='unknown'),'UPSTREAM_REQUEST_LINK')
    for field,value in [('gross_mass_kg',1),('dimensions_xyz_m',[1,1,1]),('orientation_id','sideways'),('model_scale_factor',0.5)]:
        reject('wrong_'+field,lambda x,k=field,v=value:x['external_receipts'][0].update({k:v}),'CATALOGUE_PHYSICS')
    # IBC has exactly one unit and a 1m third side: these attack Python's True == 1 loophole.
    ibc=next(i for i,h in enumerate(d['external_receipts']) if h['archetype_id']=='IBC')
    for label,value in [('bool',True),('float',1.0),('string','1'),('zero',0),('negative',-1)]:
        reject('materialized_IBC_quantity_'+label,lambda x,v=value:x['external_receipts'][ibc].update(quantity_units=v),'HU_NUMERIC_FIELDS')
    for label,value in [('bool',True),('string','1'),('zero',0),('negative',-1),('nan',float('nan')),('infinite',float('inf'))]:
        reject('materialized_IBC_dimension_'+label,lambda x,v=value:x['external_receipts'][ibc]['dimensions_xyz_m'].__setitem__(2,v),'HU_NUMERIC_FIELDS')
    reject('materialized_dimensions_length',lambda x:x['external_receipts'][ibc].update(dimensions_xyz_m=[1,1]),'HU_NUMERIC_FIELDS')
    for label,value in [('bool',True),('string','654'),('zero',0),('negative',-1),('nan',float('nan')),('infinite',float('inf'))]:
        reject('materialized_mass_'+label,lambda x,v=value:x['external_receipts'][ibc].update(gross_mass_kg=v),'HU_NUMERIC_FIELDS')
    reject('materialized_bool_scale',lambda x:x['external_receipts'][ibc].update(model_scale_factor=True),'HU_NUMERIC_FIELDS')
    reject('materialized_float_scale',lambda x:x['external_receipts'][ibc].update(model_scale_factor=1.0),'CATALOGUE_PHYSICS')
    reject('catalogue_ID',lambda x:x['external_receipts'][0].update(source_catalogue_id='unknown'),'CATALOGUE_LINK')
    reject('catalogue_pointer',lambda x:x['external_receipts'][0].update(source_catalogue_pointer='/records/0'),'CATALOGUE_LINK')
    reject('completed_receipt',lambda x:x['external_receipts'][0].update(state='received'),'RECEIPT_STATE')
    reject('invented_stock_origin',lambda x:x['external_receipts'][0].update(included_in_initial_stock=True),'RECEIPT_STATE')
    reject('rate_changed',lambda x:x['preregistration'].update(interval_s=1),'PREREGISTERED_RATE')
    reject('extra_rate',lambda x:x['preregistration'].update(throughput=999),'RATE_FIELDS')
    reject('rate_bool_as_one_HU',lambda x:x['preregistration']['release_rate'].update(numerator_HUs=True),'PREREGISTERED_RATE')
    reject('rate_integer_as_design_flag',lambda x:x['preregistration'].update(synthetic_design_assumption=1),'PREREGISTERED_RATE')
    reject('rate_float_HU_count',lambda x:x['preregistration'].update(added_HUs=12.0),'PREREGISTERED_RATE')
    reject('hidden_override',lambda x:x['comparison_policy'].update(service_multiplier=0.1),'COMPARISON_OVERRIDE')
    reject('integer_as_comparison_flag',lambda x:x['comparison_policy'].update(same_concrete_input_required=1),'COMPARISON_OVERRIDE')
    reject('integer_as_no_op_flag',lambda x:x['comparison_policy'].update(no_op_allowed=1),'COMPARISON_OVERRIDE')
    reject('removed_runtime_gate',lambda x:x.update(required_before_execution=[]),'RUNTIME_GATE_REMOVED')
    reject('loaded_profile',lambda x:x['handling_requirements'][1].update(geometry_profile_id='unloaded_bare'),'LOAD_PROFILE')
    long_index=next(i for i,r in enumerate(d['inputs']['requests']) if r['archetype_id']=='LONG_BUNDLE')
    reject('missing_LONG_attachment',lambda x:x['handling_requirements'][long_index].update(attachment_id=None),'REQUIRED_ATTACHMENT')
    heavy_index=next(i for i,r in enumerate(d['inputs']['requests']) if r['request_id']=='v3:request:W11:external:01')
    reject('manual_heavy',lambda x:x['handling_requirements'][heavy_index].update(handling_mode='manual_within_worker_and_handling_unit_limits'),'HANDLING_MODE')
    reject('wrong_pair',lambda x:x['handling_requirements'][heavy_index].update(equipment_pair_ref='OUTBOUND_FORKLIFT_PAIR'),'HANDLER_PAIR')
    def added_request(x):
        return next(r for r in x['inputs']['requests'] if r['request_id']=='v3:request:W11:external:01')
    reject('partial_four_unit_pallet',lambda x:added_request(x).update(quantity_units=4),'REQUEST_UNITS')
    reject('fractional_units',lambda x:added_request(x).update(quantity_units=24.0),'REQUEST_UNITS')
    def added_ibc_request(x):
        return next(r for r in x['inputs']['requests'] if r['request_id']==d['external_receipts'][ibc]['request_id'])
    for label,value in [('bool',True),('float',1.0),('string','1'),('zero',0),('negative',-1)]:
        reject('IBC_request_quantity_'+label,lambda x,v=value:added_ibc_request(x).update(quantity_units=v),'REQUEST_UNITS')
    reject('request_bool_HU_count',lambda x:added_ibc_request(x).update(quantity_handling_units=True),'REQUEST_UNITS')
    reject('deadline_before_release',lambda x:added_request(x).update(deadline_at_s=1),'REQUEST_TIME')
    for label,value in [('bool',True),('string','690'),('zero',0),('negative',-1),('nan',float('nan')),('infinite',float('inf'))]:
        reject('request_deadline_'+label,lambda x,v=value:added_request(x).update(deadline_at_s=v),'REQUEST_TIME')
    def boolean_release(x):
        added_request(x)['requested_at_s']=True
        x['inputs']['requests'].sort(key=lambda r:(r['requested_at_s'],r['request_id']))
    reject('request_boolean_release',boolean_release,'REQUEST_TIME')
    reject('unknown_port',lambda x:added_request(x).update(port_id='missing'),'UNKNOWN_PORT')
    reject('heavy_parcel_port',lambda x:added_request(x).update(port_id='IN_E_PARCEL'),'PORT_CARGO_OR_DIRECTION')
    reject('wrong_port_direction',lambda x:added_request(x).update(port_id='OUT_E_B2B'),'PORT_CARGO_OR_DIRECTION')
    reject('compatible_undeclared_port',lambda x:added_request(x).update(port_id='IN_N_STANDARD'),'EXTERNAL_RELEASE_OR_PORT')
    reject('changed_deadline',lambda x:added_request(x).update(deadline_at_s=700),'EXTERNAL_RELEASE_OR_PORT')
    def release(x):
        added_request(x)['requested_at_s']=91
        x['inputs']['requests'].sort(key=lambda r:(r['requested_at_s'],r['request_id']))
    reject('changed_release',release,'EXTERNAL_RELEASE_OR_PORT')
    def relink(x,field,value):
        x['external_receipts'][0][field]=value
        added_request(x)[field]=value
    reject('coordinated_unknown_HU',lambda x:relink(x,'handling_unit_id','v3:HU:invented'),'EXTERNAL_ID')
    reject('coordinated_unknown_lot',lambda x:relink(x,'lot_id','v3:lot:invented'),'EXTERNAL_ID')
    def relink_request(x):
        r=added_request(x)
        old=r['request_id'];r['request_id']='v3:request:invented'
        x['external_receipts'][0]['request_id']=r['request_id']
        next(h for h in x['handling_requirements'] if h['request_id']==old)['request_id']=r['request_id']
    reject('coordinated_unknown_request',relink_request,'EXTERNAL_ID')
    reject('coordinated_partial_pick',lambda x:relink(x,'quantity_units',4),'REQUEST_UNITS')
    reject('upstream_stock_collision',lambda x:relink(x,'handling_unit_id',x['inputs']['initial_stock'][0]['handling_unit_id']),'REQUEST_IDENTITIES')
    reject('hidden_HU_completion',lambda x:x['external_receipts'][0].update(completed=True),'HU_FIELDS')
    reject('hidden_request_override',lambda x:added_request(x).update(service_seconds=0),'REQUEST_FIELDS')
    reject('invented_handler_admission',lambda x:x['handling_requirements'][heavy_index].update(operational_admission=True),'HANDLING_FIELDS_OR_ADMISSION')
    reject('changed_clock',lambda x:x['clock'].update(duration_s=3600),'REFERENCE_OR_CLOCK')
    reject('frozen_clock_numeric_type',lambda x:x['clock'].update(duration_s=float(d['clock']['duration_s'])),'REFERENCE_OR_CLOCK')
    for name,mut,reason in [('different_path',lambda x:x['paired_runs'][1]['input_ref'].update(path='other.json'),'PAIRED_CONCRETE_INPUT'),
        ('different_hash',lambda x:x['paired_runs'][1]['input_ref'].update(sha256='0'*64),'PAIRED_CONCRETE_INPUT'),
        ('variant_jobs',lambda x:x['paired_runs'][1].update(jobs=[]),'PAIRED_CONCRETE_INPUT'),
        ('both_wrong_ref',lambda x:x.update(input_ref=dict(path='other',sha256='0'*64,bytes=1)),'PAIRED_CONCRETE_INPUT'),
        ('paired_float_byte_count',lambda x:x['paired_runs'][1]['input_ref'].update(bytes=float(len(raw))),'PAIRED_CONCRETE_INPUT'),
        ('summary_float_worker_count',lambda x:x['summary'].update(workers=24.0),'EVIDENCE_SUMMARY')]:
        changed=copy.deepcopy(e);mut(changed);source_context()
        try:verify_pair(changed,d,raw)
        except ValueError as error:
            require(str(error)==reason,name+str(error))
            cases.append(dict(case=name,reason=str(error),rejected=True,source_rechecked=True))
        else:raise AssertionError(name)
    # Independent isolated source-constraint tests, never modifications of production sources.
    b,c,m,policy,_=source_context();r=d['inputs']['requests'][heavy_index];h=d['handling_requirements'][heavy_index]
    cargo=copy.deepcopy(next(a for a in b['inputs']['archetypes'] if a['archetype_id']==r['archetype_id']))
    cargo['handling_unit']['gross_mass_kg']=1001
    try:handling_check(r,h,cargo,next(p for p in b['inputs']['ports'] if p['port_id']==r['port_id']),c,policy)
    except ValueError as error:
        require(str(error)=='RATING_VIOLATION','Rating negative did not exercise rating')
        cases.append(dict(case='isolated_overrating_load',reason=str(error),rejected=True,source_rechecked=True))
    else:raise AssertionError('Rating violation accepted')
    def isolated_numeric(name,mutation,reason):
        b,c,m,policy,_=source_context()
        request=next(r for r in d['inputs']['requests'] if r['request_id']==d['external_receipts'][ibc]['request_id'])
        handling=next(h for h in d['handling_requirements'] if h['request_id']==request['request_id'])
        cargo=copy.deepcopy(next(a for a in b['inputs']['archetypes'] if a['archetype_id']=='IBC'))
        mutation(cargo,c)
        try:handling_check(request,handling,cargo,next(p for p in b['inputs']['ports'] if p['port_id']==request['port_id']),c,policy)
        except ValueError as error:
            require(str(error)==reason,name+': '+str(error)+' expected '+reason)
            cases.append(dict(case=name,reason=str(error),rejected=True,source_rechecked=True,isolated_source_constraint=True))
        else:raise AssertionError('Isolated numeric type accepted: '+name)
    isolated_numeric('source_cargo_bool_unit_count',lambda a,c:a['handling_unit'].update(units_per_handling_unit=True),'SOURCE_CARGO_NUMERIC_FIELDS')
    isolated_numeric('source_cargo_bool_dimension',lambda a,c:a['handling_unit']['dimensions_xyz_m'].__setitem__(2,True),'SOURCE_CARGO_NUMERIC_FIELDS')
    isolated_numeric('source_cargo_bool_tare',lambda a,c:a['handling_unit'].update(packaging_tare_mass_kg=False),'SOURCE_CARGO_NUMERIC_FIELDS')
    isolated_numeric('source_cargo_nonfinite_mass',lambda a,c:a['handling_unit'].update(gross_mass_kg=float('inf')),'SOURCE_CARGO_NUMERIC_FIELDS')
    def ibc_load(c):
        return next(load for load in c['loads'] if load['archetype_id']=='IBC')
    isolated_numeric('source_load_bool_attachment_mass',lambda a,c:ibc_load(c).update(attachment_mass_kg=False),'SOURCE_LOAD_NUMERIC_FIELDS')
    isolated_numeric('source_load_bool_one_metre_arm',lambda a,c:ibc_load(c).update(extended_handling_rating_arm_from_fixed_Z04_m=True),'SOURCE_LOAD_NUMERIC_FIELDS')
    isolated_numeric('source_load_bool_dimension',lambda a,c:ibc_load(c)['handling_unit_dimensions_xyz_m'].__setitem__(2,True),'SOURCE_LOAD_NUMERIC_FIELDS')
    isolated_numeric('source_rating_infinite_budget',lambda a,c:c['rating_design'].update(moment_budget_kg_m=float('inf')),'SOURCE_LOAD_NUMERIC_FIELDS')
    isolated_numeric('source_rating_bool_capacity',lambda a,c:c['rating_design'].update(nominal_capacity_kg=True),'SOURCE_LOAD_NUMERIC_FIELDS')
    require(verify(d)==summary,'NONREPRODUCIBLE_AUDIT');verify_pair(e,d,raw)
    paths=[FIXTURE,EVIDENCE,'docs/adaptive-v3/specs/W11.1.md','tools/visual/v3/build_heavy_inbound_scenario.py','tools/visual/v3/verify_heavy_inbound_scenario.py']
    report=dict(task_id='W11.1',status='input_only_candidate_pending_root_review',source_kind='visual_fixture',
        engine_operation=False,actual_engine_run=False,execution_ready=False,input_integrity_verified=True,
        positive_cases=30,positive_case_definition='28 source-bound request/handling cases, one full semantic/source audit, one exact concrete A/B identity audit',
        negative_case_count=len(cases),negative_cases=cases,summary=summary,paired_inputs_identical=True,
        reproducibility=dict(repeated_semantic_audit_equal=True,canonical_UTF8_LF_bytes=True),
        source_hashes=d['source_hashes'],artifacts={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=sha((ROOT/p).read_bytes())) for p in paths},
        scope='Integrity only; pending root review. No W11/runtime/visual/backend acceptance.')
    data=encoded(report)
    if args.check_only:require((ROOT/REPORT).read_bytes()==data,'STALE_CHECK_REPORT')
    else:(ROOT/REPORT).write_bytes(data)
    print(json.dumps(dict(input_integrity_verified=True,positive_cases=30,negative_cases=len(cases),check_only=args.check_only,summary=summary)))


if __name__=='__main__':
    main()
