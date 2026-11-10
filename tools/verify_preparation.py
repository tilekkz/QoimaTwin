"""Read-only checks for participant A's input contracts and prepared data.

This validates supplied fixtures; it is not participant B's simulation engine.
No data or research outputs are regenerated.
"""
from collections import defaultdict
import csv
import hashlib
import heapq
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
checks = []

def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def rows(path):
    with (ROOT / path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))

def check(name, condition):
    if not condition:
        raise ValueError(name)
    checks.append(name)

def close(left, right):
    return abs(left - right) <= 1e-6

def main():
    for path in sorted(ROOT.glob('contracts/*.json')):
        load(path.relative_to(ROOT))
    layout = load('contracts/layout.example.json')
    run = load('contracts/hand_checked_run.json')
    expected = load('contracts/hand_checked_expected.json')
    for value, schema_path in [(layout, 'contracts/layout.schema.json'), (run, 'contracts/run.schema.json')]:
        schema = load(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
        checks.append(schema_path)
    check('schema/layout versions agree', run['schema_version'] == layout['schema_version'] == '1.0' and run['layout_version'] == layout['layout_version'])
    nodes = {node['node_id']: node['pos'] for node in layout['nodes']}
    slots = {slot['slot_id']: slot for slot in layout['slots']}
    graph = defaultdict(dict)
    check('31 unique nodes, 33 edges, 20 unique slots', len(nodes) == len(layout['nodes']) == 31 and len(layout['edges']) == 33 and len(slots) == len(layout['slots']) == 20)
    for edge in layout['edges']:
        a, b, length = edge['a'], edge['b'], edge['length_m']
        check(f'edge {a}/{b}', a in nodes and b in nodes and length > 0 and close(math.dist(nodes[a], nodes[b]), length) and b not in graph[a])
        graph[a][b] = graph[b][a] = length
    distances = {}
    for start in nodes:
        costs = {start: 0.0}
        queue = [(0.0, start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost > costs[node]:
                continue
            for neighbor, weight in graph[node].items():
                candidate = cost + weight
                if candidate < costs.get(neighbor, float('inf')):
                    costs[neighbor] = candidate
                    heapq.heappush(queue, (candidate, neighbor))
        check(f'reachable graph from {start}', len(costs) == 31)
        distances[start] = costs
    a = slots['S_A1_B1']['pick_node_id']
    b = slots['S_A2_B1']['pick_node_id']
    pack = layout['pack_node_id']
    check('G2: cross-aisle 8m, no 4m shortcut', close(distances[a][b], 8))
    check('G3: complete route 21.2m', close(distances[pack][a] + distances[a][b] + distances[b][pack], expected['route_distance_m']))
    check('buffer service route 9.6m', close(distances[pack][layout['buffer_node_id']], 9.6))
    actions_by_actor = defaultdict(list)
    total_distance = 0.0
    for action in run['actions']:
        actions_by_actor[action['actor_id']].append(action)
        if action['kind'] != 'WALK':
            continue
        points = action['waypoints']
        check(f"WALK endpoints {action['action_id']}", close(points[0]['at_s'], action['start_s']) and close(points[-1]['at_s'], action['end_s']))
        for left, right in zip(points, points[1:]):
            length = graph[left['node_id']].get(right['node_id'])
            check(f"WALK legal edge and speed {action['action_id']}", length is not None and left['pos'] == nodes[left['node_id']] and right['pos'] == nodes[right['node_id']] and close(right['at_s'] - left['at_s'], length / run['config']['walk_speed_mps']))
            total_distance += length
    for actor, actions in actions_by_actor.items():
        ordered = sorted(actions, key=lambda action: action['start_s'])
        check(f'non-overlap {actor}', all(left['end_s'] <= right['start_s'] for left, right in zip(ordered, ordered[1:])))
    check('distance matches fixture and backend metrics', close(total_distance, expected['route_distance_m']) and close(total_distance, run['metrics']['total_distance_m']))
    picks = [action for action in run['actions'] if action['kind'] == 'PICK']
    for action in picks:
        check(f"PICK assignment/position {action['action_id']}", run['initial_assignment'][action['slot_id']] == action['sku_id'] and action['pos'] == nodes[slots[action['slot_id']]['pick_node_id']])
    drop = next(action for action in run['actions'] if action['kind'] == 'DROPOFF')
    packing = next(action for action in run['actions'] if action['kind'] == 'PACK')
    check('ready and completed hand arithmetic', close(drop['end_s'], expected['ready_for_pack_s']) and close(packing['end_s'], expected['completed_s']))
    check('one order, zero packing queue', run['metrics']['completed_total'] == 1 and run['metrics']['max_pack_queue'] == 0)
    check('event ordering', run['events'] == sorted(run['events'], key=lambda event: (event['at_s'], event['seq'])))
    check('two picker actors even if P2 idle', sorted(actor['actor_id'] for actor in run['actors'] if actor['role'] == 'picker') == ['P1', 'P2'])
    baseline = load('contracts/baseline_assignment.example.json')
    assignment = baseline['assignment'] if 'assignment' in baseline else baseline['initial_assignment']
    check('runtime assignment slot to SKU', set(assignment) == set(slots) and len(set(assignment.values())) == 20)
    plan = load('contracts/plan.example.json')
    occupied = dict(assignment)
    occupied['BUFFER'] = None
    for transfer in plan['transfers']:
        source, destination, sku = transfer['from_location'], transfer['to_location'], transfer['sku_id']
        check(f"executable transfer {transfer['seq']}", occupied[source] == sku and occupied[destination] is None)
        occupied[destination], occupied[source] = sku, None
    check('buffer empty and plan assignment preserved', occupied.pop('BUFFER') is None and occupied == plan['assignment_after'])
    baskets = rows('data/test_basket_lines_20days.csv')
    master = rows('data/sku_master_20.csv')
    predictions = rows('data/forecast_probe_predictions.csv')
    manifest = load('data/data_manifest.json')
    check('20 SKU and 20 test dates', len(master) == 20 and len(rows('data/test_dates.csv')) == 20)
    check('1745 visits, 749 assortment baskets', len(baskets) == 1745 and len({row['order_id'] for row in baskets}) == 749)
    check('400 forecast targets', len(predictions) == 400)
    check('positive unique order-SKU lines', all(float(row['quantity']) > 0 for row in baskets) and len({(row['order_id'], row['sku_id']) for row in baskets}) == len(baskets))
    check('real assignment matches SKU catalog', set(assignment.values()) == {row['sku_id'] for row in master})
    check('coverage caveat retained', manifest['coverage']['test_invoices_completely_within_selection'] == 7 and manifest['coverage']['test_pick_visit_coverage'] < 0.04)
    for path in sorted(ROOT.glob('data/*.csv')):
        with path.open(encoding='utf-8', newline='') as stream:
            columns = next(csv.reader(stream))
        forbidden = {'customerid', 'customer_id', 'customer id', 'invoice', 'invoiceno', 'invoice_id', 'raw_invoice', 'original_invoice'}
        check(f'no raw customer/invoice identifiers {path.name}', not any(column.lower() in forbidden for column in columns))
    changed = []
    for record in load('package_manifest.json')['files']:
        actual = hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest()
        if actual != record['sha256']:
            changed.append(record['path'])
    check('original research/contracts/data unchanged', set(changed) == {'.gitignore', 'README.md'})
    print(json.dumps({'status': 'passed', 'checks_passed': len(checks), 'intentional_snapshot_changes': changed, 'scope': 'prepared inputs and manual fixtures only; no full backend/ML reproduction or warehouse performance measurement', 'checks': checks}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
