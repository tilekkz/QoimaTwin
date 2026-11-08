"""Q03: exhaustive frozen SKU/slot QA; no source, assignment or engine mutation."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from storage_eligibility import evaluate

ROOT = Path(__file__).resolve().parents[3]
REPORT = 'docs/adaptive-v3/evidence/Q03.json'
CATALOG = 'docs/v3/contract-proposals/cargo-catalog-v3.json'
SKU = 'docs/v3/contract-proposals/sku-catalog-v3.json'
STORAGE = 'docs/v3/contract-proposals/storage-slots-v3.json'
FIXTURE = 'frontend/public/data/v3/warehouse-fixture-v3.json'
# Preregistered frozen C02/C04/C05 family expectations, independent of evaluate().
# These are alternative candidate sets; shared slots cannot be summed as capacity.
EXPECTED = {
    'SMALL_CARTON': ({'SMALL', 'FLEX'}, 488, 110),
    'STANDARD_CARTON': ({'STANDARD', 'FLEX'}, 72, 55),
    'HEAVY_BOX': ({'HEAVY'}, 24, 6),
    'PALLET_LOAD': ({'HEAVY'}, 24, 5),
    'IBC': ({'HEAVY'}, 24, 3),
    'LONG_BUNDLE': ({'LONG'}, 12, 8),
    'DRUM': ({'HEAVY'}, 24, 5),
    'FRAGILE_CRATE': ({'STANDARD'}, 64, 8),
}


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def dec(n):
    return Decimal(str(n))


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def validate_frozen_mapping(records, mapping):
    rows = mapping['skus']
    canonical = [f'DEMO_{i:03}' for i in range(1, 201)]
    assert [r['sku_id'] for r in rows] == canonical, 'SKU_IDENTITIES'
    fixed = {}
    offset = 0
    for family, (_, _, count) in EXPECTED.items():
        for sku_id in canonical[offset:offset + count]:
            fixed[sku_id] = family
        offset += count
    assert offset == 200
    for sku in rows:
        assert set(sku) == {'sku_id', 'archetype_id', 'cargo_template_pointer', 'model_scale_factor'}, 'SKU_FIELDS'
        assert type(sku['model_scale_factor']) is int and sku['model_scale_factor'] == 1, 'SKU_SCALE'
        pointer = sku['cargo_template_pointer']
        assert type(pointer) is str and re.fullmatch(r'/records/(0|[1-9][0-9]*)', pointer), 'TEMPLATE_POINTER'
        index = int(pointer.split('/')[-1])
        assert 0 <= index < len(records), 'TEMPLATE_POINTER_RANGE'
        assert sku['archetype_id'] == records[index]['archetype_id'] == fixed[sku['sku_id']], 'SKU_FROZEN_TEMPLATE'
    return {r['sku_id']: r for r in rows}


def validate_frozen_stock(stock, mapping_by_id, by_id):
    assert len(stock) == len({h['handling_unit_id'] for h in stock}) == 530, 'HU_IDENTITIES'
    assert {h['sku_id'] for h in stock} == set(mapping_by_id), 'HU_SKU_IDENTITIES'
    for hu in stock:
        assert hu['archetype_id'] == mapping_by_id[hu['sku_id']]['archetype_id'], 'HU_SKU_TEMPLATE'
        template = by_id[hu['archetype_id']]['handling_unit']
        assert type(hu['model_scale_factor']) is int and hu['model_scale_factor'] == 1, 'HU_SCALE'
        assert hu['orientation_id'] == 'upright_xyz', 'HU_ORIENTATION'
        assert type(hu['quantity_units']) is int and hu['quantity_units'] > 0, 'HU_QUANTITY_TYPE'
        assert type(hu['gross_mass_kg']) in (int, float) and math.isfinite(hu['gross_mass_kg']) and hu['gross_mass_kg'] > 0, 'HU_MASS_TYPE'
        dims = hu['dimensions_xyz_m']
        assert type(dims) is list and len(dims) == 3 and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in dims), 'HU_DIMENSION_TYPE'
        assert dims == template['dimensions_xyz_m'], 'HU_DIMENSIONS'
        assert hu['quantity_units'] == template['units_per_handling_unit'], 'HU_QUANTITY'
        assert dec(hu['gross_mass_kg']) == dec(template['gross_mass_kg']), 'HU_MASS'
    assert sum(h['quantity_units'] for h in stock) == 12256, 'STOCK_UNITS'
    assert sum(dec(h['gross_mass_kg']) for h in stock) == Decimal('9403.85'), 'STOCK_MASS'


def build():
    catalog, mapping, storage, fixture = map(read, [CATALOG, SKU, STORAGE, FIXTURE])
    records = catalog['records']
    by_id = {r['archetype_id']: r for r in records}
    modules = {m['module_id']: m for m in storage['modules']}
    slots = storage['slots']
    assert set(by_id) == set(EXPECTED) and len(records) == 8
    assert len(slots) == len({s['slot_id'] for s in slots}) == 776
    assert len(modules) == 132
    assert mapping['cargo_catalog_binding']['sha256'] == sha(CATALOG)
    mapping_by_id = validate_frozen_mapping(records, mapping)
    assert mapping['operational_admission'] is False
    assert Counter(s['archetype_id'] for s in mapping['skus']) == Counter({k: v[2] for k, v in EXPECTED.items()})
    expected_orientation = {'upright_only': True,
        'permitted_orientations': [{'local_axes_in_destination': ['+X', '+Y', '+Z'], 'orientation_id': 'upright_xyz'}],
        'slot_orientation_mappings': [{'cargo_orientation_id': 'upright_xyz', 'slot_orientation_id': 'upright_xyz_in_module'}]}
    for r in records:
        assert r['orientation'] == expected_orientation
    rows = []
    all_reasons = Counter()
    total_positive = 0
    for sku in mapping['skus']:
        index = int(sku['cargo_template_pointer'].split('/')[-1])
        cargo = records[index]
        assert cargo['archetype_id'] == sku['archetype_id']
        families, expected_count, _ = EXPECTED[cargo['archetype_id']]
        accepted = []
        reasons = Counter()
        for slot in slots:
            # Oracle uses frozen family/access policy, not the solver's output/matrix.
            expected = slot['storage_type'] in families and not (slot['reserve_only'] or slot['retrieval_blocked'])
            verdict = evaluate(cargo, slot, modules[slot['module_id']])
            assert verdict['design_eligible'] is expected, (sku['sku_id'], slot['slot_id'], verdict)
            assert verdict['cost_evaluated'] is False and verdict['operational_admission'] is False
            reasons[verdict['reason']] += 1
            if expected:
                accepted.append(slot['slot_id'])
                # Independent Decimal budget/mass checks on each admitted pair.
                assert all(dec(d) + 2 * dec(slot['clearance_each_side_m']) <= dec(u)
                    for d, u in zip(cargo['handling_unit']['dimensions_xyz_m'], slot['usable_dimensions_xyz_m']))
                assert dec(cargo['handling_unit']['gross_mass_kg']) <= dec(slot['max_payload_kg'])
                assert verdict['details']['placement']['support_gap_m'] == 0
        assert len(accepted) == expected_count, sku['sku_id']
        total_positive += len(accepted)
        all_reasons.update(reasons)
        rows.append(dict(sku_id=sku['sku_id'], archetype_id=sku['archetype_id'], accepted_slots=len(accepted),
            accepted_slot_ids_sha256=hashlib.sha256(encoded(accepted)).hexdigest(), reason_counts=dict(sorted(reasons.items()))))
    assert total_positive == 58704 and sum(all_reasons.values()) == 155200
    assert all_reasons['HEIGHT_ACCESS_UNAVAILABLE'] == 200 * 188

    small = by_id['SMALL_CARTON']
    slot = next(s for s in slots if s['storage_type'] == 'SMALL' and not s['retrieval_blocked'] and not s['reserve_only'])
    module = modules[slot['module_id']]
    negatives = []
    boundary_positives = []

    def reject(name, reason, change=None, kwargs=None):
        cargo = copy.deepcopy(small)
        if change:
            change(cargo)
        verdict = evaluate(cargo, slot, module, **(kwargs or {}))
        assert verdict['design_eligible'] is False and verdict['reason'] == reason, (name, verdict)
        assert verdict['cost_evaluated'] is False and verdict['operational_admission'] is False
        negatives.append(dict(case_id=name, reason=reason, rejected_before_cost=True))

    reject('wrong_family', 'CARGO_TYPE_MISMATCH', lambda c: c['compatibility'].update(storage_type_tags=['LONG']))
    reject('forbidden_yaw', 'ORIENTATION_FORBIDDEN', kwargs={'orientation_id': 'yaw90'})
    reject('reflected_axes', 'ORIENTATION_FORBIDDEN', lambda c: c['orientation']['permitted_orientations'][0].update(local_axes_in_destination=['-X', '+Y', '+Z']))
    for axis in range(3):
        limit = float(dec(slot['usable_dimensions_xyz_m'][axis]) - 2 * dec(slot['clearance_each_side_m']))
        cargo = copy.deepcopy(small)
        cargo['handling_unit']['dimensions_xyz_m'][axis] = limit
        verdict = evaluate(cargo, slot, module)
        assert verdict['design_eligible'] is True and verdict['cost_evaluated'] is False
        boundary_positives.append(dict(case_id=f'exact_axis_{axis}_budget', dimension_m=limit, passed=True))
        reject(f'axis_{axis}_over_budget_1e-10m', 'DIMENSION_MISMATCH',
            lambda c, a=axis, value=limit: c['handling_unit']['dimensions_xyz_m'].__setitem__(a, value + 1e-10))
    for value, name in [(True, 'bool'), ('0.24', 'string'), (float('nan'), 'nan'), (float('inf'), 'infinity'), (0, 'zero'), (-1, 'negative')]:
        reject('dimension_' + name, 'ORIENTATION_FORBIDDEN', lambda c, v=value: c['handling_unit']['dimensions_xyz_m'].__setitem__(0, v))
    for value, name in [(True, 'bool'), ('0.94', 'string'), (float('nan'), 'nan'), (float('inf'), 'infinity'), (0, 'zero'), (-1, 'negative')]:
        reject('mass_' + name, 'INVALID_MASS', lambda c, v=value: c['handling_unit'].update(gross_mass_kg=v))
    for value, name in [(True, 'bool'), (1.0, 'float'), (0, 'zero'), (-1, 'negative')]:
        reject('unit_count_' + name, 'INVALID_MASS', lambda c, v=value: c['handling_unit'].update(units_per_handling_unit=v))
    reject('mass_conservation_tamper', 'MASS_ARITHMETIC_MISMATCH', lambda c: c['handling_unit'].update(contents_gross_mass_kg=1))

    def overweight(cargo):
        cargo['unit'].update(contents_mass_kg=16, packaging_tare_mass_kg=0, gross_mass_kg=16)
        cargo['handling_unit'].update(units_per_handling_unit=1, packaging_tare_mass_kg=0, contents_gross_mass_kg=16, gross_mass_kg=16)

    reject('slot_overweight_with_balanced_ledger', 'OVERWEIGHT', overweight)
    reject('occupied_slot', 'SLOT_CAPACITY', kwargs={'occupied_units': 1})
    reject('negative_occupancy', 'INVALID_OCCUPANCY', kwargs={'occupied_units': -1})
    reject('boolean_occupancy', 'INVALID_OCCUPANCY', kwargs={'occupied_units': True})
    reject('module_overweight', 'OVERWEIGHT', kwargs={'module_mass_kg': module['max_module_payload_kg']})
    reject('missing_handler', 'HANDLER_UNAVAILABLE', kwargs={'handler_available': False})
    reject('wrong_transport', 'HANDLER_UNAVAILABLE', kwargs={'transport_tag': 'forklift_assisted'})

    stock = fixture['inputs']['initial_stock']
    validate_frozen_stock(stock, mapping_by_id, by_id)
    integrity_negatives = []

    def reject_integrity(name, expected, operation):
        try:
            operation()
        except AssertionError as error:
            assert str(error) == expected, (name, str(error))
        else:
            raise AssertionError('Malformed frozen data accepted: ' + name)
        integrity_negatives.append(dict(case_id=name, reason=expected, rejected_before_cost=True))

    changed = copy.deepcopy(mapping)
    for field in ['archetype_id', 'cargo_template_pointer']:
        changed['skus'][0][field], changed['skus'][110][field] = changed['skus'][110][field], changed['skus'][0][field]
    reject_integrity('same_counts_cross_class_SKU_swap', 'SKU_FROZEN_TEMPLATE', lambda: validate_frozen_mapping(records, changed))
    for pointer in ['/records/-1', '/records/+7', '/records/07', '/records/7extra', '/records/8', '/records/1']:
        changed = copy.deepcopy(mapping)
        changed['skus'][192]['cargo_template_pointer'] = pointer
        reason = 'TEMPLATE_POINTER' if not re.fullmatch(r'/records/(0|[1-9][0-9]*)', pointer) else 'TEMPLATE_POINTER_RANGE' if pointer == '/records/8' else 'SKU_FROZEN_TEMPLATE'
        reject_integrity('noncanonical_or_wrong_pointer_' + pointer, reason, lambda: validate_frozen_mapping(records, changed))
    changed_stock = copy.deepcopy(stock)
    changed_stock[0]['sku_id'] = 'DEMO_111'
    reject_integrity('HU_own_template_valid_but_wrong_SKU', 'HU_SKU_TEMPLATE', lambda: validate_frozen_stock(changed_stock, mapping_by_id, by_id))
    ibc_index = next(i for i, h in enumerate(stock) if h['archetype_id'] == 'IBC')
    for field, value, reason in [('quantity_units', True, 'HU_QUANTITY_TYPE'), ('quantity_units', 1.0, 'HU_QUANTITY_TYPE'), ('gross_mass_kg', float('inf'), 'HU_MASS_TYPE'), ('model_scale_factor', True, 'HU_SCALE')]:
        changed_stock = copy.deepcopy(stock)
        changed_stock[ibc_index][field] = value
        reject_integrity('HU_wrong_primitive_' + field + '_' + type(value).__name__, reason, lambda: validate_frozen_stock(changed_stock, mapping_by_id, by_id))
    changed_stock = copy.deepcopy(stock)
    changed_stock[ibc_index]['dimensions_xyz_m'][2] = True
    reject_integrity('HU_boolean_dimension_1', 'HU_DIMENSION_TYPE', lambda: validate_frozen_stock(changed_stock, mapping_by_id, by_id))

    proof_paths = ['docs/adaptive-v3/evidence/W04.1-checks.json', 'docs/adaptive-v3/evidence/W04.1-independent.json',
        'docs/adaptive-v3/evidence/W04.2.json', 'docs/adaptive-v3/evidence/W04.2-geometry-calibrations.json',
        'assets/v3/iterations/warehouse/W04.2/browser/browser-checks.json',
        'assets/v3/iterations/warehouse/W04.2/visual-review.json']
    for path in proof_paths:
        proof = read(path)
        assert proof.get('passed') is True and proof.get('engine_operation', False) is False, path
        for source, digest in proof.get('input_hashes', {}).items():
            assert sha(source) == digest, (path, source)
    runtime = read(proof_paths[0])
    assert runtime['initial_HUs'] == 530 and runtime['atomic_swap'] is True and runtime['absolute_reset'] is True
    assert len(runtime['negative_cases']) == 24 and all(n['rejected'] is True for n in runtime['negative_cases'])
    review = read(proof_paths[-1])
    assert review['reviewer'] == 'root' and review['browser_report_sha256'] == sha(proof_paths[-2])
    images = []
    for family in EXPECTED:
        name = 'initial-' + family + '.png'
        image = next(i for i in review['images'] if i['file'] == name)
        path = 'assets/v3/iterations/warehouse/W04.2/browser/' + name
        assert sha(path) == image['sha256'] and image['observation'] and image['review_method']
        images.append(dict(archetype_id=family, path=path, sha256=image['sha256'],
            review='Existing current source-bound PNG opened by root for W04.2 regression; reused exact bytes, no new render or review claim.'))

    paths = [CATALOG, SKU, STORAGE, FIXTURE, 'tools/visual/v3/storage_eligibility.py',
        'tools/visual/v3/build_storage_contract.py', 'tools/visual/v3/check_all_sku_slot_compatibility.py',
        'docs/adaptive-v3/specs/Q03.md', *proof_paths]
    return dict(task_id='Q03', passed=True, source_kind='visual_fixture', engine_operation=False,
        operational_admission=False, cost_evaluated=False,
        scope='Frozen storage design eligibility for200SKU/776slots plus current same530HU native storage evidence. Alternative candidates share capacity. No dynamic route/handling, actual job, structural certification, engine or complete visual acceptance.',
        oracle='Predeclared frozen10family pairs/8candidate counts, compared with actual C05 evaluator for every SKU and physical slot; independent Decimal geometry and stock conservation audit.',
        counts=dict(SKUs=200, archetypes=8, modules=132, slots=776, slot_pairs=155200, positive_pairs=total_positive,
            negative_pairs=155200-total_positive, blocked_reserve_pairs=37600, boundary_positives=len(boundary_positives),
            mutation_negatives=len(negatives), frozen_integrity_negatives=len(integrity_negatives), current_runtime_negatives=24, initial_HUs=530, units=12256, gross_mass_kg=9403.85,
            source_bound_reused_images=8),
        reason_counts=dict(sorted(all_reasons.items())), per_sku=rows,
        boundary_positives=boundary_positives, negative_cases=negatives, frozen_integrity_negatives=integrity_negatives, image_evidence=images,
        input_hashes={p: sha(p) for p in paths})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    report = build()
    blob = encoded(report)
    path = ROOT / REPORT
    if args.check_only:
        assert path.read_bytes() == blob, 'Q03 evidence is stale; no files were written'
    else:
        temporary = path.with_suffix('.json.tmp')
        temporary.write_bytes(blob)
        temporary.replace(path)
    print(json.dumps(dict(passed=True, check_only=args.check_only, **report['counts']), sort_keys=True))


if __name__ == '__main__':
    main()
