"""C12 additive offline proposal package. Existing root proposals stay read-only."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'docs/v3/contract-proposals'
OUT = SOURCE / 'handoff'
PREFIX = 'urn:qoima:proposal:handoff:'
ROLES = ['picker', 'packer', 'receiver', 'shipper', 'forklift_driver']
ARCHETYPES = ['SMALL_CARTON', 'STANDARD_CARTON', 'HEAVY_BOX', 'PALLET_LOAD', 'IBC', 'LONG_BUNDLE', 'DRUM', 'FRAGILE_CRATE']


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def artifact(path):
    return dict(path=path, sha256=sha(path), bytes=(ROOT / path).stat().st_size)


def obj(properties, required=None):
    return dict(type='object', additionalProperties=False, properties=properties,
                required=list(properties) if required is None else required)


def arr(items, minimum=0, maximum=None, unique=False):
    result = dict(type='array', items=items, minItems=minimum)
    if maximum is not None: result['maxItems'] = maximum
    if unique: result['uniqueItems'] = True
    return result


def const(value):
    return {'const': value}


def ref(name):
    return {'$ref': PREFIX + 'common:v3:0.1.0#/$defs/' + name}


def schema(name, body):
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            '$id': PREFIX + name + ':v3:0.1.0', 'title': 'Qoima v3 isolated proposal: ' + name,
            '$comment': 'Proposal only. Offline semantic validation and exact referenced hashes are required; no canonical backend adoption.', **body}


def header(name, source):
    return dict(schema_id='qoima.' + name + '.v3-proposal', schema_version='0.1.0', status='proposal',
                source_kind=source, engine_operation=False, operational_admission=False)


def schema_header(name, source):
    return {k: const(v) for k, v in header(name, source).items()}


def build():
    source_files = sorted(SOURCE.glob('*.json'))
    original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    frozen_path = ROOT / 'work/v3/C12-source-snapshot.json'
    if frozen_path.exists():
        frozen = json.loads(frozen_path.read_text(encoding='utf8'))
        assert {f['path']: f['sha256'] for f in frozen} == {p.relative_to(ROOT).as_posix(): h for p, h in original.items()}, 'C12_ROOT_SOURCE_DRIFT'
    snapshot = ROOT / 'work/v3/protected-contracts.json'
    if snapshot.exists():
        protected = json.loads(snapshot.read_text(encoding='utf8'))['files']
    elif (OUT / 'manifest.json').exists():
        protected = read('docs/v3/contract-proposals/handoff/manifest.json')['canonical_contracts_snapshot']
    else:
        protected = [artifact(p.relative_to(ROOT).as_posix()) for p in sorted(p for p in (ROOT / 'contracts').rglob('*') if p.is_file())]
    for f in protected:
        p = (ROOT / f['path']).resolve()
        assert f['path'].startswith('contracts/') and p.is_relative_to((ROOT / 'contracts').resolve()), 'CANONICAL_PATH_OUTSIDE_CONTRACTS'
        assert hashlib.sha256(p.read_bytes()).hexdigest() == f['sha256'], 'CANONICAL_CONTRACT_DRIFT'
    protected_paths = [ROOT / f['path'] for f in protected]
    text = dict(type='string', minLength=1)
    nonnegative = dict(type='number', minimum=0)
    positive = dict(type='number', exclusiveMinimum=0)
    common = schema('common', {'$defs': {
        'hash64': dict(type='string', pattern='^[0-9a-f]{64}$'),
        'id': dict(type='string', pattern='^[A-Za-z][A-Za-z0-9:_.-]*$'),
        'role': dict(enum=ROLES),
        'archetype': dict(enum=ARCHETYPES),
        'xyz': arr(dict(type='number'), 3, 3),
        'artifact': obj({'path': dict(type='string', pattern='^(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+$'),
                         'sha256': dict(type='string', pattern='^[0-9a-f]{64}$'),
                         'bytes': dict(type='integer', minimum=1)})}})
    binding = {'layout_ref': ref('artifact'), 'layout_content_hash': ref('hash64')}
    source_properties = {**schema_header('source-labelled-input', 'geometry_proposal'), **binding,
        'source_kind': dict(enum=['geometry_proposal', 'visual_fixture', 'analytical_fixture']),
        'backend_integration_complete': const(False), 'payload_ref': ref('artifact'), 'payload_schema_id': text,
        'frame_of_reference': dict(enum=['warehouse_world', 'asset_local']),
        'metrics_scope': dict(enum=['none', 'expected_route_travel_proxy_seconds']),
        'clock': {'oneOf': [obj({'kind': const('none')}),
                           obj({'kind': const('absolute_visual_seconds'), 'duration_s': positive}),
                           obj({'kind': const('unclocked_planning_periods'), 'horizon_periods': dict(enum=[1, 2, 4, 8])})]},
        'scope': text}
    source_schema = schema('source-labelled-input', obj(source_properties))
    source_schema['allOf'] = []
    for kind, frame, payload, clock, metrics in [
        ('geometry_proposal', 'warehouse_world', 'qoima.layout-runtime.v3-proposal', 'none', 'none'),
        ('visual_fixture', 'asset_local', 'qoima.visual-packer-seam-end.v3', 'absolute_visual_seconds', 'none'),
        ('analytical_fixture', 'warehouse_world', 'qoima.adapted-assignment.v3-planning', 'unclocked_planning_periods', 'expected_route_travel_proxy_seconds')]:
        source_schema['allOf'].append({'if': {'properties': {'source_kind': const(kind)}}, 'then': {'properties': {
            'frame_of_reference': const(frame), 'payload_schema_id': const(payload), 'metrics_scope': const(metrics),
            'clock': {'properties': {'kind': const(clock)}}}}})
    port = obj({'port_id': ref('id'), 'direction': dict(enum=['inbound', 'outbound']), 'world_pos': ref('xyz'),
                'outward_normal': ref('xyz'), 'inward_facing': ref('xyz'), 'service_node_id': ref('id'),
                'service_node_world_pos': ref('xyz'), 'allowed_cargo_archetype_ids': arr(ref('archetype'), 1, unique=True),
                'clear_width_m': positive, 'clear_height_m': positive, 'operational_admission': const(False),
                'loaded_admission_scope': const('family_filter_only; loaded admission remains separate'),
                'source_ref': ref('artifact'), 'source_port_index': dict(type='integer', minimum=0, maximum=2)})
    port_schema = schema('port-view', obj({**schema_header('port-view', 'geometry_proposal'), **binding,
                                         'resource_policy_ref': ref('artifact'), 'ports': arr(port, 6, 6)}))
    worker_schema = schema('worker-profile', obj({**schema_header('worker-profile', 'visual_fixture'),
        'example_only': dict(type='boolean'), 'worker_id': ref('id'), 'registry_ref': ref('artifact'),
        'baseline_role': ref('role'), 'current_role': ref('role'), 'allowed_roles': arr(ref('role'), 1, unique=True),
        'walk_speed_m_s': positive, 'skill_levels': {'type': 'object', 'propertyNames': ref('role'),
                                                   'additionalProperties': dict(type='number', exclusiveMinimum=0, maximum=1)},
        'allowed_vehicle_ids': arr(ref('id'), unique=True),
        'assumption': obj({'kind': const('synthetic_design'), 'statement': text})}))
    worker_schema['allOf'] = [{'if': {'properties': {'allowed_roles': {'contains': const('forklift_driver')}}},
                              'then': {'properties': {'allowed_vehicle_ids': {'minItems': 1}}},
                              'else': {'properties': {'allowed_vehicle_ids': {'maxItems': 0}}}}]
    case_schema = obj({'horizon_periods': dict(enum=[1, 2, 4, 8]), 'candidate_ref': ref('artifact'),
        'comparison_inputs_sha256': ref('hash64'), 'baseline_proxy_cost_s': nonnegative,
        'adapted_proxy_cost_s': nonnegative, 'relocation_proxy_cost_s': nonnegative,
        'net_proxy_saving_s': dict(type='number'), 'transfer_count': dict(type='integer', minimum=0)})
    comparison_schema = schema('slotting-comparison', obj({**schema_header('slotting-comparison', 'analytical_fixture'), **binding,
        'scenario_ref': ref('artifact'), 'baseline_placement_ref': ref('artifact'), 'evaluation_ref': ref('artifact'),
        'metrics_scope': const('expected_route_travel_proxy_seconds'), 'staff_count': const(24),
        'staff_allocation_changes_allowed': const(False), 'period_has_clock_duration': const(False),
        'default_horizon_periods': const(1), 'one_off_relocation_cost_included': const(True),
        'allowed_differences': arr(const('HU slot placement and the explicitly priced one-off relocation sequence'), 1, 1),
        'cases': arr(case_schema, 4, 4), 'scope': text}))
    descriptor = obj({'path': common['$defs']['artifact']['properties']['path'], 'sha256': ref('hash64'),
                      'bytes': dict(type='integer', minimum=1), 'kind': dict(enum=['proposal_json', 'schema', 'example', 'documentation', 'visual_fixture', 'geometry_projection', 'canonical_v2_contract'])})
    manifest_schema = schema('bundle', obj({**schema_header('contract-handoff', 'contract_proposal_handoff'),
        'source_checkpoint_commit': dict(type='string', pattern='^[0-9a-f]{40}$'),
        'backend_integration_complete': const(False), 'actual_v3_run_supported': const(False),
        'worker_registry_materialized': const(False), 'layout_content_hash': ref('hash64'),
        'source_artifacts': arr(descriptor, 1), 'handoff_artifacts': arr(descriptor, 1),
        'extra_inputs': arr(descriptor, 1), 'canonical_contracts_snapshot': arr(descriptor, 1),
        'inventory_facts': obj({'actors': const(24), 'ports': const(6), 'handling_units': const(530),
                                'skus': const(200), 'quantity_units': const(12256), 'gross_mass_kg': const(9403.85)}),
        'scope': text}))
    schemas = {'common': common, 'source-labelled-input': source_schema, 'port-view': port_schema,
               'worker-profile': worker_schema, 'slotting-comparison': comparison_schema, 'bundle': manifest_schema}
    files = {'schemas/' + n + '.schema.json': json.dumps(s, indent=2) + '\n' for n, s in schemas.items()}
    layout = read('docs/v3/contract-proposals/layout-manifest-v3.json')
    layout_ref = artifact('docs/v3/contract-proposals/layout-manifest-v3.json')
    layout_hash = layout['layout_content_hash']
    examples = {}
    for kind, payload, frame, clock, scope in [
        ('geometry_proposal', 'frontend/public/data/adaptive-v3/layout-manifest.json', 'warehouse_world', {'kind': 'none'}, 'Geometry/data projection only; inventory and scheduling remain uninitialized.'),
        ('visual_fixture', 'frontend/public/data/v3/packer-seam-end.json', 'asset_local', {'kind': 'absolute_visual_seconds', 'duration_s': 7.5}, 'Isolated accepted P04 finishing clip on an existing closed/taped parcel; not a warehouse run or cargo transport.'),
        ('analytical_fixture', 'docs/v3/contract-proposals/adapted-assignment-v3.json', 'warehouse_world', {'kind': 'unclocked_planning_periods', 'horizon_periods': 1}, 'Default one-period C11 no-op; expected travel proxy only, no DES/throughput/money.')]:
        examples[kind + '-input'] = {**header('source-labelled-input', kind), 'backend_integration_complete': False,
            'layout_ref': layout_ref, 'layout_content_hash': layout_hash, 'payload_ref': artifact(payload),
            'payload_schema_id': read(payload)['schema_id'], 'frame_of_reference': frame, 'clock': clock,
            'metrics_scope': 'expected_route_travel_proxy_seconds' if kind == 'analytical_fixture' else 'none', 'scope': scope}
    ports = []
    for name in ['ports-v3.inbound.json', 'ports-v3.outbound.json']:
        path = 'docs/v3/contract-proposals/' + name
        for index, p in enumerate(read(path)['ports']):
            ports.append({**{k: p[k] for k in ['port_id', 'direction', 'world_pos', 'outward_normal', 'inward_facing', 'service_node_id', 'service_node_world_pos', 'allowed_cargo_archetype_ids', 'clear_width_m', 'clear_height_m']},
                'operational_admission': False, 'loaded_admission_scope': 'family_filter_only; loaded admission remains separate',
                'source_ref': artifact(path), 'source_port_index': index})
    examples['ports-view'] = {**header('port-view', 'geometry_proposal'), 'layout_ref': layout_ref,
        'layout_content_hash': layout_hash, 'resource_policy_ref': artifact('docs/v3/contract-proposals/port-resource-policy-v3.json'), 'ports': ports}
    for worker, role, roles, vehicles in [('P01', 'picker', ['picker', 'packer'], []), ('F01', 'forklift_driver', ['forklift_driver'], ['FL01'])]:
        examples['worker-' + worker] = {**header('worker-profile', 'visual_fixture'), 'example_only': True,
            'worker_id': worker, 'registry_ref': artifact('contracts/actors.example.json'), 'baseline_role': role,
            'current_role': role, 'allowed_roles': roles, 'walk_speed_m_s': 1.2,
            'skill_levels': {r: 1 if r == role else .8 for r in roles}, 'allowed_vehicle_ids': vehicles,
            'assumption': {'kind': 'synthetic_design', 'statement': 'Draft capability/speed example only. No registry activation, route, workplace allocation or actual employee training is asserted; P11/P12 remain open.'}}
    cases = []
    for horizon in [1, 2, 4, 8]:
        path = 'docs/v3/contract-proposals/' + ('adapted-assignment-v3.json' if horizon == 1 else f'adapted-assignment-horizon{horizon}-v3.json')
        result = read(path); s = result['summary']
        cases.append(dict(horizon_periods=horizon, candidate_ref=artifact(path), comparison_inputs_sha256=result['comparison_inputs_sha256'],
            baseline_proxy_cost_s=s['baseline_under_same_shifted_flow_cost_s'], adapted_proxy_cost_s=s['adapted_under_same_shifted_flow_cost_s'],
            relocation_proxy_cost_s=s['one_off_relocation_cost_s'], net_proxy_saving_s=s['net_transport_cost_reduction_s'], transfer_count=s['relocation_count']))
    examples['slotting-comparison'] = {**header('slotting-comparison', 'analytical_fixture'), 'layout_ref': layout_ref,
        'layout_content_hash': layout_hash, 'scenario_ref': artifact('docs/v3/contract-proposals/adaptation-input-v3.json'),
        'baseline_placement_ref': artifact('docs/v3/contract-proposals/baseline-assignment-v3.json'),
        'evaluation_ref': artifact('docs/v3/contract-proposals/adaptation-evaluation-v3.json'),
        'metrics_scope': 'expected_route_travel_proxy_seconds', 'staff_count': 24, 'staff_allocation_changes_allowed': False,
        'period_has_clock_duration': False, 'default_horizon_periods': 1, 'one_off_relocation_cost_included': True,
        'allowed_differences': ['HU slot placement and the explicitly priced one-off relocation sequence'], 'cases': cases,
        'scope': 'Same frozen C11 N2 flows for both placements within each case; C10 is placement identity, not its old-flow cost. Horizons1/2/4/8 are explicit sensitivity cases, no measured duration or DES/staffing simulation.'}
    files.update({'examples/' + n + '.json': json.dumps(e, indent=2) + '\n' for n, e in examples.items()})
    files['README.md'] = README
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        p = OUT / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content, encoding='utf8', newline='\n')
    descriptor_for = lambda p, kind: {**artifact(p.relative_to(ROOT).as_posix()), 'kind': kind}
    manifest = {**header('contract-handoff', 'contract_proposal_handoff'),
        'source_checkpoint_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'backend_integration_complete': False, 'actual_v3_run_supported': False, 'worker_registry_materialized': False,
        'layout_content_hash': layout_hash, 'source_artifacts': [descriptor_for(p, 'schema' if '.schema.' in p.name else 'proposal_json') for p in source_files],
        'handoff_artifacts': [descriptor_for(OUT / name, 'schema' if name.startswith('schemas/') else 'example' if name.startswith('examples/') else 'documentation') for name in sorted(files)],
        'extra_inputs': [descriptor_for(ROOT / p, kind) for p, kind in [('frontend/public/data/adaptive-v3/layout-manifest.json', 'geometry_projection'), ('frontend/public/data/v3/packer-seam-end.json', 'visual_fixture')]],
        'canonical_contracts_snapshot': [descriptor_for(p, 'canonical_v2_contract') for p in protected_paths],
        'inventory_facts': dict(actors=24, ports=6, handling_units=530, skus=200, quantity_units=12256, gross_mass_kg=9403.85),
        'scope': 'Additive C12 proposal package over frozen root inputs at the recorded checkpoint. No Arman/backend/shared V2 mutation or adoption; no actual V3 engine run. Future source additions require a new reviewed bundle generation.'}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8', newline='\n')
    assert original == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    print(json.dumps(dict(source_artifacts=len(source_files), schemas=len(schemas), examples=len(examples), canonical_contracts=len(protected_paths), original_root_proposals_unchanged=True)))


README = '''# V3 contract proposal handoff — C12

This package makes the current visual/analytical interfaces reviewable in Git. It is an additive proposal, not an adopted Arman engine contract. Existing `contracts/**` and all root proposal JSON files are preserved by exact hashes. `manifest.json` binds this generation to its inputs; later additions require a new generation.

## What is available

| Interface | Source / scope |
|---|---|
| CargoArchetype and StorageSlots | Existing strict schemas, eight cargo records, packing recipes,132modules/776slots; original C01–C08 admission and conservation checks remain authoritative |
| PortView | Six exact port projections with original source references; class membership never grants loaded route/equipment admission |
| WorkerProfile | Draft P01 cross-training and F01/FL01 capability examples; original24IDs, no active registry/scheduler. P11/P12 still have to materialize and verify their whole registry and transitions |
| Source-labelled input | Geometry projection, isolated P04 visual clip and C11 analytical default. Explicit source/clock/frame/metric types; no automatic fallback between them |
| Slotting comparison | Same frozen N2 material flow/config for both alternatives in each of the1/2/4/8period cases. Default1 is a valid no-op; relocation is charged once. No throughput, complete-order duration, money or DES claim |

## Integration and migration boundary

Keep V2 readers and existing canonical schemas unchanged. V3 consumers select this proposal namespace/version explicitly, check exact content hashes and layout_content_hash, then resolve semantic IDs. Columnar numeric indices cannot be reused across layouts. Units are metres, seconds, kg, right-handed Y-up; entity scale stays1. A packaged unit, HU, lot, SKU, storage slot, workflow tote and parcel identity remain distinct.

The original C11 payload keeps its `synthetic_planning_fixture` label; the typed wrapper exposes it as `analytical_fixture` only after its known namespace/reference and false actual-run flags pass validation. The current envelope profiles cover the three named examples; another payload needs an explicit supported profile, never a guessed fallback.

`actual_engine_run` is deliberately unsupported by this proposal input envelope. There is no positive fabricated actual-run example. A future Arman-owned exporter and separately accepted adapter must supply canonical schema/version, genuine run/producer provenance, matching physical inputs, conservation and replay semantics before that mode is enabled. A JSON label/hash by itself cannot authenticate an engine result. Unsupported actual input fails visibly; it must never turn into a visual fixture silently.

Worker capability is not a job assignment or another employee. Resolve an existing ID, check its allowed role/equipment, acquire an existing free post and resources, account for its route/travel/transition, and change effective role on the source clock. Six existing packing stations do not become eight: if all six are occupied, an extra packer is inadmissible. Draft example speeds/skills are synthetic assumptions, not measured employee training or live availability. The V2 actor reference supplies IDs/baseline roles/equipment identity only; its old home coordinates are not adopted as V3 placement.

C10 supplies frozen baseline **placement**, not a comparable old-flow cost. Re-evaluate that placement under the same C11 N2 flows/horizon used for the candidate. Port weights/horizon/staff/physical inputs cannot drift between alternatives. `comparison_inputs_sha256` binds each pair; horizons have no measured clock duration. Staffing comparison is deferred and cannot be inferred from C11 slotting results.

Current limitations remain explicit: source-labelled fixtures are not operational admission; P03.5.3 pick access, remaining personnel/replay/UI/QA and scene density are still open. Geometry/data handoff does not close visual_complete or backend_integration_complete. Publication here does not record recipient acknowledgement or backend adoption; no external message is sent by these tools.

## Offline verification

From the repository: `.venv/Scripts/python.exe tools/visual/v3/validate_contract_handoff_v3.py --check-only`. It uses installed jsonschema Draft2020-12 and a local-only reference registry, validates old Cargo/Slot schema shapes and new examples, checks exact original input/protected-contract hashes, typed source/clock/frame boundaries, capabilities, port projections, conservation/comparison arithmetic and negative mutations. It performs no network request, backend write, browser launch or original-data regeneration.

To deliberately regenerate this additive package from reviewed current inputs: `.venv/Scripts/python.exe tools/visual/v3/build_contract_handoff_v3.py`, followed by the validator and a Git review/push. The manifest excludes its own hash to avoid a cycle; all other package files are bound by it. References are repository-relative and must resolve inside the repository.
'''


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
