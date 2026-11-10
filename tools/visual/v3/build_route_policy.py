"""Project accepted C08 constraints for read-only visual routing. No operation admission."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/v3/contract-proposals'
OUT = ROOT / 'frontend/public/data/v3/route-policy-v3.json'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contains(outer, inner):
    return all(outer['min'][axis] <= inner['min'][axis] + 1e-9 and
               outer['max'][axis] >= inner['max'][axis] - 1e-9 for axis in range(3))


def document():
    layout_path = ROOT / 'frontend/public/data/adaptive-v3/layout-manifest.json'
    c08_path = BASE / 'vehicle-handling-v3.json'
    layout, c08 = read(layout_path), read(c08_path)
    data = layout['data']
    assert c08['schema_version'] == '0.2.0' and c08['layout_content_hash'] == layout['layout_content_hash']
    profiles = {p['profile_id']: p for p in data['graphs']['vehicle_profiles']}
    profiles['nonlong_forklift'] = data['storage']['access_profiles']['nonlong_forklift']
    bare = profiles['unloaded_bare']['component_bounds_local_m']
    proof = {}
    for name, profile in profiles.items():
        components = profile['component_bounds_local_m']
        assert all(any(contains(component, box) for component in components) for box in bare), name
        proof[name] = dict(profile_id=name, bare_components=bare, accepted_components=components,
                           component_subset_verified=True, arc_ids=[])
    table = data['graphs']['vehicle']['arcs']
    arcs = [dict(zip(table['columns'], row)) for row in table['rows']]
    width = max(b['max'][0] for b in bare) - min(b['min'][0] for b in bare)
    height = max(b['max'][1] for b in bare)
    for arc in arcs:
        assert height + .25 <= arc['clear_height_m'] + 1e-9
        if arc['clear_width_m'] is not None:
            assert width + .5 <= arc['clear_width_m'] + 1e-9
        # A stricter verified component envelope is a sufficient empty-vehicle bound.
        # It grants neither carried cargo permission nor an actual service action.
        profile = min(arc['allowed_geometry_profile_ids'], key=lambda p: (p != 'unloaded_bare', p))
        assert profile in proof
        proof[profile]['arc_ids'].append(arc['arc_id'])
    for row in proof.values():
        row['arc_ids'].sort()
    source_paths = [layout_path, c08_path, ROOT / 'frontend/public/data/v3/warehouse-fixture-v3.json',
                    BASE / 'port-resource-policy-v3.json', Path(__file__)]
    return dict(schema_id='qoima.visual-route-policy.v3', source_kind='visual_fixture',
        engine_operation=False, operational_admission=False, metrics_scope='none',
        layout_content_hash=layout['layout_content_hash'], layout_sha256=sha(layout_path),
        source_hashes={p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths},
        bare_geometry_subset_groups=[proof[k] for k in sorted(proof) if proof[k]['arc_ids']],
        bare_subset_scope='Empty vehicle only. Original stricter accepted envelope/analytic arc/traffic/pair restrictions retained. This is explicit component containment, not a cargo whitelist or port-service override.',
        loads=c08['loads'], loaded_arc_eligibility=c08['per_cargo_arc_eligibility'],
        ports=c08['ports'], rating_design=c08['rating_design'],
        equipment_pairs=read(BASE / 'port-resource-policy-v3.json')['forklift_pairs'],
        route_policy=c08['route_policy'],
        admission_scope='Canonical geometry routes only. Cargo/worker/job/reservation/staging/actual contact and lock evidence must be admitted by W workflows. A port service point is not a gate crossing or completed operation.',
        no_straight_line_fallback=True, cargo_overrides_allowed=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    d = document()
    data = (json.dumps(d, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    if args.check_only:
        assert OUT.read_bytes() == data, 'Stale route policy projection'
    else:
        OUT.write_bytes(data)
    print(json.dumps(dict(passed=True, check_only=args.check_only, engine_operation=False,
                         loads=6, bare_subset_arcs=sum(len(g['arc_ids']) for g in d['bare_geometry_subset_groups']),
                         sha256=sha(OUT))))


if __name__ == '__main__':
    main()
