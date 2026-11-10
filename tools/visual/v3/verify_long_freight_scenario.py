"""Independent canonical-source and semantic W12.1 audit; no builder import."""
import argparse
import copy
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
C08 = 'docs/v3/contract-proposals/vehicle-handling-v3.json'
ROUTE = 'frontend/public/data/v3/route-policy-v3.json'
GATE = 'docs/v3/contract-proposals/large-gate-v3.json'
FIXTURE = 'docs/adaptive-v3/fixtures/scenarios/W12-long-freight-input-v3.json'
EVIDENCE = 'docs/adaptive-v3/evidence/W12.1.json'
REPORT = 'docs/adaptive-v3/evidence/W12.1-checks.json'
FROZEN = {
    FIXTURE: '7aeccbc8b9b980e5170c9bd63dab5d71d12cf56ff762bd9193cd13414d74a60b',
    'tools/visual/v3/build_long_freight_scenario.py': '4adc10a1be5ed7e36ae1f65cd5188ca5591fac6545120f5181e14057cc3abe4c',
    'docs/adaptive-v3/specs/W12.1.md': 'd73588b61c8789a86ee1588442cd83773a15b31185b557086327ce3fb72ccfa6',
    EVIDENCE: '37f199d93618198bf03c04b0cba08a14182c738e14ded135a1f4c7d8723b6f78',
}
PINS = {
    BASE:'52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91',
    C08:'22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4',
    ROUTE:'24ad87f197d14b1c681814b43b2c8841ca145c6b92515af744f3cb4473d35337',
    'docs/adaptive-v3/evidence/M10.json':'bbc6b7797815f9b3c959bc7c9195db9303fa9e250f4ee1bf6059c5ddd069756b',
    'docs/adaptive-v3/evidence/P09.2.json':'79d8e3d9ee09c27864e762e27fe7f18045ea819a58c6922a87deb4986f595437',
}
SCOPE = dict(source_kind='visual_fixture', engine_operation=False, actual_engine_run=False,
             operational_admission=False, execution_ready=False, execution_state='not_scheduled',
             metrics_scope='none', status='input_only_candidate_pending_root_review')
TOP = set('schema_id schema_version task_id scenario_id status source_kind engine_operation actual_engine_run operational_admission execution_ready execution_state metrics_scope actions completion_events base_fixture_ref source_hashes clock layout_ref registry_ref profiles_ref inputs upstream_handling_units long_requirements preregistration comparison_policy required_before_execution inputs_sha256'.split())
HU_KEYS = set('handling_unit_id lot_id request_id sku_id archetype_id source_catalogue_id source_catalogue_pointer quantity_units dimensions_xyz_m gross_mass_kg orientation_id model_scale_factor origin included_in_initial_stock location_kind state'.split())
LONG_KEYS = set('request_id handling_unit_id lot_id port_id gate_id gate_constraints gate_asset_id mode actor_id vehicle_id equipment_pair_ref handler handling_mode geometry_profile_id loaded_profile attachment_id attachment_mass_kg support_design positive_lock_required independent_restraint_required rating_requirements relative_load_yaw_deg cargo_axes_to_vehicle route operational_admission'.split())
ROUTE_KEYS = set('from_node_id to_node_id node_ids arc_ids endpoint_slot_source_id endpoint_kind source_ref policy_ref closed_arc_ids cost_evaluated storage_assignment operational_admission'.split())
PREREQS = ['W12_root_loaded_contact_lock_clearance_and_gate_crossing',
    'W05_actions_clock_exclusive_resources_finite_staging', 'admitted_baseline_and_candidate_storage_and_priced_relocations',
    'explicit_runtime_registration_and_root_review', 'supported_engine_adapter_for_actual_engine_runs']


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def same(a, b):
    """Source identity includes JSON primitive types, container shapes and values."""
    if type(a) is not type(b):
        return False
    if type(b) is dict:
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    if type(b) is list:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def shape(value, source, reason):
    """Check source primitive/container schema before indexing or physical arithmetic.

    None is allowed exactly where the source declares None; bool is never numeric.
    Values are checked separately by the independent semantic/source checks.
    """
    require(type(value) is type(source), reason)
    if type(source) is dict:
        require(value.keys() == source.keys(), reason)
        for k in source:
            shape(value[k], source[k], reason)
    elif type(source) is list:
        require(len(value) == len(source), reason)
        for a, b in zip(value, source):
            shape(a, b, reason)


def finite_json(value):
    """Semantic entry guard, deliberately before canonical serialization/digests."""
    require(type(value) in (dict, list, str, int, float, bool, type(None)), 'NON_JSON_PRIMITIVE')
    if type(value) is float:
        require(math.isfinite(value), 'NONFINITE_NUMERIC')
    elif type(value) is dict:
        require(all(type(k) is str for k in value), 'NON_JSON_KEY')
        for child in value.values():
            finite_json(child)
    elif type(value) is list:
        for child in value:
            finite_json(child)


def record_list(value, reason):
    require(type(value) is list and all(type(r) is dict for r in value), reason)


def positive_int(value, reason):
    require(type(value) is int and value > 0, reason)


def read(p):
    return json.loads((ROOT/p).read_text(encoding='utf8'))


def encode(v):
    return (json.dumps(v, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rows(t):
    return [dict(zip(t['columns'], r)) for r in t['rows']]


def source_context():
    for p, digest in FROZEN.items():
        require(sha((ROOT/p).read_bytes()) == digest, 'FROZEN_ARTIFACT_DRIFT:'+p)
    for p, digest in PINS.items():
        require(sha((ROOT/p).read_bytes()) == digest, 'PINNED_SOURCE_DRIFT')
    b, c, policy, gate = read(BASE), read(C08), read(ROUTE), read(GATE)
    pins = {**b['source_hashes'], **PINS}
    for row in c['source_fingerprints']:
        require(row['path'] not in pins or pins[row['path']] == row['sha256'], 'SOURCE_AUTHORITY_CONFLICT')
        pins[row['path']] = row['sha256']
    for p, digest in pins.items():
        require(sha((ROOT/p).read_bytes()) == digest, 'CANONICAL_SOURCE_DRIFT')
    layout = read(b['layout_ref']['path'])
    require(c['schema_version'] == '0.2.0' and c['layout_content_hash'] == layout['layout_content_hash'], 'C08_LAYOUT_AUTHORITY')
    require(policy['loads'] == c['loads'] and policy['loaded_arc_eligibility'] == c['per_cargo_arc_eligibility']
            and policy['ports'] == c['ports'] and policy['rating_design'] == c['rating_design'], 'ROUTE_C08_AUTHORITY')
    catalogue = read('docs/v3/contract-proposals/cargo-catalog-v3.json')['records']
    for a in b['inputs']['archetypes']:
        original = next(x for x in catalogue if x['archetype_id'] == a['archetype_id'])
        require(all(a[k] == original[k] for k in ['handling_unit','orientation','unit']), 'CATALOGUE_AUTHORITY')
    geometry = read('docs/adaptive-v3/evidence/M10.json')['actual_geometry']['dimensions_m']
    require(all(abs(a-z)<1e-5 for a,z in zip(geometry,[4.2,.52,.65])), 'M10_GEOMETRY_AUTHORITY')
    return dict(b=b,c=c,policy=policy,gate=gate,layout=layout['data'],pins=dict(sorted(pins.items())),catalogue=catalogue,
        profiles={p['worker_id']:p for p in read(b['profiles_ref']['path'])['profiles']},
        registry={p['actor_id']:p for p in read(b['registry_ref']['path'])['workers']})


def validate(d, evidence, ctx):
    finite_json(d)
    finite_json(evidence)
    require(type(d) is dict and type(evidence) is dict, 'DOCUMENT_PRIMITIVE')
    b,c,layout,policy = (ctx[k] for k in ['b','c','layout','policy'])
    require(set(d) == TOP, 'UNAUTHORIZED_FIELDS')
    require(all(type(d[k]) is type(v) and d[k] == v for k,v in SCOPE.items()), 'FABRICATED_SCOPE')
    require(d['actions'] == [] and d['completion_events'] == [], 'FABRICATED_EXECUTION')
    require(d['schema_id'] == 'qoima.long-freight-input.v3' and d['schema_version'] == '0.1.0'
            and d['task_id'] == 'W12.1' and d['scenario_id'] == 'v3:scenario:N3_LONG_FREIGHT:001', 'SCENARIO_IDENTITY')
    require(d['source_hashes'] == ctx['pins'], 'SOURCE_FINGERPRINT_MISMATCH')
    require(d['base_fixture_ref'] == dict(path=BASE,sha256=PINS[BASE]), 'BASE_SOURCE_MISMATCH')
    for key in ['clock','layout_ref','registry_ref','profiles_ref']:
        require(same(d[key], b[key]), 'SOURCE_REFERENCE_OVERRIDE')
    inp = d['inputs']
    require(type(inp) is dict and set(inp) == set(b['inputs']), 'INPUT_OVERRIDE')
    for key, reason in [('initial_stock','INITIAL_STOCK_CHANGED'),('workers','ORIGINAL_PEOPLE_CHANGED'),
                        ('vehicles','ORIGINAL_VEHICLES_CHANGED'),('ports','ORIGINAL_PORTS_CHANGED'),
                        ('archetypes','CARGO_CATALOGUE_CHANGED'),('skus','SKU_CATALOGUE_CHANGED')]:
        require(same(inp[key], b['inputs'][key]), reason)
    requests = inp['requests']
    record_list(requests, 'REQUEST_PRIMITIVE')
    require(same(requests[:16], b['inputs']['requests']), 'ORIGINAL_REQUEST_CHANGED')
    require(len(requests) == 20, 'REQUEST_COUNT')
    require(all(type(r.get(k)) is str for r in requests for k in ['request_id','handling_unit_id']), 'REQUEST_PRIMITIVE')
    require(len({r['request_id'] for r in requests}) == 20, 'DUPLICATE_REQUEST')
    require(len({r['handling_unit_id'] for r in requests}) == 20, 'DUPLICATE_HU')
    skus = {s['sku_id']:s for s in inp['skus']}
    archetypes = {s['archetype_id']:s for s in inp['archetypes']}
    request_source = next(r for r in b['inputs']['requests'] if r['direction']=='inbound' and r['archetype_id']=='LONG_BUNDLE')
    for r in requests[16:]:
        require(type(r.get('request_id')) is str and type(r.get('handling_unit_id')) is str, 'REQUEST_PRIMITIVE')
    for i,r in enumerate(requests[16:],1):
        require(set(r) == set(b['inputs']['requests'][0]), 'REQUEST_OVERRIDE')
        shape(r, request_source, 'REQUEST_PRIMITIVE')
        positive_int(r['quantity_handling_units'], 'REQUEST_NATIVE_QUANTITY')
        positive_int(r['quantity_units'], 'REQUEST_NATIVE_QUANTITY')
        require(r['request_id'] == f'v3:request:W12:external:{i:02}', 'EXTERNAL_REQUEST_ID')
        require(r['handling_unit_id'] == f'v3:HU:W12:external:{i:02}' and r['lot_id'] == f'v3:lot:W12:external:{i:02}', 'EXTERNAL_HU_LOT_ID')
        require(r['sku_id'] in skus and skus[r['sku_id']]['archetype_id'] == r['archetype_id'] == 'LONG_BUNDLE'
                and r['sku_id'] == 'DEMO_180', 'REQUEST_SOURCE_ID')
        require(r['quantity_handling_units'] == 1 and type(r['quantity_units']) is int
                and r['quantity_units'] == archetypes[r['archetype_id']]['handling_unit']['units_per_handling_unit'], 'REQUEST_NATIVE_QUANTITY')
        require(r['port_id'] == 'IN_W_BULK' and r['direction'] == 'inbound' and r['kind'] == 'receipt_request', 'REQUEST_PORT_DIRECTION')
        require(r['source_kind'] == 'visual_fixture' and r['engine_operation'] is False
                and r['included_in_initial_stock'] is False and r['initial_location_kind'] == 'upstream', 'EXTERNAL_STOCK_PROVENANCE')
        require(r['requested_at_s'] == i*180 and r['deadline_at_s'] == i*180+900, 'SYNTHETIC_RELEASE_DEADLINE')
    pre = d['preregistration']
    require(same(pre, dict(source_kind='synthetic_design',before_comparison=True,additional_receipts=4,archetype_id='LONG_BUNDLE',
        release_seconds=[180,360,540,720],deadline_offset_seconds=900,time_provenance='SYNTHETIC_W12_INPUT_CHOICE_NOT_C11',
        selection_basis='Four whole external LONG HUs chosen before any optimization or observed outcomes.')), 'FAKE_TIME_PROVENANCE')
    upstream = d['upstream_handling_units']
    record_list(upstream, 'HU_PRIMITIVE')
    require(all(type(h.get(k)) is str for h in upstream for k in ['handling_unit_id','lot_id']), 'HU_PRIMITIVE')
    require(len(upstream) == 12, 'UPSTREAM_COUNT')
    require(len({h['handling_unit_id'] for h in upstream}) == 12 and len({h['lot_id'] for h in upstream}) == 12, 'DUPLICATE_UPSTREAM_ID')
    inbound = [r for r in requests if r['direction']=='inbound']
    for i,(h,r) in enumerate(zip(upstream,inbound)):
        require(set(h) == HU_KEYS, 'HU_OVERRIDE')
        require(all(h[k] == r[k] for k in ['handling_unit_id','lot_id','request_id','sku_id','archetype_id']), 'HU_REQUEST_LINK')
        require(h['source_catalogue_id'] == r['sku_id'] and h['source_catalogue_pointer'] == skus[r['sku_id']]['cargo_template_pointer'], 'HU_CATALOGUE_LINK')
        a = archetypes[r['archetype_id']]
        positive_int(h['quantity_units'], 'HU_UNITS')
        require(h['quantity_units'] == r['quantity_units'] == a['handling_unit']['units_per_handling_unit'], 'HU_UNITS')
        require(same(h['gross_mass_kg'], a['handling_unit']['gross_mass_kg']), 'HU_MASS')
        require(same(h['dimensions_xyz_m'], a['handling_unit']['dimensions_xyz_m']), 'HU_DIMENSIONS')
        require(h['orientation_id'] in [o['orientation_id'] for o in a['orientation']['permitted_orientations']]
                and same(h['model_scale_factor'], 1), 'HU_ORIENTATION_SCALE')
        require(h['included_in_initial_stock'] is False and h['location_kind']=='upstream' and h['state']=='planned_input'
                and h['origin'] == ('original_W01_upstream' if i<8 else 'external_synthetic_supplier'), 'UPSTREAM_PROVENANCE')
    long_requests = [r for r in requests if r['archetype_id']=='LONG_BUNDLE']
    reqmap = {r['request_id']:r for r in long_requests}
    long_rows = d['long_requirements']
    record_list(long_rows, 'LONG_PRIMITIVE')
    require(all(type(x.get('request_id')) is str for x in long_rows), 'LONG_PRIMITIVE')
    require(len(long_rows) == 6 and len({x['request_id'] for x in long_rows}) == 6
            and {x['request_id'] for x in long_rows} == set(reqmap), 'LONG_REQUEST_COVERAGE')
    nodes = rows(layout['graphs']['vehicle']['nodes'])
    ni = {n['node_id']:i for i,n in enumerate(nodes)}
    arcs = {a['arc_id']:a for a in rows(layout['graphs']['vehicle']['arcs'])}
    slots = {s['slot_id']:s for s in rows(layout['storage']['slots'])}
    allowed = set(next(x for x in c['per_cargo_arc_eligibility'] if x['archetype_id']=='LONG_BUNDLE')['allowed_arc_ids'])
    load = next(x for x in c['loads'] if x['archetype_id']=='LONG_BUNDLE')
    stock = next(x for x in b['inputs']['initial_stock'] if x['archetype_id']=='LONG_BUNDLE')
    target_slot = stock['location']['slot_id']
    for x in long_rows:
        require(set(x) == LONG_KEYS, 'LONG_OVERRIDE')
        r = reqmap[x['request_id']]
        require(x['handling_unit_id']==r['handling_unit_id'] and x['lot_id']==r['lot_id'], 'LONG_HU_REQUEST_LINK')
        require(x['port_id']==r['port_id'], 'LONG_PORT_LINK')
        p = next((p for p in c['ports'] if p['port_id']==x['port_id']), None)
        require(p is not None and 'LONG_BUNDLE' in p['forklift_cargo_archetype_ids'], 'PORT_CARGO_FORBIDDEN')
        g = next((g for g in ctx['gate']['gates'] if g['gate_id']==x['gate_id']), None)
        require(g is not None and g['port_id']==p['port_id'], 'WRONG_GATE')
        require(same(x['gate_constraints'], g), 'GATE_GEOMETRY_OVERRIDE')
        require(x['gate_asset_id'] == ('large-gate' if r['direction']=='inbound' else 'large-gate-b2b'), 'GATE_ASSET_MISMATCH')
        actual = read('docs/adaptive-v3/evidence/P09.2.json')['variants'][x['gate_asset_id']]['actual_glb_verification']
        require(actual['actual_clear_width_m']==p['clear_width_m'] and actual['actual_clear_height_m']==p['clear_height_m'], 'GATE_MODEL_AUTHORITY')
        width = max(a['max'][0] for a in load['component_bounds_local_m'])-min(a['min'][0] for a in load['component_bounds_local_m'])+.5
        height = max(a['max'][1] for a in load['component_bounds_local_m'])+.25
        require(width<=p['clear_width_m'] and height<=p['clear_height_m']
                and abs(width-g['straight_clearance']['required_width_m'])<1e-9
                and abs(height-g['straight_clearance']['required_height_m'])<1e-9, 'GATE_CLEARANCE')
        require(x['mode']=='forklift' and x['handler']=='forklift' and x['handling_mode']=='forklift_with_compatible_load_support', 'FORBIDDEN_MODE_HANDLER')
        pair = next(v for v in policy['equipment_pairs'] if v['pair_id']==p['equipment_pair_ref'])
        require(x['equipment_pair_ref']==pair['pair_id'] and x['actor_id']==pair['actor_id'] and x['vehicle_id']==pair['vehicle_id'], 'FORBIDDEN_PAIR_VEHICLE')
        profile = ctx['profiles'][x['actor_id']]
        require('forklift' in profile['allowed_handlers'] and x['vehicle_id'] in profile['allowed_vehicle_ids']
                and ctx['registry'][x['actor_id']]['assigned_vehicle_id']==x['vehicle_id'], 'HANDLER_SOURCE_RESTRICTION')
        require(x['geometry_profile_id']==load['local_geometry_profile_id'], 'FORBIDDEN_LOADED_PROFILE')
        require(same(x['relative_load_yaw_deg'], 0) and same(x['cargo_axes_to_vehicle'], ctx['gate']['load_profile']['load_axes_to_vehicle']), 'FORBIDDEN_LOAD_REORIENTATION')
        require(x['attachment_id']==c['long_cradle_design']['attachment_id'] and same(x['attachment_mass_kg'], c['long_cradle_design']['mass_kg'])
                and same(x['support_design'], load['support_design']) and x['positive_lock_required'] is True
                and x['independent_restraint_required'] is True, 'MISSING_CRADLE_LOCK_RESTRAINT')
        rating = x['rating_requirements']
        shape(rating, c['rating_design'], 'RATING_PRIMITIVE')
        shape(x['loaded_profile'], load, 'LOADED_PROFILE_PRIMITIVE')
        lifted = x['loaded_profile']['total_lifted_mass_kg']
        arms = [x['loaded_profile']['load_centre_from_fork_heel_m'],x['loaded_profile']['extended_handling_rating_arm_from_fixed_Z04_m']]
        require(all(a>0 and lifted<=min(rating['nominal_capacity_kg'],rating['moment_budget_kg_m']/a) for a in arms)
                and lifted/2<=rating['maximum_single_fork_share_kg']
                and x['loaded_profile']['HU_gross_mass_kg']<=c['long_cradle_design']['declared_payload_limit_kg'], 'RATING_EXCEEDED')
        require(same(rating, c['rating_design']), 'RATING_OVERRIDE')
        require(same(x['loaded_profile'], load), 'LOADED_ENVELOPE_OVERRIDE')
        route = x['route']
        require(type(route) is dict and set(route)==ROUTE_KEYS, 'ROUTE_OVERRIDE')
        require(all(type(route[k]) is list and all(type(v) is str for v in route[k]) for k in ['node_ids','arc_ids','closed_arc_ids']), 'ROUTE_PRIMITIVE')
        require(route['endpoint_slot_source_id']==target_slot and not slots[target_slot]['retrieval_blocked']
                and 'LONG_BUNDLE' in slots[target_slot]['allowed_cargo_archetype_ids'], 'ROUTE_ENDPOINT_SOURCE')
        target = nodes[slots[target_slot]['vehicle_node_index']]['node_id']
        start,end = ('v3:service:'+r['port_id'],target) if r['direction']=='inbound' else (target,'v3:service:'+r['port_id'])
        require(route['from_node_id']==start and route['to_node_id']==end, 'ROUTE_ENDPOINT_MISMATCH')
        require(route['source_ref']==b['layout_ref']['path'] and route['policy_ref']==ROUTE and route['closed_arc_ids']==[], 'ROUTE_SOURCE_OVERRIDE')
        require(route['endpoint_kind']=='declared_geometry_query_only' and route['cost_evaluated'] is False
                and route['storage_assignment'] is False and route['operational_admission'] is False
                and x['operational_admission'] is False, 'FABRICATED_ROUTE_ADMISSION')
        require(len(route['arc_ids'])>0 and len(route['node_ids'])==len(route['arc_ids'])+1, 'EMPTY_OR_MALFORMED_PATH')
        require(all(n in ni for n in route['node_ids']), 'UNKNOWN_ROUTE_NODE')
        require(route['node_ids'][0]==start and route['node_ids'][-1]==end, 'PATH_ENDPOINT_MISMATCH')
        for i,aid in enumerate(route['arc_ids']):
            require(aid in arcs, 'UNKNOWN_ROUTE_ARC')
            a = arcs[aid]
            require(aid in allowed and a['cargo_transport_supported'] is not False and 'LONG_BUNDLE' in a['allowed_cargo_archetype_ids'], 'FORBIDDEN_LONG_ARC')
            require(pair['pair_id'] in a['equipment_pair_refs'] and load['main_geometry_profile_id'] in a['allowed_geometry_profile_ids'], 'ARC_PAIR_PROFILE')
            require((a['clear_width_m'] is None or a['clear_width_m']>=width) and a['clear_height_m']>=height, 'PATH_CLEARANCE')
            require(a['from_node_index']==ni[route['node_ids'][i]] and a['to_node_index']==ni[route['node_ids'][i+1]], 'PATH_DISCONTINUITY')
    require(d['inputs_sha256']==sha(encode(inp)), 'INPUT_DIGEST_MISMATCH')
    require(same(d['comparison_policy'], dict(same_materialized_file_required=True,variant_overrides_allowed=False,decision_state='not_evaluated',no_op_allowed=True)), 'VARIANT_OVERRIDE')
    require(d['required_before_execution']==PREREQS, 'MISSING_RUNTIME_GATE')
    ref = dict(path=FIXTURE,bytes=len(encode(d)),sha256=sha(encode(d)))
    require(same(evidence.get('input_ref'), ref) and same(evidence.get('paired_runs'), [dict(variant=v,input_ref=ref) for v in ['baseline','adaptive']]), 'PAIRED_INPUT_IDENTITY')
    require(evidence['source_hashes']==ctx['pins'], 'EVIDENCE_SOURCE_DRIFT')
    require(all(evidence.get(k)==SCOPE[k] and type(evidence.get(k)) is type(SCOPE[k]) for k in ['source_kind','engine_operation','actual_engine_run','execution_ready','operational_admission','status']), 'EVIDENCE_FABRICATED_SCOPE')
    def total(hus):
        return dict(HUs=len(hus),units=sum(h['quantity_units'] for h in hus),gross_mass_kg=str(sum((Decimal(str(h['gross_mass_kg'])) for h in hus),Decimal(0))))
    summary = dict(initial_stock=total(inp['initial_stock']),original_upstream=total(upstream[:8]),added_external=total(upstream[8:]),all_upstream=total(upstream),
        original_requests=16,added_requests=4,total_requests=20,workers=24,powered_vehicles=2,LONG_requests=6,LONG_loaded_profile='long_loaded',gate_ids=sorted({x['gate_id'] for x in long_rows}))
    require(same(evidence['summary'], summary), 'SUMMARY_CONSERVATION')
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check-only',action='store_true')
    args = p.parse_args()
    ctx = source_context()
    d,e = read(FIXTURE),read(EVIDENCE)
    require((ROOT/FIXTURE).read_bytes()==encode(d), 'NONCANONICAL_INPUT_BYTES')
    summary = validate(d,e,ctx)
    negatives = []
    def attack(name,path,value,reason,in_evidence=False,semantic_entry=False):
        mutated,ev = copy.deepcopy(d),copy.deepcopy(e)
        current = ev if in_evidence else mutated
        for part in path[:-1]:
            current = current[part]
        current[path[-1]] = value
        # Attackers can recompute every superficial digest; semantic checks still reject.
        if not semantic_entry:
            mutated['inputs_sha256']=sha(encode(mutated['inputs']))
        if not in_evidence and not semantic_entry:
            ref=dict(path=FIXTURE,bytes=len(encode(mutated)),sha256=sha(encode(mutated)))
            ev['input_ref']=ref
            ev['paired_runs']=[dict(variant=v,input_ref=copy.deepcopy(ref)) for v in ['baseline','adaptive']]
        fresh_ctx = source_context()
        try:
            validate(mutated,ev,fresh_ctx)
        except ValueError as exc:
            require(str(exc)==reason, 'NEGATIVE_WRONG_BRANCH:'+name+':'+str(exc))
        else:
            raise ValueError('NEGATIVE_ACCEPTED:'+name)
        negatives.append(dict(case=name,reason=reason,branch='.'.join(map(str,path)),rejected=True,
                              superficial_hashes_recomputed=not in_evidence and not semantic_entry,
                              stage='semantic_validate_entry_before_encoding' if semantic_entry else 'validate_after_superficial_rehash',
                              source_rechecked=True,cost_evaluated=False))
    tests = [
        ('unknown_request',['inputs','requests',16,'request_id'],'fake','EXTERNAL_REQUEST_ID'),
        ('duplicate_request',['inputs','requests',17,'request_id'],d['inputs']['requests'][16]['request_id'],'DUPLICATE_REQUEST'),
        ('duplicate_HU',['inputs','requests',17,'handling_unit_id'],d['inputs']['requests'][16]['handling_unit_id'],'DUPLICATE_HU'),
        ('unknown_HU',['inputs','requests',16,'handling_unit_id'],'fake','EXTERNAL_HU_LOT_ID'),
        ('unknown_lot',['inputs','requests',16,'lot_id'],'fake','EXTERNAL_HU_LOT_ID'),
        ('duplicate_upstream_lot',['upstream_handling_units',9,'lot_id'],d['upstream_handling_units'][8]['lot_id'],'DUPLICATE_UPSTREAM_ID'),
        ('mismatched_HU_link',['upstream_handling_units',8,'request_id'],'fake','HU_REQUEST_LINK'),
        ('unknown_SKU',['inputs','requests',16,'sku_id'],'fake','REQUEST_SOURCE_ID'),
        ('mismatched_source',['upstream_handling_units',8,'source_catalogue_id'],'DEMO_001','HU_CATALOGUE_LINK'),
        ('wrong_source_pointer',['upstream_handling_units',8,'source_catalogue_pointer'],'/records/0','HU_CATALOGUE_LINK'),
        ('partial_pick',['inputs','requests',16,'quantity_units'],4,'REQUEST_NATIVE_QUANTITY'),
        ('wrong_HU_units',['upstream_handling_units',8,'quantity_units'],23,'HU_UNITS'),
        ('wrong_HU_mass',['upstream_handling_units',8,'gross_mass_kg'],199,'HU_MASS'),
        ('shrunken_HU',['upstream_handling_units',8,'dimensions_xyz_m'],[.65,.52,4.2],'HU_DIMENSIONS'),
        ('forbidden_orientation',['upstream_handling_units',8,'orientation_id'],'rotated_90','HU_ORIENTATION_SCALE'),
        ('scaled_HU',['upstream_handling_units',8,'model_scale_factor'],.5,'HU_ORIENTATION_SCALE'),
        ('stock_grown',['inputs','initial_stock'],d['inputs']['initial_stock']+[d['inputs']['initial_stock'][0]],'INITIAL_STOCK_CHANGED'),
        ('stock_mass_changed',['inputs','initial_stock',0,'gross_mass_kg'],0,'INITIAL_STOCK_CHANGED'),
        ('original_upstream_changed',['inputs','requests',0,'lot_id'],'fake','ORIGINAL_REQUEST_CHANGED'),
        ('original_people_changed',['inputs','workers',0,'actor_id'],'FAKE','ORIGINAL_PEOPLE_CHANGED'),
        ('original_vehicle_changed',['inputs','vehicles',0,'vehicle_id'],'FL03','ORIGINAL_VEHICLES_CHANGED'),
        ('port_widened',['inputs','ports',0,'clear_width_m'],10,'ORIGINAL_PORTS_CHANGED'),
        ('fake_release',['inputs','requests',16,'requested_at_s'],0,'SYNTHETIC_RELEASE_DEADLINE'),
        ('fake_deadline',['inputs','requests',16,'deadline_at_s'],999,'SYNTHETIC_RELEASE_DEADLINE'),
        ('C11_time_inference',['preregistration','time_provenance'],'C11_MEASURED','FAKE_TIME_PROVENANCE'),
        ('external_in_initial_stock',['upstream_handling_units',8,'included_in_initial_stock'],True,'UPSTREAM_PROVENANCE'),
        ('wrong_port',['long_requirements',0,'port_id'],'IN_E_PARCEL','LONG_PORT_LINK'),
        ('narrow_wrong_gate',['long_requirements',0,'gate_id'],'v3:large-gate:IN_E_PARCEL','WRONG_GATE'),
        ('wrong_direction_gate',['long_requirements',0,'gate_id'],'v3:large-gate:OUT_E_B2B','WRONG_GATE'),
        ('gate_geometry_override',['long_requirements',0,'gate_constraints','clear_width_m'],4,'GATE_GEOMETRY_OVERRIDE'),
        ('wrong_gate_asset',['long_requirements',0,'gate_asset_id'],'large-gate-b2b','GATE_ASSET_MISMATCH'),
        ('manual_LONG',['long_requirements',0,'mode'],'manual_cart','FORBIDDEN_MODE_HANDLER'),
        ('wrong_handler',['long_requirements',0,'handler'],'manual','FORBIDDEN_MODE_HANDLER'),
        ('wrong_driver',['long_requirements',0,'actor_id'],'P01','FORBIDDEN_PAIR_VEHICLE'),
        ('wrong_vehicle',['long_requirements',0,'vehicle_id'],'FL02','FORBIDDEN_PAIR_VEHICLE'),
        ('wrong_pair',['long_requirements',0,'equipment_pair_ref'],'OUTBOUND_FORKLIFT_PAIR','FORBIDDEN_PAIR_VEHICLE'),
        ('bare_profile',['long_requirements',0,'geometry_profile_id'],'unloaded_bare','FORBIDDEN_LOADED_PROFILE'),
        ('rotate_load_to_fit',['long_requirements',0,'relative_load_yaw_deg'],90,'FORBIDDEN_LOAD_REORIENTATION'),
        ('missing_cradle',['long_requirements',0,'attachment_id'],None,'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('missing_lock',['long_requirements',0,'positive_lock_required'],False,'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('missing_restraint',['long_requirements',0,'independent_restraint_required'],False,'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('cradle_mass_dropped',['long_requirements',0,'attachment_mass_kg'],0,'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('overweight_rating',['long_requirements',0,'loaded_profile','total_lifted_mass_kg'],1001.0,'RATING_EXCEEDED'),
        ('lower_rating',['long_requirements',0,'rating_requirements','nominal_capacity_kg'],100,'RATING_EXCEEDED'),
        ('rating_override',['long_requirements',0,'rating_requirements','nominal_capacity_kg'],2000,'RATING_OVERRIDE'),
        ('loaded_envelope_shrunk',['long_requirements',0,'loaded_profile','handling_unit_dimensions_xyz_m'],[.65,.52,4.2],'LOADED_ENVELOPE_OVERRIDE'),
        ('unknown_slot_source',['long_requirements',0,'route','endpoint_slot_source_id'],'fake','ROUTE_ENDPOINT_SOURCE'),
        ('wrong_endpoint',['long_requirements',0,'route','from_node_id'],'v3:service:OUT_E_B2B','ROUTE_ENDPOINT_MISMATCH'),
        ('unknown_node',['long_requirements',0,'route','node_ids',1],'fake','UNKNOWN_ROUTE_NODE'),
        ('unknown_arc',['long_requirements',0,'route','arc_ids',0],'fake','UNKNOWN_ROUTE_ARC'),
        ('route_source_override',['long_requirements',0,'route','policy_ref'],'fake','ROUTE_SOURCE_OVERRIDE'),
        ('fake_cost',['long_requirements',0,'route','cost_evaluated'],True,'FABRICATED_ROUTE_ADMISSION'),
        ('fake_storage_assignment',['long_requirements',0,'route','storage_assignment'],True,'FABRICATED_ROUTE_ADMISSION'),
        ('stale_source',['source_hashes',C08],'0'*64,'SOURCE_FINGERPRINT_MISMATCH'),
        ('fabricated_engine',['actual_engine_run'],True,'FABRICATED_SCOPE'),
        ('fabricated_readiness',['execution_ready'],True,'FABRICATED_SCOPE'),
        ('fabricated_action',['actions'],[{'action':'move'}],'FABRICATED_EXECUTION'),
        ('fabricated_completion',['completion_events'],[{'done':True}],'FABRICATED_EXECUTION'),
        ('fabricated_metrics',['metrics'],{'throughput':1},'UNAUTHORIZED_FIELDS'),
        ('variant_override',['comparison_policy','variant_overrides_allowed'],True,'VARIANT_OVERRIDE'),
        ('nested_override',['long_requirements',0,'free_relocation'],True,'LONG_OVERRIDE'),
    ]
    # Independent host audit regressions: select real source rows, never builder output logic.
    stock_one = next(i for i,h in enumerate(d['inputs']['initial_stock']) if type(h['quantity_units']) is int and h['quantity_units']==1)
    stock_dim = next((i,j) for i,h in enumerate(d['inputs']['initial_stock']) for j,v in enumerate(h['dimensions_xyz_m']) if v==1)
    request_one = next(i for i,r in enumerate(d['inputs']['requests'][:16]) if r['quantity_units']==1)
    upstream_one = next(i for i,h in enumerate(d['upstream_handling_units']) if h['quantity_units']==1)
    upstream_dim = next((i,j) for i,h in enumerate(d['upstream_handling_units']) for j,v in enumerate(h['dimensions_xyz_m']) if v==1)
    strict_probes = [
        ('strict_probe_01_stock_bool_units',['inputs','initial_stock',stock_one,'quantity_units'],True,'INITIAL_STOCK_CHANGED'),
        ('strict_probe_02_stock_bool_dimension',['inputs','initial_stock',stock_dim[0],'dimensions_xyz_m',stock_dim[1]],True,'INITIAL_STOCK_CHANGED'),
        ('strict_probe_03_original_bool_HU_count',['inputs','requests',0,'quantity_handling_units'],True,'ORIGINAL_REQUEST_CHANGED'),
        ('strict_probe_04_original_float_units',['inputs','requests',request_one,'quantity_units'],1.0,'ORIGINAL_REQUEST_CHANGED'),
        ('strict_probe_05_upstream_bool_units',['upstream_handling_units',upstream_one,'quantity_units'],True,'HU_UNITS'),
        ('strict_probe_06_upstream_bool_dimension',['upstream_handling_units',upstream_dim[0],'dimensions_xyz_m',upstream_dim[1]],True,'HU_DIMENSIONS'),
        ('strict_probe_07_upstream_bool_scale',['upstream_handling_units',0,'model_scale_factor'],True,'HU_ORIENTATION_SCALE'),
        ('strict_probe_08_bool_yaw',['long_requirements',0,'relative_load_yaw_deg'],False,'FORBIDDEN_LOAD_REORIENTATION'),
    ]
    tests.extend(strict_probes)
    # Wrong primitive classes exercise source mirrors, new counts and physical profiles.
    primitive_fields = [
        ('stock_quantity',['inputs','initial_stock',stock_one,'quantity_units'],'INITIAL_STOCK_CHANGED'),
        ('original_HU_count',['inputs','requests',0,'quantity_handling_units'],'ORIGINAL_REQUEST_CHANGED'),
        ('external_units',['inputs','requests',16,'quantity_units'],'REQUEST_PRIMITIVE'),
        ('external_HU_count',['inputs','requests',16,'quantity_handling_units'],'REQUEST_PRIMITIVE'),
        ('upstream_units',['upstream_handling_units',0,'quantity_units'],'HU_UNITS'),
        ('upstream_dimension',['upstream_handling_units',0,'dimensions_xyz_m',0],'HU_DIMENSIONS'),
        ('upstream_mass',['upstream_handling_units',0,'gross_mass_kg'],'HU_MASS'),
        ('upstream_scale',['upstream_handling_units',0,'model_scale_factor'],'HU_ORIENTATION_SCALE'),
        ('yaw',['long_requirements',0,'relative_load_yaw_deg'],'FORBIDDEN_LOAD_REORIENTATION'),
        ('attachment_mass',['long_requirements',0,'attachment_mass_kg'],'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('gate_width',['long_requirements',0,'gate_constraints','clear_width_m'],'GATE_GEOMETRY_OVERRIDE'),
        ('gate_axis',['long_requirements',0,'gate_constraints','transit_heading_world',0],'GATE_GEOMETRY_OVERRIDE'),
        ('loaded_mass',['long_requirements',0,'loaded_profile','total_lifted_mass_kg'],'LOADED_PROFILE_PRIMITIVE'),
        ('loaded_dimension',['long_requirements',0,'loaded_profile','handling_unit_dimensions_xyz_m',0],'LOADED_PROFILE_PRIMITIVE'),
        ('loaded_scale',['long_requirements',0,'loaded_profile','scale_factor'],'LOADED_PROFILE_PRIMITIVE'),
        ('loaded_arm',['long_requirements',0,'loaded_profile','extended_handling_rating_arm_from_fixed_Z04_m'],'LOADED_PROFILE_PRIMITIVE'),
        ('rating_capacity',['long_requirements',0,'rating_requirements','nominal_capacity_kg'],'RATING_PRIMITIVE'),
    ]
    for name,path,reason in primitive_fields:
        for label,value in [('bool',True),('string','1'),('null',None),('list',[]),('dict',{})]:
            tests.append((name+'_'+label,path,value,reason))
    tests.extend([
        ('external_float_units',['inputs','requests',16,'quantity_units'],24.0,'REQUEST_PRIMITIVE'),
        ('external_float_count',['inputs','requests',16,'quantity_handling_units'],1.0,'REQUEST_PRIMITIVE'),
        ('external_zero_count',['inputs','requests',16,'quantity_handling_units'],0,'REQUEST_NATIVE_QUANTITY'),
        ('external_negative_units',['inputs','requests',16,'quantity_units'],-24,'REQUEST_NATIVE_QUANTITY'),
        ('upstream_float_units',['upstream_handling_units',upstream_one,'quantity_units'],1.0,'HU_UNITS'),
        ('upstream_zero_units',['upstream_handling_units',0,'quantity_units'],0,'HU_UNITS'),
        ('scale_float_substitution',['upstream_handling_units',0,'model_scale_factor'],1.0,'HU_ORIENTATION_SCALE'),
        ('yaw_float_substitution',['long_requirements',0,'relative_load_yaw_deg'],0.0,'FORBIDDEN_LOAD_REORIENTATION'),
        ('loaded_mass_int_substitution',['long_requirements',0,'loaded_profile','total_lifted_mass_kg'],240,'LOADED_PROFILE_PRIMITIVE'),
        ('rating_float_substitution',['long_requirements',0,'rating_requirements','nominal_capacity_kg'],1000.0,'RATING_PRIMITIVE'),
    ])
    policy_fields = [
        ('original_request_flag',['inputs','requests',0,'engine_operation'],0,'ORIGINAL_REQUEST_CHANGED'),
        ('stock_placement_flag',['inputs','initial_stock',0,'location','placement','operational_admission'],0,'INITIAL_STOCK_CHANGED'),
        ('port_policy_flag',['inputs','ports',0,'service_capacity','requires_shared_resources'],1,'ORIGINAL_PORTS_CHANGED'),
        ('external_request_flag',['inputs','requests',16,'included_in_initial_stock'],0,'REQUEST_PRIMITIVE'),
        ('upstream_flag',['upstream_handling_units',0,'included_in_initial_stock'],0,'UPSTREAM_PROVENANCE'),
        ('positive_lock_flag',['long_requirements',0,'positive_lock_required'],1,'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('restraint_flag',['long_requirements',0,'independent_restraint_required'],1,'MISSING_CRADLE_LOCK_RESTRAINT'),
        ('loaded_verified_flag',['long_requirements',0,'loaded_profile','component_containment_verified'],1,'LOADED_PROFILE_PRIMITIVE'),
        ('rating_certification_flag',['long_requirements',0,'rating_requirements','certification'],0,'RATING_PRIMITIVE'),
        ('rating_symmetry_flag',['long_requirements',0,'rating_requirements','restricted_to_symmetrical_centre_of_gravity'],1,'RATING_PRIMITIVE'),
        ('route_admission_flag',['long_requirements',0,'route','operational_admission'],0,'FABRICATED_ROUTE_ADMISSION'),
        ('long_admission_flag',['long_requirements',0,'operational_admission'],0,'FABRICATED_ROUTE_ADMISSION'),
        ('comparison_flag',['comparison_policy','no_op_allowed'],1,'VARIANT_OVERRIDE'),
        ('preregistration_flag',['preregistration','before_comparison'],1,'FAKE_TIME_PROVENANCE'),
        ('scope_flag',['execution_ready'],0,'FABRICATED_SCOPE'),
    ]
    tests.extend(policy_fields)
    tests.extend([
        ('inputs_wrong_container',['inputs'],[],'INPUT_OVERRIDE'),
        ('requests_wrong_container',['inputs','requests'],{},'REQUEST_PRIMITIVE'),
        ('request_wrong_record',['inputs','requests',16],None,'REQUEST_PRIMITIVE'),
        ('upstream_wrong_container',['upstream_handling_units'],{},'HU_PRIMITIVE'),
        ('upstream_wrong_record',['upstream_handling_units',0],None,'HU_PRIMITIVE'),
        ('long_wrong_container',['long_requirements'],{},'LONG_PRIMITIVE'),
        ('long_wrong_record',['long_requirements',0],None,'LONG_PRIMITIVE'),
        ('route_wrong_container',['long_requirements',0,'route'],[],'ROUTE_OVERRIDE'),
        ('route_nodes_wrong_container',['long_requirements',0,'route','node_ids'],'fake','ROUTE_PRIMITIVE'),
        ('gate_wrong_container',['long_requirements',0,'gate_constraints'],[],'GATE_GEOMETRY_OVERRIDE'),
        ('rating_wrong_container',['long_requirements',0,'rating_requirements'],[],'RATING_PRIMITIVE'),
        ('loaded_wrong_container',['long_requirements',0,'loaded_profile'],[],'LOADED_PROFILE_PRIMITIVE'),
        ('source_optional_null_changed',['inputs','workers',0,'assigned_vehicle_id'],False,'ORIGINAL_PEOPLE_CHANGED'),
        ('source_catalogue_bool_quantity',['inputs','archetypes',0,'handling_unit','units_per_handling_unit'],True,'CARGO_CATALOGUE_CHANGED'),
    ])
    for t in tests:
        attack(*t)
    # JSON cannot encode these with allow_nan=False. Call validate itself first:
    # a serializer exception cannot satisfy the exact semantic reason assertion.
    nonfinite_fields = [
        ['inputs','initial_stock',0,'dimensions_xyz_m',0],
        ['inputs','initial_stock',0,'gross_mass_kg'],
        ['inputs','requests',0,'quantity_units'],
        ['upstream_handling_units',0,'quantity_units'],
        ['upstream_handling_units',0,'dimensions_xyz_m',0],
        ['upstream_handling_units',0,'gross_mass_kg'],
        ['upstream_handling_units',0,'model_scale_factor'],
        ['long_requirements',0,'relative_load_yaw_deg'],
        ['long_requirements',0,'attachment_mass_kg'],
        ['long_requirements',0,'gate_constraints','clear_width_m'],
        ['long_requirements',0,'loaded_profile','total_lifted_mass_kg'],
        ['long_requirements',0,'loaded_profile','handling_unit_dimensions_xyz_m',0],
        ['long_requirements',0,'loaded_profile','extended_handling_rating_arm_from_fixed_Z04_m'],
        ['long_requirements',0,'rating_requirements','nominal_capacity_kg'],
    ]
    for index,path in enumerate(nonfinite_fields,1):
        for label,value in [('nan',float('nan')),('positive_inf',float('inf')),('negative_inf',float('-inf'))]:
            attack(f'nonfinite_{index:02}_{label}',path,value,'NONFINITE_NUMERIC',semantic_entry=True)
    arcs = rows(ctx['layout']['graphs']['vehicle']['arcs'])
    permitted = set(next(x for x in ctx['c']['per_cargo_arc_eligibility'] if x['archetype_id']=='LONG_BUNDLE')['allowed_arc_ids'])
    narrow = next(a for a in arcs if a['clear_width_m'] is not None and a['clear_width_m']<4.7 and a['arc_id'] not in permitted)
    attack('actual_narrow_arc',['long_requirements',0,'route','arc_ids',0],narrow['arc_id'],'FORBIDDEN_LONG_ARC')
    bare = next(a for a in arcs if a['arc_id'] not in permitted and a['cargo_transport_supported'] is False)
    attack('actual_bare_only_arc',['long_requirements',0,'route','arc_ids',0],bare['arc_id'],'FORBIDDEN_LONG_ARC')
    chain = d['long_requirements'][0]['route']['arc_ids']
    attack('discontinuous_allowed_path',['long_requirements',0,'route','arc_ids',0],chain[-1],'PATH_DISCONTINUITY')
    for key,value in [('path','fake.json'),('bytes',0),('sha256','0'*64)]:
        attack('variant_'+key,['paired_runs',1,'input_ref',key],value,'PAIRED_INPUT_IDENTITY',True)
    attack('evidence_engine',['actual_engine_run'],True,'EVIDENCE_FABRICATED_SCOPE',True)
    positive = [dict(case='canonical_source_authority',source_files=len(ctx['pins'])),
                dict(case='original_population_and_external_conservation',summary=summary),
                dict(case='same_full_input_bytes',input_ref=e['input_ref'])]
    for x in d['long_requirements']:
        positive.append(dict(case='source_eligible_LONG_chain',request_id=x['request_id'],gate_id=x['gate_id'],
            profile=x['geometry_profile_id'],pair=x['equipment_pair_ref'],arc_count=len(x['route']['arc_ids']),
            node_count=len(x['route']['node_ids']),from_node=x['route']['from_node_id'],to_node=x['route']['to_node_id']))
    # Reordering declarations does not change their semantics; proves acceptance is not one giant fixture equality.
    reordered = copy.deepcopy(d)
    reordered['long_requirements'].reverse()
    ev = copy.deepcopy(e)
    ref=dict(path=FIXTURE,bytes=len(encode(reordered)),sha256=sha(encode(reordered)))
    ev['input_ref']=ref
    ev['paired_runs']=[dict(variant=v,input_ref=copy.deepcopy(ref)) for v in ['baseline','adaptive']]
    validate(reordered,ev,source_context())
    positive.append(dict(case='independent_declaration_order_semantically_valid',in_memory_only=True))
    report = dict(task_id='W12.1',status=SCOPE['status'],source_kind='visual_fixture',engine_operation=False,
        actual_engine_run=False,execution_ready=False,operational_admission=False,input_integrity_verified=True,
        input_ref=e['input_ref'],source_hashes=ctx['pins'],positive_count=len(positive),negative_count=len(negatives),
        positives=positive,negatives=negatives,all_expected_reasons_exact=True,all_rejections_before_cost=True,
        superficial_hash_attack_policy='Input digest and both full-file refs recomputed for every JSON-representable fixture mutation; nonfinite cases call validate entry before encoding.',
        strict_host_probe_count=len(strict_probes),strict_host_probes_all_rejected=True,
        nonfinite_semantic_entry_count=3*len(nonfinite_fields),
        verifier_ref=dict(path=Path(__file__).relative_to(ROOT).as_posix(),bytes=Path(__file__).stat().st_size,sha256=sha(Path(__file__).read_bytes())),
        frozen_artifacts={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=digest) for p,digest in FROZEN.items()},
        graph_discovery='No graph-specific tools exposed; scoped source fallback only, no reindex or memory mutation.',
        summary=summary,limits='Source eligibility only; no native motion, structural certification, physical slot admission, completed operation, runtime or performance proof. W12 root acceptance open.')
    source_context()  # Detect concurrent source drift before publishing checker evidence.
    raw=encode(report)
    if args.check_only:
        require((ROOT/REPORT).read_bytes()==raw, 'STALE_CHECK_REPORT')
    else:
        (ROOT/REPORT).write_bytes(raw)
    print(json.dumps(dict(input_integrity_verified=True,execution_ready=False,positive_count=len(positive),
        negative_count=len(negatives),check_only=args.check_only,report_sha256=sha(raw))))


if __name__ == '__main__':
    main()
