"""Deterministic W12.1 frozen inputs. No scheduling, execution or optimization."""
import argparse
import copy
import hashlib
import json
from collections import deque
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
C08 = 'docs/v3/contract-proposals/vehicle-handling-v3.json'
ROUTE = 'frontend/public/data/v3/route-policy-v3.json'
GATE = 'docs/v3/contract-proposals/large-gate-v3.json'
FIXTURE = 'docs/adaptive-v3/fixtures/scenarios/W12-long-freight-input-v3.json'
SPEC = 'docs/adaptive-v3/specs/W12.1.md'
EVIDENCE = 'docs/adaptive-v3/evidence/W12.1.json'
PINS = {
    BASE: '52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91',
    C08: '22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4',
    ROUTE: '24ad87f197d14b1c681814b43b2c8841ca145c6b92515af744f3cb4473d35337',
    'docs/adaptive-v3/evidence/M10.json': 'bbc6b7797815f9b3c959bc7c9195db9303fa9e250f4ee1bf6059c5ddd069756b',
    'docs/adaptive-v3/evidence/P09.2.json': '79d8e3d9ee09c27864e762e27fe7f18045ea819a58c6922a87deb4986f595437',
}


def read(p):
    return json.loads((ROOT / p).read_text(encoding='utf8'))


def encoded(v):
    return (json.dumps(v, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf8')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def table(t):
    return [dict(zip(t['columns'], r)) for r in t['rows']]


def documents():
    b, c, policy, gate = read(BASE), read(C08), read(ROUTE), read(GATE)
    pins = {**b['source_hashes'], **PINS}
    for row in c['source_fingerprints']:
        assert row['path'] not in pins or pins[row['path']] == row['sha256']
        pins[row['path']] = row['sha256']
    for p, digest in pins.items():
        assert sha((ROOT / p).read_bytes()) == digest, 'Authoritative source drift: ' + p
    pins = dict(sorted(pins.items()))
    layout = read(b['layout_ref']['path'])['data']
    nodes = table(layout['graphs']['vehicle']['nodes'])
    arcs = table(layout['graphs']['vehicle']['arcs'])
    slots = {s['slot_id']: s for s in table(layout['storage']['slots'])}
    allowed = set(next(x for x in c['per_cargo_arc_eligibility'] if x['archetype_id'] == 'LONG_BUNDLE')['allowed_arc_ids'])
    stock = next(h for h in b['inputs']['initial_stock'] if h['archetype_id'] == 'LONG_BUNDLE')
    slot = slots[stock['location']['slot_id']]
    target = slot['vehicle_node_index']
    index = {n['node_id']: i for i, n in enumerate(nodes)}
    load = next(x for x in c['loads'] if x['archetype_id'] == 'LONG_BUNDLE')
    inputs = copy.deepcopy(b['inputs'])
    source = next(r for r in inputs['requests'] if r['direction'] == 'inbound' and r['archetype_id'] == 'LONG_BUNDLE')
    extras = []
    for i in range(1, 5):
        r = copy.deepcopy(source)
        r.update(request_id=f'v3:request:W12:external:{i:02}', handling_unit_id=f'v3:HU:W12:external:{i:02}',
                 lot_id=f'v3:lot:W12:external:{i:02}', requested_at_s=180*i, deadline_at_s=180*i+900)
        inputs['requests'].append(r)
        extras.append(r)
    # Original array order is retained; synthetic requests are appended explicitly.
    archetypes = {a['archetype_id']: a for a in inputs['archetypes']}
    skus = {s['sku_id']: s for s in inputs['skus']}
    upstream = []
    for r in inputs['requests']:
        if r['direction'] != 'inbound':
            continue
        a = archetypes[r['archetype_id']]['handling_unit']
        upstream.append(dict(handling_unit_id=r['handling_unit_id'], lot_id=r['lot_id'], request_id=r['request_id'],
            sku_id=r['sku_id'], archetype_id=r['archetype_id'], source_catalogue_id=r['sku_id'],
            source_catalogue_pointer=skus[r['sku_id']]['cargo_template_pointer'], quantity_units=r['quantity_units'],
            dimensions_xyz_m=a['dimensions_xyz_m'], gross_mass_kg=a['gross_mass_kg'], orientation_id='upright_xyz',
            model_scale_factor=1, origin='external_synthetic_supplier' if r in extras else 'original_W01_upstream',
            included_in_initial_stock=False, location_kind='upstream', state='planned_input'))
    requirements = []
    for r in inputs['requests']:
        if r['archetype_id'] != 'LONG_BUNDLE':
            continue
        p = next(p for p in c['ports'] if p['port_id'] == r['port_id'])
        pair = next(p2 for p2 in policy['equipment_pairs'] if p2['pair_id'] == p['equipment_pair_ref'])
        service = index['v3:service:' + r['port_id']]
        start, end = (service, target) if r['direction'] == 'inbound' else (target, service)
        adjacency = {}
        for a in sorted(arcs, key=lambda x: x['arc_id']):
            if a['arc_id'] in allowed and pair['pair_id'] in a['equipment_pair_refs'] and a['cargo_transport_supported'] is not False:
                adjacency.setdefault(a['from_node_index'], []).append(a)
        parents, pending = {start: None}, deque([start])
        while pending and end not in parents:
            for a in adjacency.get(pending.popleft(), []):
                if a['to_node_index'] not in parents:
                    parents[a['to_node_index']] = a
                    pending.append(a['to_node_index'])
        assert end in parents, 'No canonical LONG path'
        chain, node_chain, current = [], [end], end
        while current != start:
            a = parents[current]
            chain.append(a['arc_id'])
            current = a['from_node_index']
            node_chain.append(current)
        g = next(g for g in gate['gates'] if g['port_id'] == r['port_id'])
        requirements.append(dict(request_id=r['request_id'], handling_unit_id=r['handling_unit_id'], lot_id=r['lot_id'],
            port_id=r['port_id'], gate_id=g['gate_id'], gate_constraints=copy.deepcopy(g),
            gate_asset_id='large-gate' if r['direction'] == 'inbound' else 'large-gate-b2b',
            mode='forklift', actor_id=pair['actor_id'], vehicle_id=pair['vehicle_id'], equipment_pair_ref=pair['pair_id'],
            handler='forklift', handling_mode='forklift_with_compatible_load_support',
            geometry_profile_id=load['local_geometry_profile_id'], loaded_profile=copy.deepcopy(load),
            attachment_id=c['long_cradle_design']['attachment_id'], attachment_mass_kg=c['long_cradle_design']['mass_kg'],
            support_design=load['support_design'], positive_lock_required=True, independent_restraint_required=True,
            rating_requirements=copy.deepcopy(c['rating_design']), relative_load_yaw_deg=0,
            cargo_axes_to_vehicle=copy.deepcopy(gate['load_profile']['load_axes_to_vehicle']),
            route=dict(from_node_id=nodes[start]['node_id'], to_node_id=nodes[end]['node_id'],
                node_ids=[nodes[n]['node_id'] for n in reversed(node_chain)], arc_ids=list(reversed(chain)),
                endpoint_slot_source_id=stock['location']['slot_id'], endpoint_kind='declared_geometry_query_only',
                source_ref=b['layout_ref']['path'], policy_ref=ROUTE, closed_arc_ids=[],
                cost_evaluated=False, storage_assignment=False, operational_admission=False), operational_admission=False))
    d = dict(schema_id='qoima.long-freight-input.v3', schema_version='0.1.0', task_id='W12.1',
        scenario_id='v3:scenario:N3_LONG_FREIGHT:001', status='input_only_candidate_pending_root_review',
        source_kind='visual_fixture', engine_operation=False, actual_engine_run=False, operational_admission=False,
        execution_ready=False, execution_state='not_scheduled', metrics_scope='none', actions=[], completion_events=[],
        base_fixture_ref=dict(path=BASE, sha256=PINS[BASE]), source_hashes=pins,
        clock=copy.deepcopy(b['clock']), layout_ref=copy.deepcopy(b['layout_ref']), registry_ref=copy.deepcopy(b['registry_ref']),
        profiles_ref=copy.deepcopy(b['profiles_ref']), inputs=inputs, upstream_handling_units=upstream, long_requirements=requirements,
        preregistration=dict(source_kind='synthetic_design', before_comparison=True, additional_receipts=4,
            archetype_id='LONG_BUNDLE', release_seconds=[180,360,540,720], deadline_offset_seconds=900,
            time_provenance='SYNTHETIC_W12_INPUT_CHOICE_NOT_C11',
            selection_basis='Four whole external LONG HUs chosen before any optimization or observed outcomes.'),
        comparison_policy=dict(same_materialized_file_required=True, variant_overrides_allowed=False,
            decision_state='not_evaluated', no_op_allowed=True),
        required_before_execution=['W12_root_loaded_contact_lock_clearance_and_gate_crossing',
            'W05_actions_clock_exclusive_resources_finite_staging', 'admitted_baseline_and_candidate_storage_and_priced_relocations',
            'explicit_runtime_registration_and_root_review', 'supported_engine_adapter_for_actual_engine_runs'])
    d['inputs_sha256'] = sha(encoded(inputs))
    raw = encoded(d)
    ref = dict(path=FIXTURE, bytes=len(raw), sha256=sha(raw))
    def total(rows):
        return dict(HUs=len(rows), units=sum(x['quantity_units'] for x in rows),
                    gross_mass_kg=str(sum((Decimal(str(x['gross_mass_kg'])) for x in rows), Decimal(0))))
    evidence = dict(task_id='W12.1', status=d['status'], source_kind='visual_fixture', engine_operation=False,
        actual_engine_run=False, execution_ready=False, operational_admission=False, input_ref=ref,
        paired_runs=[dict(variant=v, input_ref=copy.deepcopy(ref)) for v in ['baseline','adaptive']],
        source_hashes=pins, summary=dict(initial_stock=total(inputs['initial_stock']),
            original_upstream=total(upstream[:8]), added_external=total(upstream[8:]), all_upstream=total(upstream),
            original_requests=16, added_requests=4, total_requests=20, workers=24, powered_vehicles=2,
            LONG_requests=6, LONG_loaded_profile='long_loaded', gate_ids=sorted({x['gate_id'] for x in requirements})),
        graph_discovery='No graph MCP access exposed; exact scoped source fallback, no reindex or memory refresh.',
        scope='Source eligibility and frozen input identity only; actual loaded movement/contact/clearance and W12 root runtime gates remain open.')
    spec = '''# W12.1 — frozen LONG FREIGHT / LARGE GATE inputs

Status: input_only_candidate_pending_root_review. source_kind=visual_fixture.
engine_operation, actual_engine_run, operational_admission and execution_ready are false.
Execution is not_scheduled; actions and completion_events are empty. Parent W12 remains open.

W01 accepted fixture, C08 v0.2, L12 compact layout, original cargo/SKU/port/resource
catalogues, W03.1 route policy and M10/P09.2 evidence are fingerprinted. No graph MCP
access was exposed: exact source fallback included build_route_policy.py,
warehouseRouting.ts and check-warehouse-routing-v3.mjs. No graph update occurred.
W02 does not automatically admit this new scenario; runtime registration remains required.

Preregistered SYNTHETIC choice, before comparison: four external LONG_BUNDLE whole-HU
receipt requests at 180/360/540/720 seconds, deadline release+900 seconds, IN_W_BULK,
DEMO_180 source catalogue. These times are input assumptions, not C11 proxy conversions,
arrival/completion predictions or measured capacity. Distinct W12 HU/lot/request IDs
and full native quantities/dimensions/masses/provenance are materialized.

Original 530 HUs / 200 SKUs / 12256 units / 9403.85 kg, 24 people, two powered vehicles,
all six port definitions, original eight upstream and sixteen request rows remain intact.
Original upstream: 8 HUs / 107 units / 1784.29 kg. Added: 4 HUs / 96 units / 800 kg.
All upstream: 12 HUs / 203 units / 2584.29 kg, excluded from initial inventory until
admitted execution. Total requests 20. No partial pick is reinterpreted as a whole HU.

Six LONG declarations cover original inbound/outbound and four external receipts.
Native HU 4.20 x .52 x .65 m, 24 units, 200 kg, upright_xyz, scale1. Cargo X stays
across vehicle X with relative yaw0; whole-vehicle heading along a curve does not
rotate cargo relative to forks. Original C08 loaded components, travel bottom .80 m,
top1.32 m, vehicle height2.10 m and long_loaded profile are retained. Positive-locked
v3:attachment:long-cradle:01 weighs40 kg separately: lifted total240 kg. Two retained
pins and independent bundle restraint are declared requirements. Cradle payload600 kg;
fork rating min(1000,800/arm), extended arm1 m, capacity800 kg and500 kg per fork.
These are synthetic design constraints, not structural or OEM certification.

Actual source gates v3:large-gate:IN_W_BULK (7 x 4.5 m, large-gate asset) and
v3:large-gate:OUT_E_B2B (6 x 4.5 m, large-gate-b2b asset) require straight aligned
crossing, 4.70 x 2.35 m padded clearance, source approach and transverse axes.
F01/FL01 inbound and F02/FL02 outbound retain their original pairs and profiles.

Every LONG declaration contains explicit original graph node/arc sequences. The
canonical vehicle node for original LONG_W:002:L1:B1 is the frozen geometric query
endpoint; this is not an allocation of that occupied slot to external inventory.
Inbound begins at its actual service node; outbound ends there. Each directed arc
must be C08 LONG-allowed and pair-allowed; no straight-line fallback, bare-only edge,
narrow-route substitution or in-place cargo rotation. The independent verifier reopens
the original indexed graph, checks continuity, endpoint source, profile, pair, cargo
and clearance relationships before any cost; no cost is computed. Service-node route
eligibility does not prove boundary crossing or actual swept mesh clearance.

Evidence binds baseline/adaptive to the exact same fully materialized file path,
whole-file byte length and SHA256. No per-variant overrides/resampling/staff/arrivals,
jobs/queues/results/metrics/free relocations exist. Input integrity does not assert
baseline/candidate physical slot admission. Root must prove actual contact/locks,
loaded motion, full gate crossing and stopped reach sweeps, exclusive original
resources, finite staging/upstream holds, supported actions/clock and priced relocations.

Run existing .venv/Scripts/python.exe -X utf8 -B on build_long_freight_scenario.py,
then verify_long_freight_scenario.py, then both with --check-only. Builder writes only
fixture/spec/evidence; verifier writes only W12.1-checks.json. Check mode compares
bytes without writes. Verifier imports no builder; mutations stay in memory and
recompute superficial input/file hashes to exercise independent semantic branches.
UTF8/LF/sorted JSON; no timestamps or recursive self-hashes; no task PASS manufactured.
'''
    return {FIXTURE:raw, SPEC:spec.encode('utf8'), EVIDENCE:encoded(evidence)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    outputs = documents()
    assert outputs == documents(), 'Non-deterministic production'
    for path, raw in outputs.items():
        target = ROOT / path
        if args.check_only:
            assert target.read_bytes() == raw, 'Stale output: ' + path
        else:
            target.write_bytes(raw)
    print(json.dumps(dict(input_integrity_candidate=True, execution_ready=False, check_only=args.check_only,
        files={p:dict(bytes=len(b),sha256=sha(b)) for p,b in outputs.items()})))


if __name__ == '__main__':
    main()
