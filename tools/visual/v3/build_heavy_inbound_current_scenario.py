"""W11.1.1: explicit source-epoch migration, preserving historical W11.1 bytes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = 'docs/adaptive-v3/fixtures/scenarios/heavy-inbound'
BASE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
HISTORICAL = 'docs/adaptive-v3/fixtures/scenarios/W11-heavy-inbound-input-v3.json'
REGISTRY = 'frontend/public/data/v3/worker-registry-v3.json'
PROFILES = 'frontend/public/data/v3/worker-profiles-v3.json'
C08 = 'docs/v3/contract-proposals/vehicle-handling-v3.json'
C07 = 'docs/v3/contract-proposals/cargo-mass-cases-v3.json'
INPUT = DIRECTORY + '/current-input-v3.json'
PAIR = DIRECTORY + '/current-pair-v3.json'
MIGRATION = DIRECTORY + '/source-migration-v3.json'
SPEC = 'docs/adaptive-v3/specs/W11.1.1.md'
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


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ref(path):
    data = (ROOT / path).read_bytes()
    return dict(path=path, sha256=sha(data), bytes=len(data))


def deltas(before, after, pointer=''):
    """Typed JSON leaf differences, including JSON Pointer escaping."""
    if type(before) is not type(after):
        return [dict(pointer=pointer, before=before, after=after)]
    if isinstance(before, dict) and before.keys() == after.keys():
        return [row for key in sorted(before) for row in deltas(before[key], after[key],
            pointer + '/' + key.replace('~', '~0').replace('/', '~1'))]
    if isinstance(before, list) and len(before) == len(after):
        return [row for i, (a, b) in enumerate(zip(before, after)) for row in deltas(a, b, pointer + '/' + str(i))]
    return [] if before == after else [dict(pointer=pointer, before=before, after=after)]


def documents():
    base, old = read(BASE), read(HISTORICAL)
    pins = {**base['source_hashes'], **PINS}
    for path in [C08, C07]:
        for row in read(path)['source_fingerprints']:
            assert row['path'] not in pins or pins[row['path']] == row['sha256'], 'Conflicting authority'
            pins[row['path']] = row['sha256']
    # Current registry/profile references are transitive authorities, never job inputs.
    for path in [REGISTRY, PROFILES]:
        for source, digest in read(path)['source_hashes'].items():
            assert source not in pins or pins[source] == digest, 'Conflicting current worker authority'
            pins[source] = digest
    for path, digest in pins.items():
        assert sha((ROOT / path).read_bytes()) == digest, 'Pinned source drift: ' + path
    assert all(encode(base['inputs'][key]) == encode(old['inputs'][key]) for key in base['inputs'] if key != 'requests')
    requests = {r['request_id']: r for r in old['inputs']['requests']}
    assert all(encode(requests[r['request_id']]) == encode(r) for r in base['inputs']['requests'])
    migration_rows = []
    for path, commit in [(REGISTRY, '0d3a57bb9e35c8dbb43c070b6967e9aee0857e3f'),
                         (PROFILES, '8a1687737e53b4844ce68673c54bf5c41bdaf869')]:
        snapshot = DIRECTORY + '/historical-' + Path(path).name
        migration_rows.append(dict(source_path=path, historical_snapshot_ref=ref(snapshot),
            historical_git_commit=commit, current_ref=ref(path), changes=deltas(read(snapshot), read(path))))
    migration = dict(schema_id='qoima.heavy-inbound-source-migration.v3', task_id='W11.1.1',
        source_kind='visual_fixture', engine_operation=False, operational_admission=False,
        historical_input_ref=ref(HISTORICAL), current_fixture_ref=ref(BASE), sources=migration_rows,
        original_workload_preserved=True, all_28_heavy_scenario_requests_preserved=True,
        scope='Reference/fingerprint migration only. No changed worker capabilities, clip timing, workload or runtime admission.')
    migration_data = encode(migration)
    current = copy.deepcopy(old)
    current.update(schema_id='qoima.heavy-inbound-current-input.v3', task_id='W11.1.1',
        scenario_id='v3:scenario:N2_HEAVY_INBOUND:current:001',
        status='input_only_current_source_candidate_pending_root_review',
        base_fixture_ref=dict(path=BASE, sha256=PINS[BASE]), historical_input_ref=ref(HISTORICAL),
        migration_ref=dict(path=MIGRATION, sha256=sha(migration_data), bytes=len(migration_data)),
        source_hashes=dict(sorted(pins.items())), registry_ref=copy.deepcopy(base['registry_ref']),
        profiles_ref=copy.deepcopy(base['profiles_ref']))
    input_data = encode(current)
    reference = dict(path=INPUT, sha256=sha(input_data), bytes=len(input_data), inputs_sha256=current['inputs_sha256'])
    pair = dict(schema_id='qoima.heavy-inbound-current-pair.v3', task_id='W11.1.1',
        source_kind='visual_fixture', engine_operation=False, operational_admission=False, execution_ready=False,
        paired_runs=[dict(variant=v, input_ref=copy.deepcopy(reference)) for v in ['baseline', 'adaptive']],
        comparison_policy=copy.deepcopy(old['comparison_policy']),
        scope='Identical current input bytes. Same original initial placement; no adaptive placement decision or relocation/run result.')
    spec = '''# W11.1.1 — current source compatibility for heavy inbound

Input-only candidate, pending root review. Historical W11.1 and its review remain unchanged.
Current W01 fixture SHA: 81d0caad4898a68a41f9c647141e7290df480900599e82b81739809cab0f9579.
Both pair references point to the same concrete current-input-v3.json bytes and input hash.
The baseline/adaptive labels prescribe no action, relocation, result or alternate initial stock.

All historical W11.1 workload rows are preserved exactly: 530 initial HUs, 200 SKUs,
12256 stock units/9403.85kg, 24 workers, two powered vehicles, six ports and 28 requests.
These include the 16 original W01 requests plus 12 preregistered synthetic external receipts:
four each PALLET_LOAD/IBC/HEAVY_BOX, release 90+60*i seconds, deadline release+600s,
IN_W_BULK and the original inbound F01/FL01 pair. Original eight upstream HUs remain
distinct from the external twelve; none is admitted initial stock. Added total:132 units/5236kg.
Each pallet is one complete 24-unit/455kg HU at1.20x1.35x1.00m; each IBC one sealed
654kg HU at1.20x1.16x1.00m. No partial pick, scale or dimensional mass reduction.

The migration artifact records every typed leaf difference against exact-byte historical
registry/profile snapshots whose hashes match W11.1's old authority. Snapshot provenance
is recorded with source Git commits; verification thereafter needs no Git history.
Only registry receiver/shipper proof/source fingerprints and transitive source hashes changed;
worker definitions, capability profiles, clip modes/durations and resource counts are identical.
Profiles only update registry_ref/source_hashes. New authority is explicit and fail-closed.

The independent verifier reopens pinned current sources, compares every workload row,
audits all530 original placements through canonical C05 eligibility with occupied-slot and
other-HU module mass, and checks current profiles plus original C07/C08 handler/port/rating
constraints. The original same initial state is design-compatible for both pair references.
This is no operational placement admission, adaptive plan, contact, loaded route or staffing decision.
Manual15kg remains a declared synthetic assumption. Heavy HUs require the original forklift
pair plus compatible support; LONG additionally retains its40kg locked cradle requirement.

Run .venv/Scripts/python.exe -B tools/visual/v3/build_heavy_inbound_current_scenario.py
and verify_heavy_inbound_current_scenario.py; repeat each with --check-only. Builder
compares frozen output bytes and refuses replacement. Verifier imports no scenario builder;
its semantic mutation controls recompute superficial hashes. Sources, old scenario and old
proof are read-only. No source refresh, optimization, arrival completion, queue duration,
engine/throughput metric, resource admission or W11/W11.2 completion is produced.
'''
    return {MIGRATION: migration_data, INPUT: input_data, PAIR: encode(pair), SPEC: spec.encode('utf8')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    values = documents()
    assert values == documents(), 'Nonreproducible generation'
    for path, data in values.items():
        target = ROOT / path
        if args.check_only or target.exists():
            assert target.read_bytes() == data, 'Frozen output differs: ' + path
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print(json.dumps(dict(input_only=True, execution_ready=False, check_only=args.check_only,
        files={p: dict(bytes=len(d), sha256=sha(d)) for p, d in values.items()})))


if __name__ == '__main__':
    main()
