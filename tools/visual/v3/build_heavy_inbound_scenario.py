"""Preregister W11.1 input bytes only; no workflow execution or optimization."""
import argparse
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
BASE_SHA = '52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91'
C08 = 'docs/v3/contract-proposals/vehicle-handling-v3.json'
C07 = 'docs/v3/contract-proposals/cargo-mass-cases-v3.json'
POLICY = 'docs/v3/contract-proposals/port-resource-policy-v3.json'
FIXTURE = 'docs/adaptive-v3/fixtures/scenarios/W11-heavy-inbound-input-v3.json'
SPEC = 'docs/adaptive-v3/specs/W11.1.md'
EVIDENCE = 'docs/adaptive-v3/evidence/W11.1.json'
PINS = {BASE: BASE_SHA, C08: '22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4',
        C07: '3d4e15a4941f4692d14238f4891a1ca24bdd46858e327d4e1e0682fb2b4e25ce'}


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')


def sources():
    base = read(BASE)
    pins = {**base['source_hashes'], **PINS}
    for row in read(C08)['source_fingerprints'] + read(C07)['source_fingerprints']:
        if row['path'] in pins:
            assert pins[row['path']] == row['sha256'], 'Conflicting source authorities'
        pins[row['path']] = row['sha256']
    for path, expected in pins.items():
        assert sha((ROOT / path).read_bytes()) == expected, 'Stale authoritative source: ' + path
    return base, dict(sorted(pins.items()))


def materialize(request, catalog, skus, external):
    a = catalog[request['archetype_id']]
    return dict(handling_unit_id=request['handling_unit_id'], lot_id=request['lot_id'],
        request_id=request['request_id'], sku_id=request['sku_id'], archetype_id=request['archetype_id'],
        source_catalogue_id=request['sku_id'], source_catalogue_pointer=skus[request['sku_id']]['cargo_template_pointer'],
        quantity_units=request['quantity_units'], dimensions_xyz_m=copy.deepcopy(a['handling_unit']['dimensions_xyz_m']),
        gross_mass_kg=a['handling_unit']['gross_mass_kg'], orientation_id='upright_xyz', model_scale_factor=1,
        origin='external_synthetic_supplier' if external else 'original_W01_upstream',
        location_kind='upstream', state='planned_input', included_in_initial_stock=False)


def documents():
    base, fingerprints = sources()
    catalog = {a['archetype_id']: a for a in base['inputs']['archetypes']}
    skus = {s['sku_id']: s for s in base['inputs']['skus']}
    inputs = copy.deepcopy(base['inputs'])
    original = [r for r in inputs['requests'] if r['direction'] == 'inbound']
    originals = [materialize(r, catalog, skus, False) for r in original]
    added = []
    # Frozen design choice, independent of placement or optimization outcomes.
    for i in range(12):
        archetype = ['PALLET_LOAD', 'IBC', 'HEAVY_BOX'][i % 3]
        source = next(r for r in original if r['archetype_id'] == archetype)
        r = copy.deepcopy(source)
        r.update(request_id=f'v3:request:W11:external:{i+1:02}',
            handling_unit_id=f'v3:HU:W11:external:{i+1:02}', lot_id=f'v3:lot:W11:external:{i+1:02}',
            port_id='IN_W_BULK', requested_at_s=90 + 60*i, deadline_at_s=690 + 60*i)
        inputs['requests'].append(r)
        added.append(materialize(r, catalog, skus, True))
    inputs['requests'].sort(key=lambda r: (r['requested_at_s'], r['request_id']))
    c08 = read(C08)
    loads = {r['archetype_id']: r for r in c08['loads']}
    ports = {r['port_id']: r for r in inputs['ports']}
    handling = []
    for r in inputs['requests']:
        requirement = next(x for x in ports[r['port_id']]['resource_requirements'] if r['archetype_id'] in x['cargo_archetype_ids'])
        load = loads.get(r['archetype_id'])
        handling.append(dict(request_id=r['request_id'], handling_mode=requirement['handling_mode'],
            equipment_pair_ref=requirement['forklift_pair_ref'],
            geometry_profile_id=load['local_geometry_profile_id'] if load else None,
            attachment_id=c08['long_cradle_design']['attachment_id'] if r['archetype_id'] == 'LONG_BUNDLE' else None,
            rating_source=C08 if load else None, operational_admission=False))
    d = dict(schema_id='qoima.heavy-inbound-input.v3', schema_version='0.1.0', task_id='W11.1',
        scenario_id='v3:scenario:N2_HEAVY_INBOUND:001', source_kind='visual_fixture',
        engine_operation=False, actual_engine_run=False, execution_ready=False, operational_admission=False,
        actual_v3_run_supported=False, visual_complete=False, backend_integration_complete=False,
        execution_state='not_scheduled', metrics_scope='none', status='input_only_candidate_pending_root_review',
        base_fixture_ref=dict(path=BASE, sha256=BASE_SHA), source_hashes=fingerprints,
        clock=copy.deepcopy(base['clock']), layout_ref=copy.deepcopy(base['layout_ref']),
        registry_ref=copy.deepcopy(base['registry_ref']), profiles_ref=copy.deepcopy(base['profiles_ref']),
        inputs=inputs, original_upstream=originals, external_receipts=added, handling_requirements=handling,
        preregistration=dict(synthetic_design_assumption=True, added_HUs=12,
            repeating_archetypes=['PALLET_LOAD','IBC','HEAVY_BOX'], port_id='IN_W_BULK',
            first_release_s=90, interval_s=60, last_release_s=750, deadline_offset_s=600,
            release_rate=dict(numerator_HUs=1, denominator_seconds=60, scope='added_release_schedule_only'),
            selection_basis='Mixed pallet, sealed IBC and heavy box; fixed before comparisons; no optimization result used.'),
        comparison_policy=dict(kind='slotting_only', same_concrete_input_required=True,
            allowed_output_differences=['admitted_HU_slot_placement','explicit_relocation_sequence_and_cost'],
            decision_state='not_evaluated', no_op_allowed=True, force_improvement=False),
        required_before_execution=['W05_unified_actions_and_clock','W11_loaded_physical_and_route_admission',
            'finite_staging_and_exclusive_original_resources','priced_relocations_and_admissible_baseline_candidate',
            'root_scene_replay_and_comparison_review','supported_backend_adapter_for_actual_engine_runs'],
        actions=[], completion_events=[])
    d['inputs_sha256'] = sha(encode(inputs))
    data = encode(d)
    ref = dict(path=FIXTURE, sha256=sha(data), bytes=len(data))
    def total(rows):
        return dict(HUs=len(rows), units=sum(x['quantity_units'] for x in rows),
            gross_mass_kg=str(sum((Decimal(str(x['gross_mass_kg'])) for x in rows), Decimal(0))))
    summary = dict(initial_stock=total(inputs['initial_stock']), original_upstream=total(originals),
        added_external=total(added), all_upstream=total(originals+added), original_requests=16,
        added_requests=12, total_requests=28, outbound_existing_requests=8, workers=24, powered_vehicles=2)
    evidence = dict(task_id='W11.1', status='input_only_candidate_pending_root_review',
        source_kind='visual_fixture', engine_operation=False, actual_engine_run=False, execution_ready=False,
        input_ref=ref, paired_runs=[dict(variant=v, input_ref=copy.deepcopy(ref)) for v in ['baseline','adaptive']],
        full_identity_lists=dict(request_ids=[r['request_id'] for r in inputs['requests']],
            initial_HU_ids=[h['handling_unit_id'] for h in inputs['initial_stock']],
            upstream_HU_ids=[h['handling_unit_id'] for h in originals+added],
            upstream_lot_ids=[h['lot_id'] for h in originals+added]),
        summary=summary, source_hashes=fingerprints,
        scope='Input integrity candidate only. No root PASS, arrival, completed receipt, queue, runtime or performance acceptance.')
    spec = '''# W11.1 — frozen HEAVY INBOUND input candidate

Status: input_only_candidate_pending_root_review. source_kind=visual_fixture;
engine_operation=false; actual_engine_run=false; execution_ready=false. Parent W11 remains open.

Authority is accepted W01 fixture SHA 52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91,
its exact catalogue/layout/ports/registry/profiles and relevant transitive C07/C08 source fingerprints.
The builder refuses changed authoritative bytes. Neither contracts nor accepted model/reference files are outputs.
M08 means one PALLET_LOAD HU with 24 packaged units, 455kg, 1.20×1.35×1.00m.
M09 means one sealed IBC unit/HU, 654kg, 1.20×1.16×1.00m; no inferred fluid mesh or partial pick.

Preregistered synthetic choice: 12 additional external receipts, four each PALLET_LOAD, IBC,
HEAVY_BOX in that repeated order; release 90+60*i seconds for i=0..11, deadline release+600s.
All added receipts use IN_W_BULK and original INBOUND_FORKLIFT_PAIR F01/FL01.
This is one added release per 60s during the declared schedule, not measured throughput,
arrival completion, service capacity, a promised deadline, or C11 period/weight conversion.
No optimization was run to select these counts, times or classes.

Original stock: 530 HUs, 200 SKUs, 12256 units, 9403.85kg; original 24 workers and two powered vehicles.
Original 16 requests remain byte-for-value intact: eight inbound and eight outbound existing-stock HUs.
Original eight upstream HUs: 107 units, 1784.29kg, excluded from initial stock.
Added external 12 HUs/12 requests: 132 units, 5236kg; all 20 upstream HUs total 239 units, 7020.29kg.
Final request count 28 (20 planned inbound, eight original outbound). Request units are whole source HUs;
no four-unit pick is relabelled as a 24-unit pallet. Every upstream HU has a concrete unique HU/lot/request
ID, actual SKU catalogue ID/pointer, integral quantity, exact source gross mass/dimensions/orientation.
Original upstream identities are preserved and are materialized separately from distinctly external receipts.

All six original ports and their finite capacities/service assumptions remain unchanged. Added use bulk west;
original requests retain three inbound and three outbound port coverage. Each request selects the actual source
port handling rule. Manual selection is restricted to source manual families and C07 synthetic 15kg limit.
Forklift requests retain direction-specific original pairs and C08 local loaded profiles. Original LONG requests
require the positive-locked 40kg long cradle in addition to the unchanged 200kg HU; other loads use declared
two-fork support. Rating min(1000,800/arm) uses the fixed chassis reference and extended handling arm;
single-fork limit 500kg also applies. This is a synthetic equipment constraint, not structural certification.
Unknown cargo/port/profile, absent attachment, heavy manual selection, rating violation, scale changes,
overrides and source drift reject. Actual lock/support/contact, stopped reach sweeps, loaded route and
finite staging admission remain W05/W11 work. Port count is not extra equipment or simultaneous capacity.

Baseline and adaptive references in W11.1 evidence point to exactly the same materialized JSON path,
byte length and whole-file SHA, including all full HU/lot/request identities. No variant-specific stream,
seed regeneration, staff, service, port override or free relocation is permitted. Only admitted placement and
priced relocation outputs may differ; no-op is allowed and no decision/result has been made.

Run existing .venv/Scripts/python.exe -B with tools/visual/v3/build_heavy_inbound_scenario.py,
then verify_heavy_inbound_scenario.py; repeat each with --check-only. Builder check compares all three
owned output bytes without writes. Independent verifier imports no builder and reopens pinned sources,
checks semantic relations and attacks in memory after superficial rehashing. Its report is integrity evidence,
not root acceptance. UTF-8, sorted keys, LF and no volatile timestamps or recursive self hashes.

Runtime must register this input explicitly: W02 currently rejects unregistered V3 execution and actual V3
engine runs remain unsupported. Root must prove admitted baseline/candidate slots, handling/loaded routes,
exclusive resources, upstream holds and finite buffers, relocation cost, unified action clock and actual replay.
No queues, costs, duration, throughput, deadlines met, completed receipts or engine results are produced here.
'''
    return {FIXTURE:data, SPEC:spec.encode('utf8'), EVIDENCE:encode(evidence)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    values = documents()
    assert values == documents(), 'Non-reproducible production'
    for path, data in values.items():
        target = ROOT / path
        if args.check_only or target.exists():
            assert target.read_bytes() == data, 'Frozen output differs: ' + path
        else:
            target.write_bytes(data)
    print(json.dumps(dict(input_integrity=True, execution_ready=False, check_only=args.check_only,
        files={p:dict(bytes=len(d),sha256=sha(d)) for p,d in values.items()})))


if __name__ == '__main__':
    main()
