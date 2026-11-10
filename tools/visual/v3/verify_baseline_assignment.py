"""Independent C10 artifact checks against canonical templates and live C09 gates."""
from collections import defaultdict
from decimal import Decimal
import json,math
from pathlib import Path
from admission_policy import AdmissionPolicy,PlanningContext,ROOT,BASE
from storage_eligibility import read,sha,encoded

p=AdmissionPolicy();f=read(BASE/'baseline-input-v3.json');b=read(BASE/'baseline-assignment-v3.json')
assert b['baseline_input']['sha256']==sha(BASE/'baseline-input-v3.json')
for binding in f['source_fingerprints']+b['source_fingerprints']:assert sha(ROOT/binding['path'])==binding['sha256']
skus={r['sku_id']:r for r in f['skus']};expected={h:r for r in f['skus'] for h in r['handling_unit_ids']}
rows={r['handling_unit_id']:r for r in b['assignments']}
assert len(rows)==len(b['assignments'])==len(expected)==530 and set(rows)==set(expected)
assert len({r['sku_id'] for r in rows.values()})==200
assert len({r['slot_id'] for r in rows.values()})==530
occupied=set();masses=defaultdict(lambda:Decimal(0));total_units=0;total_mass=Decimal(0);legs_checked=0
def contexts(sku,occupied,masses):
    fork=sku['archetype_id'] not in ['SMALL_CARTON','STANDARD_CARTON']
    tags=frozenset(['forklift','approved_load_support','positive_locked_long_cradle'] if fork else ['manual_cart'])
    for direction,key,moves in [('inbound','inbound_port_mix','expected_inbound_HU_moves'),('outbound','outbound_port_mix','expected_outbound_HU_moves')]:
        for port,share in sku[key].items():
            ctx=PlanningContext('v3:service:'+port,direction,
                ('INBOUND_FORKLIFT_PAIR' if direction=='inbound' else 'OUTBOUND_FORKLIFT_PAIR') if fork else None,
                design_equipment_tags=tags,occupied_slot_ids=frozenset(occupied),
                module_masses_kg=tuple((k,float(v)) for k,v in masses.items() if v))
            yield port,direction,sku[moves]/sku['stock_handling_units']*share,ctx
for hu_id,row in rows.items():
    sku=expected[hu_id];aid=p._skus[sku['sku_id']]['archetype_id'];cargo=p._cargo[aid]
    slot=p._slots[row['slot_id']];module=p._modules[slot['module_id']]
    assert row['sku_id']==sku['sku_id'] and row['lot_id']==sku['lot_id'] and row['archetype_id']==aid
    assert row['quantity_units']==cargo['handling_unit']['units_per_handling_unit']
    assert row['model_scale_factor']==1 and row['orientation_id']=='upright_xyz'
    assert not slot['retrieval_blocked'] and not slot['reserve_only'] and slot['storage_type']!='FLEX'
    assert slot['storage_type']==sku['home_storage_type'] and row['module_id']==slot['module_id']
    tag='manual_cart' if aid in ['SMALL_CARTON','STANDARD_CARTON'] else 'forklift_assisted'
    request=dict(sku_id=sku['sku_id'],slot_id=slot['slot_id'],transport_tag=tag)
    actual_legs={(x['port_id'],x['direction']):x for x in row['planning_legs']};score=0
    expected_leg_count=len(sku['inbound_port_mix'])+len(sku['outbound_port_mix'])
    assert len(actual_legs)==len(row['planning_legs'])==expected_leg_count
    for port,direction,moves,ctx in contexts(sku,occupied,masses):
        verdict=p.admit(request,ctx);assert verdict['planning_eligible'] and not verdict['operational_admission'],(hu_id,verdict)
        leg=actual_legs[(port,direction)]
        assert math.isclose(leg['route_length_m'],verdict['route']['length_m'],abs_tol=1e-9)
        assert math.isclose(leg['expected_HU_moves'],moves,abs_tol=1e-12)
        assert row['placement']==verdict['placement']
        score+=moves*verdict['route']['length_m'];legs_checked+=1
    assert math.isclose(row['planning_score'],score,abs_tol=1e-8)
    occupied.add(slot['slot_id']);mass=Decimal(str(cargo['handling_unit']['gross_mass_kg']))
    masses[slot['module_id']]+=mass;assert masses[slot['module_id']]<=Decimal(str(module['max_module_payload_kg']))
    total_mass+=mass;total_units+=row['quantity_units']
assert total_units==12256 and total_mass==Decimal('9403.85')
assert {k:float(v) for k,v in masses.items() if v}==b['module_mass_kg']
assert b['summary']['quantity_units']==total_units and b['summary']['gross_mass_kg']==float(total_mass)
# Reconstruct four independent greedy choices, including beginning and last HU.
jobs=[]
for sku in f['skus']:
    for ordinal,hu in enumerate(sku['handling_unit_ids'],1):jobs.append(((sku['expected_inbound_HU_moves']+sku['expected_outbound_HU_moves'])/sku['stock_handling_units'],sku['sku_id'],ordinal,hu,sku))
jobs.sort(key=lambda x:(-x[0],x[1],x[2]));occupied=set();masses=defaultdict(lambda:Decimal(0));samples=[]
for index,(_,sku_id,ordinal,hu_id,sku) in enumerate(jobs):
    if index in [0,100,300,529]:
        options=[];aid=sku['archetype_id'];tag='manual_cart' if aid in ['SMALL_CARTON','STANDARD_CARTON'] else 'forklift_assisted'
        for slot in p._slots.values():
            if slot['storage_type']!=sku['home_storage_type']:continue
            cost=0;valid=True
            for port,direction,moves,ctx in contexts(sku,occupied,masses):
                v=p.admit(dict(sku_id=sku_id,slot_id=slot['slot_id'],transport_tag=tag),ctx)
                if not v['planning_eligible']:valid=False;break
                cost+=moves*v['route']['length_m']
            if valid:options.append((cost,slot['slot_id']))
        best=min(options);assert rows[hu_id]['slot_id']==best[1] and math.isclose(rows[hu_id]['planning_score'],best[0],abs_tol=1e-8)
        samples.append(dict(job_index=index,handling_unit_id=hu_id,candidate_count=len(options),chosen_slot=best[1],score=best[0]))
    row=rows[hu_id];occupied.add(row['slot_id']);masses[row['module_id']]+=Decimal(str(p._cargo[row['archetype_id']]['handling_unit']['gross_mass_kg']))
report=dict(passed=True,source_kind='synthetic_planning_fixture',operational_admission=False,
    HUs_checked=530,SKUs_checked=200,legs_checked=legs_checked,quantity_units=total_units,gross_mass_kg=float(total_mass),
    reserved_FLEX_initially_empty=True,blocked_reserve_assignments=0,unique_HU_and_slot_ids=True,
    independent_greedy_samples=samples,artifact_sha256=sha(BASE/'baseline-assignment-v3.json'))
(ROOT/'docs/adaptive-v3/evidence/C10-independent.json').write_bytes(encoded(report));print(json.dumps({k:v for k,v in report.items() if k!='independent_greedy_samples'}))
