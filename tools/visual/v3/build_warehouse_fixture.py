"""W01 deterministic visual inputs. This does not execute jobs or a DES."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/v3/contract-proposals'
STREAM = ROOT / 'docs/adaptive-v3/fixtures/warehouse-request-stream-v3.json'
OUT = ROOT / 'frontend/public/data/v3/warehouse-fixture-v3.json'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')).hexdigest()


def stream_document():
    stock = read(BASE / 'baseline-assignment-v3.json')['assignments']
    # Chosen once before any W scenario/assignment comparison, independent of C11 costs.
    families = [
        ('SMALL_CARTON', 'IN_E_PARCEL', 'OUT_S_EXPRESS'),
        ('STANDARD_CARTON', 'IN_N_STANDARD', 'OUT_W_RETAIL'),
        ('HEAVY_BOX', 'IN_W_BULK', 'OUT_E_B2B'),
        ('PALLET_LOAD', 'IN_N_STANDARD', 'OUT_W_RETAIL'),
        ('IBC', 'IN_W_BULK', 'OUT_E_B2B'),
        ('LONG_BUNDLE', 'IN_W_BULK', 'OUT_E_B2B'),
        ('DRUM', 'IN_W_BULK', 'OUT_W_RETAIL'),
        ('FRAGILE_CRATE', 'IN_W_BULK', 'OUT_E_B2B'),
    ]
    requests = []
    for ordinal, (family, incoming, outgoing) in enumerate(families, 1):
        item = min((r for r in stock if r['archetype_id'] == family), key=lambda r: r['handling_unit_id'])
        for direction, port, at in [('inbound', incoming, 60 + (ordinal - 1) * 120),
                                    ('outbound', outgoing, 120 + (ordinal - 1) * 120)]:
            incoming_request = direction == 'inbound'
            requests.append(dict(request_id=f'v3:request:base:{direction}:{ordinal:02d}',
                kind='receipt_request' if incoming_request else 'order_request',
                direction=direction, requested_at_s=at, deadline_at_s=at + 600,
                port_id=port, sku_id=item['sku_id'], archetype_id=family,
                handling_unit_id=f'v3:HU:incoming:{item["sku_id"]}:01' if incoming_request else item['handling_unit_id'],
                lot_id=f'v3:lot:incoming:{item["sku_id"]}' if incoming_request else item['lot_id'],
                quantity_handling_units=1, quantity_units=item['quantity_units'],
                initial_location_kind='upstream' if incoming_request else 'storage_slot',
                included_in_initial_stock=not incoming_request,
                source_kind='visual_fixture', engine_operation=False))
    return dict(schema_id='qoima.visual-request-stream.v3', source_kind='visual_fixture',
        engine_operation=False, operational_admission=False, duration_s=1800,
        requests=sorted(requests, key=lambda r: (r['requested_at_s'], r['request_id'])),
        assumptions='Fixed illustrative absolute release/deadline seconds; not measured arrivals, service completion times or a conversion of C10/C11 unclocked planning periods. No random event-loop generation.',
        execution_policy='Inputs only. W workflows must independently admit handlers, cargo, paths, finite buffers and exclusive resources before changing stock or reporting completion.')


def fixture_document():
    stream = read(STREAM)
    assert encoded(stream) == encoded(stream_document()), 'Frozen base requests changed; declare a separate scenario instead'
    assignment = read(BASE / 'baseline-assignment-v3.json')
    catalog = read(BASE / 'cargo-catalog-v3.json')
    manifest = read(BASE / 'layout-manifest-v3.json')
    registry_path = ROOT / 'frontend/public/data/v3/worker-registry-v3.json'
    profiles_path = ROOT / 'frontend/public/data/v3/worker-profiles-v3.json'
    registry = read(registry_path)
    archetypes = [{k: r[k] for k in ['archetype_id', 'unit', 'handling_unit', 'orientation', 'handling', 'fragile', 'stacking']} for r in catalog['records']]
    cargo = {r['archetype_id']: r for r in archetypes}
    initial = []
    for row in assignment['assignments']:
        hu = cargo[row['archetype_id']]['handling_unit']
        initial.append(dict(handling_unit_id=row['handling_unit_id'], lot_id=row['lot_id'],
            sku_id=row['sku_id'], archetype_id=row['archetype_id'], quantity_units=row['quantity_units'],
            dimensions_xyz_m=hu['dimensions_xyz_m'], gross_mass_kg=hu['gross_mass_kg'],
            model_scale_factor=1, orientation_id=row['orientation_id'],
            location=dict(kind='storage_slot', slot_id=row['slot_id'], module_id=row['module_id'],
                          placement=row['placement'])))
    ports = []
    for filename in ['ports-v3.inbound.json', 'ports-v3.outbound.json']:
        for p in read(BASE / filename)['ports']:
            ports.append({k: p[k] for k in ['port_id', 'direction', 'world_pos', 'service_node_id',
                'service_node_world_pos', 'allowed_cargo_archetype_ids', 'clear_width_m', 'clear_height_m',
                'available_equipment_refs', 'resource_requirements', 'service_capacity',
                'finite_buffer_capacity', 'service_time_rule', 'open_windows']})
    workers = [{k: w[k] for k in ['actor_id', 'baseline_role', 'initial_role', 'assigned_vehicle_id']} for w in registry['workers']]
    relative_sources = [
        'docs/v3/contract-proposals/layout-manifest-v3.json', manifest['public_runtime']['path'],
        'docs/v3/contract-proposals/baseline-input-v3.json', 'docs/v3/contract-proposals/baseline-assignment-v3.json',
        'docs/v3/contract-proposals/cargo-catalog-v3.json', 'docs/v3/contract-proposals/sku-catalog-v3.json',
        'docs/v3/contract-proposals/ports-v3.inbound.json', 'docs/v3/contract-proposals/ports-v3.outbound.json',
        'docs/v3/contract-proposals/port-resource-policy-v3.json', 'docs/v3/contract-proposals/handoff/manifest.json',
        registry_path.relative_to(ROOT).as_posix(), profiles_path.relative_to(ROOT).as_posix(),
        STREAM.relative_to(ROOT).as_posix(), Path(__file__).relative_to(ROOT).as_posix(),
    ]
    inputs = dict(initial_stock=initial, requests=stream['requests'], workers=workers,
                  vehicles=registry['vehicles'], ports=ports, archetypes=archetypes,
                  skus=read(BASE / 'sku-catalog-v3.json')['skus'])
    return dict(schema_id='qoima.warehouse-visual-fixture.v3', fixture_id='v3:fixture:warehouse-base:001',
        namespace='v3', layout_version='qoima-144x72-v3', source_kind='visual_fixture',
        engine_operation=False, operational_admission=False, actual_v3_run_supported=False,
        visual_complete=False, backend_integration_complete=False, metrics_scope='none',
        clock=dict(kind='absolute_visual_seconds', duration_s=stream['duration_s'], interval='[start_s,end_s)'),
        layout_ref=dict(path=manifest['public_runtime']['path'], sha256=manifest['public_runtime']['sha256'],
            url='/data/adaptive-v3/layout-manifest.json', layout_content_hash=manifest['layout_content_hash']),
        registry_ref=dict(path=registry_path.relative_to(ROOT).as_posix(), sha256=sha(registry_path)),
        profiles_ref=dict(path=profiles_path.relative_to(ROOT).as_posix(), sha256=sha(profiles_path)),
        source_hashes={p: sha(ROOT / p) for p in relative_sources},
        inputs=inputs, input_hashes={k: content_hash(v) for k, v in inputs.items()},
        summary=dict(initial_handling_units=530, initial_skus=200, initial_quantity_units=12256,
            initial_gross_mass_kg=9403.85, occupied_slots=530, active_slots=588, free_active_slots=58,
            blocked_reserve_slots=188, incoming_requests=8, outgoing_requests=8,
            request_quantity_is_not_initial_stock=True, workers=24, vehicles=2, ports=6, archetypes=8),
        assumptions=[stream['assumptions'],
            'Initial stock is the accepted C10 baseline, frozen before evaluation. No intentional worsening, extra decorative inventory, mass/dimension scaling or legacy V2 coordinates.',
            'Incoming HUs stay upstream requests until an admitted visual workflow receives them; orders do not remove stock by their release time alone.',
            'Actor/vehicle identities and declared roles are materialized here; world placements, routes, reservations and action intervals are later W adapter/workflow outputs.',
            'No DES, throughput, AI uplift or money result is generated by these inputs. C12 remains its historical offline proposal snapshot.'],
        execution_state='not_scheduled', actions=[], completion_events=[])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze-inputs', action='store_true')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.freeze_inputs:
        data = encoded(stream_document())
        if STREAM.exists():
            assert STREAM.read_bytes() == data, 'Refuse silently overwriting frozen requests'
        else:
            STREAM.parent.mkdir(parents=True, exist_ok=True)
            STREAM.write_bytes(data)
        print(json.dumps(dict(frozen_requests=16, sha256=sha(STREAM), execution_created=False)))
        return
    data = encoded(fixture_document())
    if args.check_only:
        assert OUT.read_bytes() == data, 'Current fixture differs from deterministic source bytes'
    else:
        OUT.write_bytes(data)
    print(json.dumps(dict(passed=True, check_only=args.check_only, source_kind='visual_fixture',
                         engine_operation=False, initial_HUs=530, requests=16, sha256=sha(OUT))))


if __name__ == '__main__':
    main()
