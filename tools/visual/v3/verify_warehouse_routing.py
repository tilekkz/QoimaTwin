"""Independent original-ID graph distances for current TypeScript route outputs."""
import argparse
from collections import defaultdict
import hashlib
import heapq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/v3/contract-proposals'
OUT = ROOT / 'docs/adaptive-v3/evidence/W03.1-independent.json'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shortest(adjacency, start, end):
    distances = {start: 0}
    pending = [(0, start)]
    while pending:
        distance, node = heapq.heappop(pending)
        if distance != distances[node]:
            continue
        if node == end:
            return distance
        for arc in adjacency[node]:
            target = arc['to_node_id']
            new = distance + arc['length_m']
            if new < distances.get(target, float('inf')):
                distances[target] = new
                heapq.heappush(pending, (new, target))
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    report_path = ROOT / 'docs/adaptive-v3/evidence/W03.1-checks.json'
    r = read(report_path)
    assert r['passed'] and not r['engine_operation']
    for path, expected in r['input_hashes'].items():
        assert sha(ROOT / path) == expected, path
    original = read(BASE / 'layout-links-v3.json')
    c08 = read(BASE / 'vehicle-handling-v3.json')
    allowed = {row['archetype_id']: set(row['allowed_arc_ids']) for row in c08['per_cargo_arc_eligibility']}
    graphs = {kind: original[kind + '_graph'] for kind in ['walk', 'vehicle']}
    distances = []
    for route in r['positive_routes']:
        kind = route['graph']
        graph = graphs[kind]
        arcs = {a['arc_id']: a for a in graph['arcs']}
        adjacency = defaultdict(list)
        vehicle = kind == 'vehicle'
        pair = 'INBOUND_FORKLIFT_PAIR' if route['vehicle_id'] == 'FL01' else 'OUTBOUND_FORKLIFT_PAIR'
        for arc in arcs.values():
            if vehicle:
                if pair not in arc['equipment_pair_refs']:
                    continue
                aid = route['cargo_archetype_id']
                if aid is not None and (arc['arc_id'] not in allowed[aid] or arc.get('cargo_transport_supported') is False):
                    continue
                # The independently checked TS report binds explicit bare subset proofs for every arc.
                if aid is None:
                    assert arc['allowed_geometry_profile_ids']
            elif route['mode'] not in arc['allowed_modes']:
                continue
            adjacency[arc['from_node_id']].append(arc)
        node = route['from_node_id']
        length = 0
        for arc_id in route['arc_ids']:
            arc = arcs[arc_id]
            assert arc['from_node_id'] == node
            assert arc in adjacency[node]
            node = arc['to_node_id']
            length += arc['length_m']
        assert node == route['to_node_id']
        distance = shortest(adjacency, route['from_node_id'], route['to_node_id'])
        assert distance is not None and abs(distance - length) < 1e-7
        assert abs(length - route['length_m']) < 1e-7
        distances.append(dict(mode=route['mode'], cargo_archetype_id=route['cargo_archetype_id'],
            from_node_id=route['from_node_id'], to_node_id=route['to_node_id'],
            original_graph_shortest_m=distance, reported_m=route['length_m']))
    assert len(distances) == 78
    assert len(r['negative_cases']) == 31
    assert all(not row['cost_evaluated'] and row['length_m'] is None and not row['arc_ids'] for row in r['negative_cases'])
    result = dict(passed=True, source_kind='visual_fixture', engine_operation=False,
        original_ID_graph_shortest_routes_checked=78, before_cost_negative_cases=31,
        port_family_cases=36, port_family_positive=17, distances=distances,
        input_hashes={**r['input_hashes'], report_path.relative_to(ROOT).as_posix(): sha(report_path),
                      'docs/v3/contract-proposals/layout-links-v3.json': sha(BASE / 'layout-links-v3.json'),
                      Path(__file__).relative_to(ROOT).as_posix(): sha(Path(__file__))},
        scope='Independent static geometry distances only; bare component containment separately checked against original runtime profiles. No actor/resource grants, action execution or actual engine operation.')
    data = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    if args.check_only:
        assert OUT.read_bytes() == data, 'Stale independent route proof'
    else:
        OUT.write_bytes(data)
    print(json.dumps(dict(passed=True, independent_routes=78, negative_cases=31, engine_operation=False)))


if __name__ == '__main__':
    main()
