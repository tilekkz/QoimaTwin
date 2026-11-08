"""Independently compare runtime storage poses to the original C04 local-space support recipe."""
import hashlib
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'docs/adaptive-v3/evidence/W04.1-independent.json'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


runtime = read('docs/adaptive-v3/evidence/W04.1-checks.json')
assert runtime['passed'] and runtime['source_kind'] == 'visual_fixture' and runtime['engine_operation'] is False
for path, digest in runtime['input_hashes'].items():
    assert sha(path) == digest, ('Stale cargo state proof', path)
paths = ['docs/adaptive-v3/evidence/W04.1-checks.json',
         'docs/v3/contract-proposals/storage-slots-v3.json',
         'docs/v3/contract-proposals/cargo-catalog-v3.json',
         'frontend/public/data/v3/warehouse-fixture-v3.json',
         'tools/visual/v3/verify_warehouse_cargo.py']
source = read(paths[1])
slots = {s['slot_id']: s for s in source['slots']}
modules = {m['module_id']: m for m in source['modules']}
fixture = read(paths[3])
stock = {h['handling_unit_id']: h for h in fixture['inputs']['initial_stock']}
assert len(stock) == len(runtime['initial_placements']) == 530
assert len({r['handling_unit_id'] for r in runtime['initial_placements']}) == 530
assert len(runtime['negative_cases']) == 24 and all(c['rejected'] for c in runtime['negative_cases'])
assert runtime['atomic_swap'] and runtime['absolute_reset'] and runtime['world_corner_checks'] == 4240
maximum_error = 0
for placement in runtime['initial_placements'] + runtime['compatible_free_relocations']:
    hu = stock[placement['handling_unit_id']]
    slot = slots[placement['slot_id']]
    module = modules[slot['module_id']]
    assert not slot['reserve_only'] and not slot['retrieval_blocked']
    assert hu['archetype_id'] in slot['allowed_cargo_archetype_ids']
    d = hu['dimensions_xyz_m']
    clearance = slot['clearance_each_side_m']
    assert all(Decimal(str(a)) + 2 * Decimal(str(clearance)) <= Decimal(str(b))
               for a, b in zip(d, slot['usable_dimensions_xyz_m']))
    assert hu['gross_mass_kg'] <= slot['max_payload_kg']
    anchor = slot['bin_anchor_module_local']
    bounds = slot['usable_bounds_module_local']
    local = [anchor[0], anchor[1], bounds['max'][2] - clearance - d[2] / 2]
    yaw = module['yaw_rad']
    c, s = math.cos(yaw), math.sin(yaw)
    origin = module['world_pos']
    world = [origin[0] + c * local[0] + s * local[2], origin[1] + local[1], origin[2] - s * local[0] + c * local[2]]
    error = max(abs(a - b) for a, b in zip(world, placement['position']))
    maximum_error = max(maximum_error, error)
    assert error < 1e-8 and placement['yaw_rad'] == yaw
    assert hu['model_scale_factor'] == 1 and hu['orientation_id'] == 'upright_xyz'
report = dict(passed=True, source_kind='visual_fixture', engine_operation=False,
              independently_checked_initial_HUs=530, independently_checked_free_relocations=8,
              maximum_position_error_m=maximum_error, negative_cases=24,
              input_hashes={p: sha(p) for p in paths},
              scope='Original C04 Decimal fit and local front-aligned/support placement, immutable W01 HU identity. Native mesh contacts and carrier bindings remain W04.2/W04.3.')
text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
if '--check-only' in sys.argv:
    assert REPORT.read_text(encoding='utf8') == text, 'Stale independent cargo placement proof'
else:
    REPORT.write_text(text, encoding='utf8')
print(json.dumps({k: v for k, v in report.items() if k not in ['input_hashes', 'scope']}))
