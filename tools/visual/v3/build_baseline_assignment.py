"""C10: input freeze first, then a compatible deterministic normal baseline."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
import json
from pathlib import Path
from admission_policy import AdmissionPolicy,PlanningContext,BASE,ROOT
from storage_eligibility import evaluate,read,sha,encoded

FROZEN=BASE/'baseline-input-v3.json'
OUT=BASE/'baseline-assignment-v3.json'
# Planning assumptions, not UCI observations or materialized engine events.
MIX={
 'SMALL_CARTON':({'IN_E_PARCEL':1.0},{'OUT_W_RETAIL':.55,'OUT_S_EXPRESS':.45}),
 'STANDARD_CARTON':({'IN_N_STANDARD':.70,'IN_E_PARCEL':.30},{'OUT_W_RETAIL':.55,'OUT_S_EXPRESS':.45}),
 'HEAVY_BOX':({'IN_W_BULK':1.0},{'OUT_W_RETAIL':.60,'OUT_E_B2B':.40}),
 'PALLET_LOAD':({'IN_W_BULK':.50,'IN_N_STANDARD':.50},{'OUT_W_RETAIL':.50,'OUT_E_B2B':.50}),
 'IBC':({'IN_W_BULK':1.0},{'OUT_E_B2B':1.0}),
 'LONG_BUNDLE':({'IN_W_BULK':1.0},{'OUT_E_B2B':1.0}),
 'DRUM':({'IN_W_BULK':1.0},{'OUT_W_RETAIL':.60,'OUT_E_B2B':.40}),
 'FRAGILE_CRATE':({'IN_W_BULK':1.0},{'OUT_W_RETAIL':.70,'OUT_E_B2B':.30})}
HOME={'SMALL_CARTON':'SMALL','STANDARD_CARTON':'STANDARD','HEAVY_BOX':'HEAVY',
    'PALLET_LOAD':'HEAVY','IBC':'HEAVY','LONG_BUNDLE':'LONG','DRUM':'HEAVY','FRAGILE_CRATE':'STANDARD'}


def input_document(policy):
    rows=[]
    for index,sku in enumerate(policy._skus.values()):
        aid=sku['archetype_id'];count=4 if aid=='SMALL_CARTON' else 1
        hu=policy._cargo[aid]['handling_unit'];inbound,outbound=MIX[aid]
        assert sum(Decimal(str(v)) for v in inbound.values())==1
        assert sum(Decimal(str(v)) for v in outbound.values())==1
        rows.append(dict(sku_id=sku['sku_id'],archetype_id=aid,
            lot_id='v3:lot:initial:'+sku['sku_id'],stock_handling_units=count,
            handling_unit_ids=[f'v3:HU:initial:{sku["sku_id"]}:{n:02d}' for n in range(1,count+1)],
            quantity_units=count*hu['units_per_handling_unit'],
            expected_inbound_HU_moves=[16,8,4,2][index%4],
            expected_outbound_HU_moves=[16,8,4,2][index%4],
            inbound_port_mix=inbound,outbound_port_mix=outbound,home_storage_type=HOME[aid]))
    assert len(rows)==200 and sum(r['stock_handling_units'] for r in rows)==530
    return dict(schema_id='qoima.baseline-input.v3-planning',schema_version='0.1.0',source_kind='synthetic_design',
        operational_admission=False,source_fingerprints=policy.fingerprints,
        freeze_scope='Load and normal flow weights fixed before baseline/adapted comparison; not learned UCI, measured arrivals or engine events.',
        initial_loading_rule='4 unchanged C02 HUs for each110 SMALL SKUs;1 for other90. 530HUs,200SKUs. No legacy2000unit quantities.',
        expected_move_unit='Expected HU moves per synthetic unclocked planning period; equal inbound/outbound total perSKU, not units/events/receipts on a timeline.',
        turnover_rule='Sorted canonical SKU ordinal cycles16,8,4,2 before layout scoring. Expected SKU HU moves split equally across its stockHUs.',
        buffer_policy='All8 FLEX slots initially free for later compatible transfer buffering. No fake occupied cargo or reserve retrieval.',
        baseline_rule='Home families; descending expected visits perHU, minimum compatible weighted directed inbound+outbound distance; tie slot_id.',
        score_unit='weighted_route_metres_per_planning_period; no full-order duration, throughput or money',skus=rows)


def context_for(row,port,direction,occupied,masses):
    fork=row['archetype_id'] not in ['SMALL_CARTON','STANDARD_CARTON']
    return PlanningContext('v3:service:'+port,direction,
        ('INBOUND_FORKLIFT_PAIR' if direction=='inbound' else 'OUTBOUND_FORKLIFT_PAIR') if fork else None,
        design_equipment_tags=frozenset(['forklift','approved_load_support','positive_locked_long_cradle'] if fork else ['manual_cart']),
        occupied_slot_ids=frozenset(occupied),module_masses_kg=tuple(sorted(masses.items())))


def assignment(policy,frozen):
    occupied=set();masses=defaultdict(lambda:Decimal(0));rows=[];rejections=Counter()
    jobs=[]
    for sku in frozen['skus']:
        for ordinal,hu_id in enumerate(sku['handling_unit_ids'],1):
            weight=(sku['expected_inbound_HU_moves']+sku['expected_outbound_HU_moves'])/sku['stock_handling_units']
            jobs.append((weight,sku['sku_id'],ordinal,hu_id,sku))
    jobs.sort(key=lambda x:(-x[0],x[1],x[2]))
    for job_index,(_,sku_id,ordinal,hu_id,sku) in enumerate(jobs):
        aid=sku['archetype_id'];cargo=policy._cargo[aid]
        tag='manual_cart' if aid in ['SMALL_CARTON','STANDARD_CARTON'] else 'forklift_assisted'
        candidates=[]
        for slot in policy._slots.values():
            if slot['storage_type']!=sku['home_storage_type']:continue
            request=dict(sku_id=sku_id,slot_id=slot['slot_id'],transport_tag=tag)
            # Cheap live capacity gate before any route/placement cost.
            v=evaluate(cargo,slot,policy._modules[slot['module_id']],transport_tag=tag,
                occupied_units=int(slot['slot_id'] in occupied),module_mass_kg=float(masses[slot['module_id']]))
            if not v['design_eligible']:rejections[v['reason']]+=1;continue
            cost=0.0;legs=[];valid=True
            mass_snapshot={k:float(v) for k,v in masses.items() if v}
            for direction,mix,move_field in [('inbound',sku['inbound_port_mix'],'expected_inbound_HU_moves'),
                ('outbound',sku['outbound_port_mix'],'expected_outbound_HU_moves')]:
                for port,share in mix.items():
                    ctx=context_for(sku,port,direction,occupied,mass_snapshot)
                    verdict=policy.admit(request,ctx)
                    if not verdict['planning_eligible']:
                        rejections[verdict['reason']]+=1;valid=False;break
                    expected_moves=sku[move_field]/sku['stock_handling_units']*share
                    cost+=expected_moves*verdict['route']['length_m']
                    legs.append(dict(port_id=port,direction=direction,expected_HU_moves=expected_moves,
                        route_length_m=verdict['route']['length_m'],graph=verdict['route']['graph']))
                if not valid:break
            if valid:candidates.append((cost,slot['slot_id'],v['details']['placement'],legs))
        assert candidates,('NO_BASELINE_CAPACITY',sku_id)
        cost,slot_id,placement,legs=min(candidates,key=lambda x:(x[0],x[1]));slot=policy._slots[slot_id]
        occupied.add(slot_id);masses[slot['module_id']]+=Decimal(str(cargo['handling_unit']['gross_mass_kg']))
        rows.append(dict(handling_unit_id=hu_id,lot_id=sku['lot_id'],sku_id=sku_id,archetype_id=aid,
            quantity_units=cargo['handling_unit']['units_per_handling_unit'],slot_id=slot_id,
            module_id=slot['module_id'],orientation_id='upright_xyz',model_scale_factor=1,
            placement=placement,planning_score=cost,planning_legs=legs,operational_admission=False))
        if (job_index+1)%100==0:print(json.dumps(dict(assigned=job_index+1,total=len(jobs))),flush=True)
    rows.sort(key=lambda r:r['handling_unit_id'])
    per_type=Counter(policy._slots[r['slot_id']]['storage_type'] for r in rows)
    active=sum(not s['retrieval_blocked'] and not s['reserve_only'] for s in policy._slots.values())
    mass=sum(Decimal(str(policy._cargo[r['archetype_id']]['handling_unit']['gross_mass_kg'])) for r in rows)
    summary=dict(SKU_count=len({r['sku_id'] for r in rows}),handling_units=len(rows),occupied_slots=len(occupied),
        quantity_units=sum(r['quantity_units'] for r in rows),gross_mass_kg=float(mass),
        physical_slots=len(policy._slots),active_geometric_slots=active,blocked_reserve_slots=len(policy._slots)-active,
        free_active_slots=active-len(occupied),free_initial_FLEX_slots=8,occupied_by_storage_type=dict(per_type),
        weighted_route_metres=sum(r['planning_score'] for r in rows))
    assert summary['SKU_count']==200 and summary['handling_units']==530 and summary['quantity_units']==12256
    assert summary['gross_mass_kg']==9403.85 and summary['free_active_slots']==58
    return dict(schema_id='qoima.baseline-assignment.v3-planning',schema_version='0.1.0',source_kind='synthetic_design',
        operational_admission=False,actual_engine_run=False,baseline_input=dict(path=FROZEN.relative_to(ROOT).as_posix(),sha256=sha(FROZEN)),
        source_fingerprints=policy.fingerprints,rule=frozen['baseline_rule'],score_unit=frozen['score_unit'],
        initial_inventory_frozen_before_comparison=True,summary=summary,assignments=rows,
        module_mass_kg={k:float(v) for k,v in sorted(masses.items()) if v},candidate_rejection_counts=dict(rejections),
        limitations=['Static planning baseline; actual M/P support/actions/resources/DES gates remain',
            'HU occupancy does not close the open4.0123% floor-footprint final composition finding',
            'No intentionally bad/random baseline, adapted result or AI/financial uplift claimed'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze-inputs',action='store_true');parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    policy=AdmissionPolicy();inputs=input_document(policy)
    if args.freeze_inputs:
        if FROZEN.exists():assert FROZEN.read_bytes()==encoded(inputs),'Refuse silently changing frozen initial stock/normal flow'
        else:FROZEN.write_bytes(encoded(inputs))
        print(json.dumps(dict(frozen=True,sha256=sha(FROZEN),SKUs=200,HUs=530,assignments_created=False)));return
    assert FROZEN.exists(),'Freeze initial load/normal flow before assignment'
    assert FROZEN.read_bytes()==encoded(inputs),'Initial sources/stock/flows changed after freeze'
    document=assignment(policy,read(FROZEN))
    if args.check_only:assert OUT.read_bytes()==encoded(document),'Saved baseline differs from frozen inputs/deterministic rule'
    else:
        OUT.write_bytes(encoded(document))
        e=dict(task_id='C10',owner='root',status='VERIFY',artifact=dict(path=OUT.relative_to(ROOT).as_posix(),sha256=sha(OUT),bytes=OUT.stat().st_size),
            input_freeze=dict(path=FROZEN.relative_to(ROOT).as_posix(),sha256=sha(FROZEN)),builder_sha256=sha(Path(__file__)),summary=document['summary'])
        (ROOT/'docs/adaptive-v3/evidence/C10.json').write_bytes(encoded(e))
    print(json.dumps(dict(passed=True,**document['summary'])))


if __name__=='__main__':main()
