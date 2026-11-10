"""Current Q03 numeric storage component; no historical visual-proof freshness relaxation.

Runs the frozen independent family oracle against actual C05 for every SKU/slot,
Decimal budgets and43 mutation/integrity negatives. Full native/browser Q03
acceptance remains separate. No source catalog/model/action or old receipt edits.
"""
import argparse
from collections import Counter
import copy
import hashlib
import math
import re
from pathlib import Path
from check_all_sku_slot_compatibility import (
    ROOT, CATALOG, SKU, STORAGE, FIXTURE, EXPECTED, read, sha, dec, encoded,
    validate_frozen_mapping, validate_frozen_stock,
)
from storage_eligibility import evaluate
REPORT='docs/adaptive-v3/evidence/Q03-current-numeric-20261110.json'

def build_current_numeric_report():
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
    assert Counter((s['archetype_id'] for s in mapping['skus'])) == Counter({k: v[2] for k, v in EXPECTED.items()})
    expected_orientation = {'upright_only': True, 'permitted_orientations': [{'local_axes_in_destination': ['+X', '+Y', '+Z'], 'orientation_id': 'upright_xyz'}], 'slot_orientation_mappings': [{'cargo_orientation_id': 'upright_xyz', 'slot_orientation_id': 'upright_xyz_in_module'}]}
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
            expected = slot['storage_type'] in families and (not (slot['reserve_only'] or slot['retrieval_blocked']))
            verdict = evaluate(cargo, slot, modules[slot['module_id']])
            assert verdict['design_eligible'] is expected, (sku['sku_id'], slot['slot_id'], verdict)
            assert verdict['cost_evaluated'] is False and verdict['operational_admission'] is False
            reasons[verdict['reason']] += 1
            if expected:
                accepted.append(slot['slot_id'])
                assert all((dec(d) + 2 * dec(slot['clearance_each_side_m']) <= dec(u) for d, u in zip(cargo['handling_unit']['dimensions_xyz_m'], slot['usable_dimensions_xyz_m'])))
                assert dec(cargo['handling_unit']['gross_mass_kg']) <= dec(slot['max_payload_kg'])
                assert verdict['details']['placement']['support_gap_m'] == 0
        assert len(accepted) == expected_count, sku['sku_id']
        total_positive += len(accepted)
        all_reasons.update(reasons)
        rows.append(dict(sku_id=sku['sku_id'], archetype_id=sku['archetype_id'], accepted_slots=len(accepted), accepted_slot_ids_sha256=hashlib.sha256(encoded(accepted)).hexdigest(), reason_counts=dict(sorted(reasons.items()))))
    assert total_positive == 58704 and sum(all_reasons.values()) == 155200
    assert all_reasons['HEIGHT_ACCESS_UNAVAILABLE'] == 200 * 188
    small = by_id['SMALL_CARTON']
    slot = next((s for s in slots if s['storage_type'] == 'SMALL' and (not s['retrieval_blocked']) and (not s['reserve_only'])))
    module = modules[slot['module_id']]
    negatives = []
    boundary_positives = []

    def reject(name, reason, change=None, kwargs=None):
        cargo = copy.deepcopy(small)
        if change:
            change(cargo)
        verdict = evaluate(cargo, slot, module, **kwargs or {})
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
        reject(f'axis_{axis}_over_budget_1e-10m', 'DIMENSION_MISMATCH', lambda c, a=axis, value=limit: c['handling_unit']['dimensions_xyz_m'].__setitem__(a, value + 1e-10))
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
        changed['skus'][0][field], changed['skus'][110][field] = (changed['skus'][110][field], changed['skus'][0][field])
    reject_integrity('same_counts_cross_class_SKU_swap', 'SKU_FROZEN_TEMPLATE', lambda: validate_frozen_mapping(records, changed))
    for pointer in ['/records/-1', '/records/+7', '/records/07', '/records/7extra', '/records/8', '/records/1']:
        changed = copy.deepcopy(mapping)
        changed['skus'][192]['cargo_template_pointer'] = pointer
        reason = 'TEMPLATE_POINTER' if not re.fullmatch('/records/(0|[1-9][0-9]*)', pointer) else 'TEMPLATE_POINTER_RANGE' if pointer == '/records/8' else 'SKU_FROZEN_TEMPLATE'
        reject_integrity('noncanonical_or_wrong_pointer_' + pointer, reason, lambda: validate_frozen_mapping(records, changed))
    changed_stock = copy.deepcopy(stock)
    changed_stock[0]['sku_id'] = 'DEMO_111'
    reject_integrity('HU_own_template_valid_but_wrong_SKU', 'HU_SKU_TEMPLATE', lambda: validate_frozen_stock(changed_stock, mapping_by_id, by_id))
    ibc_index = next((i for i, h in enumerate(stock) if h['archetype_id'] == 'IBC'))
    for field, value, reason in [('quantity_units', True, 'HU_QUANTITY_TYPE'), ('quantity_units', 1.0, 'HU_QUANTITY_TYPE'), ('gross_mass_kg', float('inf'), 'HU_MASS_TYPE'), ('model_scale_factor', True, 'HU_SCALE')]:
        changed_stock = copy.deepcopy(stock)
        changed_stock[ibc_index][field] = value
        reject_integrity('HU_wrong_primitive_' + field + '_' + type(value).__name__, reason, lambda: validate_frozen_stock(changed_stock, mapping_by_id, by_id))
    changed_stock = copy.deepcopy(stock)
    changed_stock[ibc_index]['dimensions_xyz_m'][2] = True
    reject_integrity('HU_boolean_dimension_1', 'HU_DIMENSION_TYPE', lambda: validate_frozen_stock(changed_stock, mapping_by_id, by_id))
    paths = [CATALOG, SKU, STORAGE, FIXTURE, 'tools/visual/v3/storage_eligibility.py', 'tools/visual/v3/build_storage_contract.py', 'tools/visual/v3/check_all_sku_slot_compatibility.py', 'tools/visual/v3/check_current_sku_slot_compatibility.py']
    return dict(schema_id='qoima.q03.current-numeric-component.v1', task_id='Q03-current-numeric-component', passed=True, source_kind='visual_fixture', engine_operation=False, operational_admission=False, cost_evaluated=False, full_Q03_visual_acceptance=False, current_browser_evidence_claimed=False, historical_receipts_modified=False, scope='Current155200actualC05 SKU-slot verdicts andindependentDecimal budgets/conservation/negativecontrols. Currentnative/browser acceptance is separate; archivedW04proofs are neverrepinned orpromotedbythisnumericgate.', counts=dict(SKUs=len(mapping['skus']), archetypes=len(records), modules=len(modules), slots=len(slots), slot_pairs=sum(all_reasons.values()), positive_pairs=total_positive, negative_pairs=sum(all_reasons.values()) - total_positive, boundary_positives=len(boundary_positives), mutation_negatives=len(negatives), frozen_integrity_negatives=len(integrity_negatives), initial_HUs=len(stock), units=sum((h['quantity_units'] for h in stock)), gross_mass_kg=str(sum((dec(h['gross_mass_kg']) for h in stock))), current_runtime_negatives=0, source_bound_reused_images=0), reason_counts=dict(sorted(all_reasons.items())), per_sku=rows, boundary_positives=boundary_positives, negative_cases=negatives, frozen_integrity_negatives=integrity_negatives, input_hashes={p: sha(p) for p in paths})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--output',type=Path,help='Explicit new component receipt; default is the canonical current numeric receipt.')
    args=parser.parse_args()
    report=build_current_numeric_report()
    blob=encoded(report)
    target=args.output.resolve() if args.output else ROOT/REPORT
    if args.check_only:
        assert target.read_bytes()==blob,'Current numeric receipt differs; no files written'
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(blob)
    print(__import__('json').dumps(dict(passed=True,full_Q03_visual_acceptance=False,check_only=args.check_only,**report['counts']),sort_keys=True))


if __name__=='__main__':
    main()
