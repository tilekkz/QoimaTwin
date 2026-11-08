"""Independent W01 source/identity/conservation check and rejection witnesses."""
import argparse
import copy
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/v3/contract-proposals'
FIXTURE = ROOT / 'frontend/public/data/v3/warehouse-fixture-v3.json'
REPORT = ROOT / 'docs/adaptive-v3/evidence/W01-checks.json'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def finite_number(value):
    return type(value) in [int, float] and math.isfinite(value)


def verify(d):
    require(d['schema_id'] == 'qoima.warehouse-visual-fixture.v3' and d['namespace'] == 'v3', 'SCHEMA_MISMATCH')
    require(d['source_kind'] == 'visual_fixture' and d['engine_operation'] is False and
        d['operational_admission'] is False and d['actual_v3_run_supported'] is False and
        d['visual_complete'] is False and d['backend_integration_complete'] is False and d['metrics_scope'] == 'none', 'SOURCE_SCOPE_MISMATCH')
    require(d['execution_state'] == 'not_scheduled' and d['actions'] == [] and d['completion_events'] == [], 'FABRICATED_EXECUTION')
    for path, expected in d['source_hashes'].items():
        require(sha(ROOT / path) == expected, 'SOURCE_HASH_MISMATCH')
    manifest = read(BASE / 'layout-manifest-v3.json')
    require(d['layout_ref']['layout_content_hash'] == manifest['layout_content_hash'] and
        d['layout_ref']['sha256'] == manifest['public_runtime']['sha256'] == sha(ROOT / d['layout_ref']['path']) and
        d['layout_ref']['url'] == '/data/adaptive-v3/layout-manifest.json' and
        d['layout_version'] == 'qoima-144x72-v3', 'LAYOUT_MISMATCH')
    for field in ['registry_ref', 'profiles_ref']:
        require(sha(ROOT / d[field]['path']) == d[field]['sha256'], 'PROFILE_REGISTRY_MISMATCH')
    inputs = d['inputs']
    catalog = {r['archetype_id']: r for r in read(BASE / 'cargo-catalog-v3.json')['records']}
    sku = {r['sku_id']: r for r in read(BASE / 'sku-catalog-v3.json')['skus']}
    require(inputs['skus'] == list(sku.values()), 'SKU_IDENTITY_MISMATCH')
    require(len(inputs['archetypes']) == 8 and {r['archetype_id'] for r in inputs['archetypes']} == set(catalog), 'ARCHETYPE_COUNT_MISMATCH')
    for row in inputs['archetypes']:
        require(all(value == catalog[row['archetype_id']][key] for key, value in row.items()), 'ARCHETYPE_OVERRIDE')
    registry = read(ROOT / d['registry_ref']['path'])
    require(inputs['workers'] == [{k: w[k] for k in ['actor_id', 'baseline_role', 'initial_role', 'assigned_vehicle_id']} for w in registry['workers']], 'WORKER_IDENTITY_MISMATCH')
    require(inputs['vehicles'] == registry['vehicles'], 'VEHICLE_PAIR_MISMATCH')
    original_ports = {p['port_id']: p for f in ['ports-v3.inbound.json', 'ports-v3.outbound.json'] for p in read(BASE / f)['ports']}
    ports = {p['port_id']: p for p in inputs['ports']}
    require(len(inputs['ports']) == len(ports) == 6 and set(ports) == set(original_ports), 'PORT_IDENTITY_MISMATCH')
    for p in inputs['ports']:
        require(all(value == original_ports[p['port_id']][key] for key, value in p.items()), 'PORT_OVERRIDE')
    original = {r['handling_unit_id']: r for r in read(BASE / 'baseline-assignment-v3.json')['assignments']}
    stock = {r['handling_unit_id']: r for r in inputs['initial_stock']}
    require(len(stock) == len(inputs['initial_stock']) == 530 and set(stock) == set(original), 'STOCK_IDENTITY_MISMATCH')
    slots = set()
    for item in stock.values():
        src = original[item['handling_unit_id']]
        require(all(item[k] == src[k] for k in ['lot_id', 'sku_id', 'archetype_id', 'quantity_units', 'orientation_id']), 'STOCK_CONTENT_MISMATCH')
        hu = catalog[item['archetype_id']]['handling_unit']
        require(item['dimensions_xyz_m'] == hu['dimensions_xyz_m'] and item['gross_mass_kg'] == hu['gross_mass_kg'] and item['model_scale_factor'] == 1, 'CARGO_DIMENSION_MASS_SCALE_OVERRIDE')
        location = item['location']
        require(location == dict(kind='storage_slot', slot_id=src['slot_id'], module_id=src['module_id'], placement=src['placement']), 'STOCK_PLACEMENT_MISMATCH')
        require(location['slot_id'] not in slots, 'SLOT_CAPACITY')
        slots.add(location['slot_id'])
    require(sum(r['quantity_units'] for r in stock.values()) == 12256 and
        sum(Decimal(str(r['gross_mass_kg'])) for r in stock.values()) == Decimal('9403.85') and
        len({r['sku_id'] for r in stock.values()}) == 200, 'STOCK_CONSERVATION')
    require(d['clock'] == dict(kind='absolute_visual_seconds', duration_s=1800, interval='[start_s,end_s)'), 'CLOCK_MISMATCH')
    requests = inputs['requests']
    require(len(requests) == 16 and len({r['request_id'] for r in requests}) == 16 and
        len({r['handling_unit_id'] for r in requests}) == 16, 'REQUEST_IDENTITY_MISMATCH')
    require(requests == sorted(requests, key=lambda r: (r['requested_at_s'], r['request_id'])), 'REQUEST_ORDER_MISMATCH')
    used_ports = set()
    for request in requests:
        require(request['source_kind'] == 'visual_fixture' and request['engine_operation'] is False, 'REQUEST_SOURCE_MISMATCH')
        require(request['port_id'] in ports, 'UNKNOWN_PORT')
        p = ports[request['port_id']]
        require(request['direction'] == p['direction'] and request['kind'] == ('receipt_request' if p['direction'] == 'inbound' else 'order_request'), 'PORT_DIRECTION_MISMATCH')
        require(request['sku_id'] in sku and request['archetype_id'] == sku[request['sku_id']]['archetype_id'], 'REQUEST_CARGO_IDENTITY_MISMATCH')
        require(request['archetype_id'] in p['allowed_cargo_archetype_ids'], 'PORT_CARGO_FORBIDDEN')
        hu = catalog[request['archetype_id']]['handling_unit']
        require(request['quantity_handling_units'] == 1 and request['quantity_units'] == hu['units_per_handling_unit'], 'REQUEST_QUANTITY_MISMATCH')
        at, deadline = request['requested_at_s'], request['deadline_at_s']
        require(finite_number(at) and finite_number(deadline) and 0 <= at < deadline <= 1800, 'REQUEST_TIME_INVALID')
        require(any(start <= at < end for start, end in p['open_windows']), 'PORT_CLOSED')
        incoming = request['direction'] == 'inbound'
        require(request['included_in_initial_stock'] is (not incoming) and
            request['initial_location_kind'] == ('upstream' if incoming else 'storage_slot'), 'UPSTREAM_STOCK_CONFUSION')
        if incoming:
            require(request['handling_unit_id'] not in stock and request['handling_unit_id'].startswith('v3:HU:incoming:') and request['lot_id'].startswith('v3:lot:incoming:'), 'UPSTREAM_HU_COLLISION')
        else:
            require(request['handling_unit_id'] in stock and all(request[k] == stock[request['handling_unit_id']][k] for k in ['sku_id', 'lot_id', 'archetype_id', 'quantity_units']), 'OUTBOUND_STOCK_MISSING')
        used_ports.add(p['port_id'])
    require(used_ports == set(ports), 'UNUSED_PORT')
    for direction in ['inbound', 'outbound']:
        rows = [r for r in requests if r['direction'] == direction]
        require(len(rows) == 8 and {r['archetype_id'] for r in rows} == set(catalog), 'REQUEST_FAMILY_COVERAGE')
    stream = read(ROOT / 'docs/adaptive-v3/fixtures/warehouse-request-stream-v3.json')
    require(requests == stream['requests'], 'FROZEN_INPUT_MISMATCH')
    require(d['input_hashes'] == {key: digest(value) for key, value in inputs.items()}, 'INPUT_HASH_MISMATCH')
    require(d['summary'] == dict(initial_handling_units=530, initial_skus=200, initial_quantity_units=12256,
        initial_gross_mass_kg=9403.85, occupied_slots=530, active_slots=588, free_active_slots=58,
        blocked_reserve_slots=188, incoming_requests=8, outgoing_requests=8,
        request_quantity_is_not_initial_stock=True, workers=24, vehicles=2, ports=6, archetypes=8), 'SUMMARY_MISMATCH')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    document = read(FIXTURE)
    verify(document)
    cases = []

    def reject(name, mutation, expected):
        changed = copy.deepcopy(document)
        mutation(changed)
        # Invalid semantic cases must fail even if someone recomputes generic input hashes.
        changed['input_hashes'] = {key: digest(value) for key, value in changed['inputs'].items()}
        try:
            verify(changed)
        except ValueError as error:
            require(str(error) == expected, f'Wrong rejection for {name}: {error}')
            cases.append(dict(case=name, reason=str(error), rejected=True))
        else:
            raise AssertionError('Invalid fixture accepted: ' + name)

    reject('actual_engine_label', lambda d: d.update(source_kind='actual_engine_run'), 'SOURCE_SCOPE_MISMATCH')
    reject('invented_completion', lambda d: d['completion_events'].append(dict(at_s=10)), 'FABRICATED_EXECUTION')
    reject('layout_content_hash', lambda d: d['layout_ref'].update(layout_content_hash='0' * 64), 'LAYOUT_MISMATCH')
    reject('extra_PK01_worker', lambda d: d['inputs']['workers'].append(dict(d['inputs']['workers'][0], actor_id='PK01')), 'WORKER_IDENTITY_MISMATCH')
    reject('driver_wrong_vehicle', lambda d: d['inputs']['vehicles'][0].update(driver_actor_id='F02'), 'VEHICLE_PAIR_MISMATCH')
    reject('port_widening', lambda d: d['inputs']['ports'][0].update(clear_width_m=99), 'PORT_OVERRIDE')
    reject('duplicate_stock', lambda d: d['inputs']['initial_stock'].append(d['inputs']['initial_stock'][0]), 'STOCK_IDENTITY_MISMATCH')
    reject('changed_stock_units', lambda d: d['inputs']['initial_stock'][0].update(quantity_units=2000), 'STOCK_CONTENT_MISMATCH')
    reject('shrink_cargo', lambda d: d['inputs']['initial_stock'][0].update(model_scale_factor=.5), 'CARGO_DIMENSION_MASS_SCALE_OVERRIDE')
    reject('reduce_cargo_mass', lambda d: d['inputs']['initial_stock'][0].update(gross_mass_kg=.01), 'CARGO_DIMENSION_MASS_SCALE_OVERRIDE')
    reject('teleport_storage', lambda d: d['inputs']['initial_stock'][0]['location']['placement'].update(bottom_y_m=99), 'STOCK_PLACEMENT_MISMATCH')
    reject('duplicate_request', lambda d: d['inputs']['requests'][1].update(request_id=d['inputs']['requests'][0]['request_id']), 'REQUEST_IDENTITY_MISMATCH')
    reject('unknown_port', lambda d: d['inputs']['requests'][0].update(port_id='IN_FAKE'), 'UNKNOWN_PORT')
    reject('wrong_port_direction', lambda d: d['inputs']['requests'][0].update(port_id='OUT_S_EXPRESS'), 'PORT_DIRECTION_MISMATCH')
    reject('manual_port_heavy', lambda d: d['inputs']['requests'][4].update(port_id='IN_E_PARCEL'), 'PORT_CARGO_FORBIDDEN')
    reject('request_wrong_units', lambda d: d['inputs']['requests'][0].update(quantity_units=2000), 'REQUEST_QUANTITY_MISMATCH')
    reject('deadline_before_release', lambda d: d['inputs']['requests'][0].update(deadline_at_s=0), 'REQUEST_TIME_INVALID')
    reject('nonfinite_request_time', lambda d: d['inputs']['requests'][0].update(deadline_at_s=float('nan')), 'REQUEST_TIME_INVALID')
    reject('upstream_counted_stock', lambda d: d['inputs']['requests'][0].update(included_in_initial_stock=True), 'UPSTREAM_STOCK_CONFUSION')
    reject('missing_outbound_HU', lambda d: d['inputs']['requests'][1].update(handling_unit_id='v3:HU:initial:fake:01'), 'OUTBOUND_STOCK_MISSING')
    reject('false_summary', lambda d: d['summary'].update(initial_handling_units=538), 'SUMMARY_MISMATCH')
    report = dict(passed=True, source_kind='visual_fixture', engine_operation=False,
        initial_HUs_checked=530, SKUs_checked=200, initial_quantity_units=12256, initial_gross_mass_kg=9403.85,
        workers_checked=24, vehicles_checked=2, ports_checked=6, materialized_requests_checked=16,
        all_eight_archetypes_in_each_direction=True, no_execution_or_metrics_generated=True,
        incoming_requests_excluded_from_initial_stock=True, negatives=cases,
        input_hashes={**document['source_hashes'], FIXTURE.relative_to(ROOT).as_posix(): sha(FIXTURE),
                      Path(__file__).relative_to(ROOT).as_posix(): sha(Path(__file__))})
    data = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if args.check_only:
        require(REPORT.read_bytes() == data, 'STALE_W01_REPORT')
    else:
        REPORT.write_bytes(data)
    print(json.dumps(dict(passed=True, engine_operation=False, initial_HUs=530, SKUs=200,
                          requests=16, ports=6, negative_cases=len(cases), check_only=args.check_only)))


if __name__ == '__main__':
    main()
