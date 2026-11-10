"""Continuous conservative XZ swept-body witnesses for the two shown empty-truck routes."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/adaptive-v3/evidence/W03.3-clearance.json'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pose(geometry, u):
    yaw = geometry['start_yaw_rad'] + u * (geometry['end_yaw_rad'] - geometry['start_yaw_rad'])
    if geometry['kind'] == 'line':
        a, b = geometry['front_axle_start_xz_m'], geometry['front_axle_end_xz_m']
        front = [a[i] + (b[i] - a[i]) * u for i in range(2)]
    else:
        centre, q = geometry['icr_world_xz_m'], geometry['icr_vehicle_local_x_m']
        front = [centre[0] - q * math.cos(yaw), centre[1] + q * math.sin(yaw)]
    return [front[0] - .4 * math.sin(yaw), front[1] - .4 * math.cos(yaw)], yaw


def rectangle(centre, yaw, half_x, half_z):
    c, s = math.cos(yaw), math.sin(yaw)
    return [[centre[0] + c * x + s * z, centre[1] - s * x + c * z]
            for x, z in [(-half_x, -half_z), (half_x, -half_z), (half_x, half_z), (-half_x, half_z)]]


def separation(a, b, yaw):
    # Unit axes of both the moving oriented rectangle and each fixed axis-aligned obstacle.
    axes = [(1, 0), (0, 1), (math.cos(yaw), -math.sin(yaw)), (math.sin(yaw), math.cos(yaw))]
    largest = -float('inf')
    for axis in axes:
        pa = [point[0] * axis[0] + point[1] * axis[1] for point in a]
        pb = [point[0] * axis[0] + point[1] * axis[1] for point in b]
        largest = max(largest, min(pa) - max(pb), min(pb) - max(pa))
    return largest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    numeric_path = ROOT / 'docs/adaptive-v3/evidence/W03.2-checks.json'
    browser_path = ROOT / 'assets/v3/iterations/warehouse/W03.3/browser/browser-checks.json'
    source_path = ROOT / 'docs/v3/contract-proposals/layout-links-v3.json'
    storage_path = ROOT / 'docs/v3/contract-proposals/storage-layout-v3.json'
    numeric, browser, graph, storage = read(numeric_path), read(browser_path), read(source_path)['vehicle_graph'], read(storage_path)
    assert numeric['passed'] and browser['passed'] and not browser['preview_only']
    first_scene = browser['frames'][0]['state']['scene']
    arcs = {a['arc_id']: a for a in graph['arcs']}
    module_obstacles = []
    for module in storage['modules']:
        b = module['operating_bounds_world']
        module_obstacles.append((module['module_id'], rectangle([(b['min'][0] + b['max'][0]) / 2,
            (b['min'][2] + b['max'][2]) / 2], 0, (b['max'][0] - b['min'][0]) / 2, (b['max'][2] - b['min'][2]) / 2)))
    static_workers = [(worker_id, rectangle([h['world_pos'][0], h['world_pos'][2]], 0, .4, .4))
                      for worker_id, h in first_scene['actor_homes'].items() if not worker_id.startswith('F')]
    assert len(module_obstacles) == 132 and len(static_workers) == 22
    homes = {'FL01': ([6, 18], math.pi / 2), 'FL02': ([138, 18], math.pi / 2)}
    results = []
    for example in numeric['route_previews'][:2]:
        plan = example['plan']
        assert plan['cargo_archetype_id'] is None
        other = 'FL02' if plan['vehicle_id'] == 'FL01' else 'FL01'
        other_centre, other_yaw = homes[other]
        # The inactive vehicle is axis-aligned at its admitted initial service pose.
        obstacle_vehicle = (other, rectangle(other_centre, other_yaw, .6, 1.5))
        obstacles = module_obstacles + static_workers + [obstacle_vehicle]
        minimum_gap, witnesses, pair_checks = float('inf'), 0, 0

        def check(centre, yaw, half_x, half_z, arc_id):
            nonlocal minimum_gap, witnesses, pair_checks
            footprint = rectangle(centre, yaw, half_x, half_z)
            assert all(-1e-9 <= p[0] <= 144 + 1e-9 and -1e-9 <= p[1] <= 72 + 1e-9 for p in footprint), ('FLOOR_BOUNDARY', arc_id)
            for obstacle_id, obstacle in obstacles:
                gap = separation(footprint, obstacle, yaw)
                assert gap >= -1e-8, ('SWEPT_BODY_OBSTACLE', arc_id, obstacle_id, gap)
                minimum_gap = min(minimum_gap, gap)
                pair_checks += 1
            witnesses += 1

        for arc_id in plan['arc_ids']:
            g = arcs[arc_id]['geometry']
            if g['kind'] == 'line':
                a, yaw = pose(g, 0)
                b, _ = pose(g, 1)
                length = math.dist(a, b)
                check([(a[i] + b[i]) / 2 for i in range(2)], yaw, .85, 1.75 + length / 2, arc_id)
            else:
                delta = abs(g['end_yaw_rad'] - g['start_yaw_rad'])
                steps = math.ceil(delta / (math.pi / 720))
                step = delta / steps
                q = g['icr_vehicle_local_x_m']
                radius = max(math.hypot(x - q, z - .4) for x in [-.85, .85] for z in [-1.75, 1.75])
                inflation = 2 * radius * math.sin(step / 4)
                for j in range(steps + 1):
                    centre, yaw = pose(g, j / steps)
                    check(centre, yaw, .85 + inflation, 1.75 + inflation, arc_id)
        results.append(dict(vehicle_id=plan['vehicle_id'], arc_count=len(plan['arc_ids']),
            swept_witnesses=witnesses, obstacle_pairs=pair_checks, minimum_SAT_projection_gap_m=minimum_gap))
    source_paths = [numeric_path, browser_path, source_path, storage_path, Path(__file__)]
    result = dict(passed=True, source_kind='visual_fixture', engine_operation=False,
        routes=results, storage_obstacles=132, standing_worker_obstacles=22, inactive_vehicle_obstacles=1,
        vehicle_body_dimensions_xz_m=[1.2, 3], clearance_padding_m=.25,
        arc_yaw_step_max_deg=.25, inter_sample_displacement_inflation=True,
        straight_sweep_exact=True, floor_bounds_m=[144, 72],
        input_hashes={p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths},
        scope='Conservative continuous XZ geometric witnesses for two shown empty-truck routes against fixed accepted footprints. Actual mesh/driver bounds independently sampled in browser; no moving-traffic schedule, loaded workflow, structural or operational certification.')
    data = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    if args.check_only:
        assert OUT.read_bytes() == data, 'Stale route preview clearance proof'
    else:
        OUT.write_bytes(data)
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_hashes', 'scope']}))


if __name__ == '__main__':
    main()
