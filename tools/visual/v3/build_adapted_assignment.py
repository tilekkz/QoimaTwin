"""C11 bounded analytical placement example; never an engine/planner endpoint."""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from collections import defaultdict,Counter
from decimal import Decimal
from dataclasses import replace
from pathlib import Path
from admission_policy import AdmissionPolicy,PlanningContext,ROOT,BASE
from storage_eligibility import evaluate,read,sha,encoded
from build_baseline_assignment import context_for

INPUT=BASE/'adaptation-input-v3.json'
OUT=BASE/'adapted-assignment-v3.json'
BASELINE=BASE/'baseline-assignment-v3.json'
FROZEN=BASE/'baseline-input-v3.json'

def digest(value):return hashlib.sha256(encoded(value)).hexdigest()

def material_inputs(policy):
    initial=read(FROZEN);flows=copy.deepcopy(initial['skus'])
    for row in flows:
        aid=row['archetype_id']
        if aid=='STANDARD_CARTON':row['inbound_port_mix']={'IN_N_STANDARD':.1,'IN_E_PARCEL':.9}
        if aid in ('SMALL_CARTON','STANDARD_CARTON'):row['outbound_port_mix']={'OUT_W_RETAIL':.15,'OUT_S_EXPRESS':.85}
        if aid in ('HEAVY_BOX','PALLET_LOAD','DRUM','FRAGILE_CRATE'):row['outbound_port_mix']={'OUT_W_RETAIL':.1,'OUT_E_B2B':.9}
    return dict(schema_id='qoima.adaptation-input.v3-planning',schema_version='0.1.0',
        source_kind='synthetic_planning_fixture',actual_engine_run=False,operational_admission=False,
        source_fingerprints=policy.fingerprints,baseline_input_sha256=sha(FROZEN),baseline_assignment_sha256=sha(BASELINE),
        scenario_id='N2_DECLARED_PORT_MIX_SHIFT',
        materialization='Explicit expected HU-move weights per unclocked synthetic period, not engine events/receipts or observed demand.',
        allowed_differences=['HU slot placement and the explicitly priced one-off relocation sequence'],
        fixed=['same530HU/200SKU inventory and lot/unit IDs','same physical layout, ports and graphs','same cargo dimensions/mass/orientations','same declared24person headcount; no staffing allocation/availability simulation'],
        staffing=dict(headcount=24,allocation_changes_allowed=False,availability_simulated=False),
        rule='At most8 single-HU transfers to currently free home-family slots; each HU at most once. Best positive net saving, deterministic HU/slot tie. No swaps, FLEX final occupancy, global optimum or AI claim.',
        maximum_transfers=8,
        cost_assumptions=dict(manual_cart=dict(speed_m_s=1.4,handling_allowance_s=12),forklift_assisted=dict(speed_m_s=1.8,handling_allowance_s=40)),
        cost_scope='Expected route-travel seconds proxy per planning period. Relocation charges the admitted loaded route, a separately admitted reverse route using conservative loaded envelope, and a declared handling allowance. No queues, availability, full-order duration, throughput, money or DES outcome.',
        skus=flows)

def mode(aid):return 'manual_cart' if aid in ('SMALL_CARTON','STANDARD_CARTON') else 'forklift_assisted'

def inventory(rows):
    keys=['handling_unit_id','lot_id','sku_id','archetype_id','quantity_units','orientation_id','model_scale_factor']
    return [{k:row[k] for k in keys} for row in sorted(rows,key=lambda r:r['handling_unit_id'])]

def state_of(policy,rows):
    occupied={r['slot_id'] for r in rows};assert len(occupied)==len(rows)
    masses=defaultdict(lambda:Decimal(0))
    for row in rows:masses[row['module_id']]+=Decimal(str(policy._cargo[row['archetype_id']]['handling_unit']['gross_mass_kg']))
    return occupied,masses

def without(policy,row,occupied,masses):
    left=set(occupied);left.remove(row['slot_id']);weights=dict(masses)
    weights[row['module_id']]-=Decimal(str(policy._cargo[row['archetype_id']]['handling_unit']['gross_mass_kg']))
    return left,weights

def adapt(policy,inputs,*,handling_multiplier=1,maximum_transfers=None,horizon_periods=1):
    assert horizon_periods in (1,2,4,8)
    baseline=read(BASELINE);rows=copy.deepcopy(baseline['assignments']);skus={r['sku_id']:r for r in inputs['skus']}
    normal={r['sku_id']:r for r in read(FROZEN)['skus']}
    for binding in inputs['source_fingerprints']:assert sha(ROOT/binding['path'])==binding['sha256']
    assert inputs['baseline_assignment_sha256']==sha(BASELINE) and inputs['baseline_input_sha256']==sha(FROZEN)
    assert len(skus)==200 and set(skus)==set(normal)
    for sid,row in skus.items():
        for field in ('archetype_id','lot_id','stock_handling_units','handling_unit_ids','quantity_units','expected_inbound_HU_moves','expected_outbound_HU_moves','home_storage_type'):assert row[field]==normal[sid][field],('FORBIDDEN_INPUT_CHANGE',sid,field)
        for key in ('inbound_port_mix','outbound_port_mix'):
            assert sum(Decimal(str(v)) for v in row[key].values())==1 and all(v>0 for v in row[key].values())
    cache={};rejected=Counter()
    def eligible(row,slot_id,occupied,masses):
        slot=policy._slots[slot_id]
        return evaluate(policy._cargo[row['archetype_id']],slot,policy._modules[slot['module_id']],
            transport_tag=mode(row['archetype_id']),occupied_units=int(slot_id in occupied),module_mass_kg=float(masses.get(slot['module_id'],0)))
    def score(row,slot_id):
        sku=skus[row['sku_id']];tag=mode(row['archetype_id']);speed=inputs['cost_assumptions'][tag]['speed_m_s'];legs=[];total=0
        for direction,mix,field in [('inbound','inbound_port_mix','expected_inbound_HU_moves'),('outbound','outbound_port_mix','expected_outbound_HU_moves')]:
            for port,share in sorted(sku[mix].items()):
                key=(row['archetype_id'],slot_id,port,direction)
                if key not in cache:
                    verdict=policy.admit(dict(sku_id=row['sku_id'],slot_id=slot_id,transport_tag=tag),context_for(sku,port,direction,set(),{}))
                    if not verdict['planning_eligible']:return None
                    cache[key]=verdict['route']
                route=cache[key];moves=horizon_periods*sku[field]/sku['stock_handling_units']*share
                total+=moves*route['length_m']/speed
                legs.append(dict(port_id=port,direction=direction,expected_HU_moves=moves,route=route))
        return total,legs
    def objective(rows):
        occupied,masses=state_of(policy,rows);total=0
        for row in rows:
            left,weights=without(policy,row,occupied,masses)
            assert eligible(row,row['slot_id'],left,weights)['design_eligible']
            verdict=score(row,row['slot_id']);assert verdict is not None
            total+=verdict[0]
        return total
    before=objective(rows);transfers=[];moved=set();paid=0
    changed=any(skus[sid][k]!=normal[sid][k] for sid in skus for k in ('inbound_port_mix','outbound_port_mix'))
    limit=inputs['maximum_transfers'] if maximum_transfers is None else maximum_transfers
    for _ in range(limit if changed else 0):
        occupied,masses=state_of(policy,rows);options=[]
        for row in rows:
            if row['handling_unit_id'] in moved:continue
            left,weights=without(policy,row,occupied,masses);old=score(row,row['slot_id'])[0];sku=skus[row['sku_id']];tag=mode(row['archetype_id'])
            costs=inputs['cost_assumptions'][tag];handling=costs['handling_allowance_s']*handling_multiplier
            source_slot=policy._slots[row['slot_id']];access='cart_stop_id' if tag=='manual_cart' else 'vehicle'
            for target in policy._slots.values():
                tid=target['slot_id']
                if tid in occupied or target['storage_type']!=sku['home_storage_type']:continue
                v=eligible(row,tid,left,weights)
                if not v['design_eligible']:rejected[v['reason']]+=1;continue
                # A cached route score is only read after current live capacity/mass gates.
                target_score=score(row,tid)
                if target_score is None:rejected['PORT_OR_PATH_UNAVAILABLE']+=1;continue
                gross=old-target_score[0]
                if gross<=1e-8:rejected['NO_GROSS_BENEFIT']+=1;continue
                if gross<=handling+1e-8:rejected['HANDLING_COST_EXCEEDS_GROSS']+=1;continue
                forward=context_for(sku,'IN_W_BULK','inbound',left,{k:float(v) for k,v in weights.items()})
                forward=replace(forward,origin_node_id=source_slot['access'][access])
                loaded=policy.admit(dict(sku_id=row['sku_id'],slot_id=tid,transport_tag=tag),forward)
                reverse=replace(forward,origin_node_id=target['access'][access])
                empty=policy.admit(dict(sku_id=row['sku_id'],slot_id=row['slot_id'],transport_tag=tag),reverse)
                if not loaded['planning_eligible'] or not empty['planning_eligible']:rejected['RELOCATION_PATH_UNAVAILABLE']+=1;continue
                charge=(loaded['route']['length_m']+empty['route']['length_m'])/costs['speed_m_s']+handling
                net=gross-charge
                if net>1e-8:options.append((net,row['handling_unit_id'],tid,row,v,target_score,loaded['route'],empty['route'],charge,gross))
                else:rejected['RELOCATION_COST_EXCEEDS_GROSS']+=1
        if not options:break
        net,hu,tid,row,v,target_score,forward,reverse,charge,gross=min(options,key=lambda o:(-o[0],o[1],o[2]))
        origin=row['slot_id'];old_module=row['module_id'];target=policy._slots[tid]
        row.update(slot_id=tid,module_id=target['module_id'],placement=v['details']['placement'])
        transfers.append(dict(sequence=len(transfers)+1,handling_unit_id=hu,sku_id=row['sku_id'],archetype_id=row['archetype_id'],
            from_slot_id=origin,to_slot_id=tid,from_module_id=old_module,to_module_id=target['module_id'],transport_tag=mode(row['archetype_id']),
            loaded_route=forward,conservative_reverse_route=reverse,handling_allowance_s=inputs['cost_assumptions'][mode(row['archetype_id'])]['handling_allowance_s']*handling_multiplier,
            relocation_cost_s=charge,gross_route_saving_s=gross,net_saving_s=net,operational_admission=False))
        moved.add(hu);paid+=charge
    after=objective(rows)
    for row in rows:
        row.pop('planning_score',None);row.pop('planning_legs',None)
        row['planning_transport_cost_s'],row['planning_legs']=score(row,row['slot_id'])
    assert inventory(rows)==inventory(baseline['assignments'])
    assert math.isclose(before-after-paid,sum(t['net_saving_s'] for t in transfers),abs_tol=1e-7)
    assert before-after-paid>=-1e-7
    occupied,masses=state_of(policy,rows)
    return dict(schema_id='qoima.adapted-assignment.v3-planning',schema_version='0.1.0',source_kind='synthetic_planning_fixture',actual_engine_run=False,operational_admission=False,
        comparison_inputs_sha256=digest(dict(frozen_inputs=inputs,evaluation_horizon_periods=horizon_periods)),baseline_comparison_inputs_sha256=digest(dict(frozen_inputs=inputs,evaluation_horizon_periods=horizon_periods)),adapted_comparison_inputs_sha256=digest(dict(frozen_inputs=inputs,evaluation_horizon_periods=horizon_periods)),inventory_sha256=digest(inventory(rows)),
        baseline_inventory_sha256=digest(inventory(baseline['assignments'])),source_fingerprints=policy.fingerprints,scenario_id=inputs['scenario_id'],
        allowed_differences=inputs['allowed_differences'],staffing=inputs['staffing'],rule=inputs['rule'],cost_assumptions=inputs['cost_assumptions'],cost_scope=inputs['cost_scope'],
        assignments=rows,transfers=transfers,module_mass_kg={k:float(v) for k,v in sorted(masses.items()) if v},
        summary=dict(evaluation_horizon_periods=horizon_periods,handling_units=530,SKUs=200,quantity_units=sum(r['quantity_units'] for r in rows),gross_mass_kg=float(sum(masses.values())),
            baseline_under_same_shifted_flow_cost_s=before,adapted_under_same_shifted_flow_cost_s=after,one_off_relocation_cost_s=paid,net_transport_cost_reduction_s=before-after-paid,
            relocation_count=len(transfers),occupied_slots=len(occupied),FLEX_occupied=sum(policy._slots[s]['storage_type']=='FLEX' for s in occupied),
            no_op=not transfers,flow_mix_changed=changed),rejections=dict(sorted(rejected.items())),
        limitations=['Bounded single-transfer analytical example, not a global optimization or backend planner','Weighted travel-time proxy and explicit synthetic handling allowance, not real throughput/duration/financial gain','No real actors/traffic/reservations or M/P physical action admission','Visual_complete and backend_integration_complete remain false'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze-inputs',action='store_true');parser.add_argument('--check-only',action='store_true');parser.add_argument('--horizon',type=int,choices=[1,2,4,8],default=1);args=parser.parse_args()
    policy=AdmissionPolicy();inputs=material_inputs(policy)
    if args.freeze_inputs:
        if INPUT.exists():assert INPUT.read_bytes()==encoded(inputs),'Refuse changing frozen comparison inputs'
        else:INPUT.write_bytes(encoded(inputs))
        print(json.dumps(dict(frozen=True,input_sha256=sha(INPUT))));return
    assert INPUT.read_bytes()==encoded(inputs),'Comparison input/source drift'
    inputs=read(INPUT)
    evaluation=dict(schema_id='qoima.adaptation-evaluation.v3-planning',frozen_inputs_sha256=sha(INPUT),horizons_periods=[1,2,4,8],default_horizon_periods=1,meaning='Sensitivity cases repeat the SAME frozen expected flow profile for both baseline/adapted. A period has no measured hours or DES schedule; longer horizon is an explicit assumption, not a tuned inventory or promised gain.')
    evaluation_path=BASE/'adaptation-evaluation-v3.json'
    if evaluation_path.exists():assert evaluation_path.read_bytes()==encoded(evaluation),'Evaluation assumptions changed'
    else:evaluation_path.write_bytes(encoded(evaluation))
    document=adapt(policy,inputs,horizon_periods=args.horizon)
    output=OUT if args.horizon==1 else BASE/f'adapted-assignment-horizon{args.horizon}-v3.json'
    if args.check_only:assert output.read_bytes()==encoded(document),'Saved adapted proposal differs'
    else:
        output.write_bytes(encoded(document));(ROOT/f'docs/adaptive-v3/evidence/C11-builder-horizon{args.horizon}.json').write_bytes(encoded(dict(task_id='C11',status='VERIFY',artifact_sha256=sha(output),builder_sha256=sha(Path(__file__)),summary=document['summary'])))
    print(json.dumps(document['summary']))

if __name__=='__main__':main()
