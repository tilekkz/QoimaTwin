"""Independent C11 transfer replay, canonical identities, paths and arithmetic."""
import copy,hashlib,json,math
from collections import defaultdict
from decimal import Decimal
from admission_policy import AdmissionPolicy,PlanningContext,ROOT,BASE
from storage_eligibility import read,sha,encoded,evaluate

p=AdmissionPolicy();inputs=read(BASE/'adaptation-input-v3.json');baseline=read(BASE/'baseline-assignment-v3.json')
skus={s['sku_id']:s for s in inputs['skus']}
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def near(a,b):assert math.isclose(a,b,abs_tol=1e-7,rel_tol=1e-12),(a,b)
def mode(aid):return 'manual_cart' if aid in ('SMALL_CARTON','STANDARD_CARTON') else 'forklift_assisted'
def signature(rows):
    fields=['handling_unit_id','lot_id','sku_id','archetype_id','quantity_units','orientation_id','model_scale_factor']
    return [{k:r[k] for k in fields} for r in sorted(rows,key=lambda r:r['handling_unit_id'])]
def state(rows):
    occupied={r['slot_id'] for r in rows.values()};assert len(occupied)==len(rows)
    masses=defaultdict(lambda:Decimal(0))
    for row in rows.values():masses[row['module_id']]+=Decimal(str(p._cargo[row['archetype_id']]['handling_unit']['gross_mass_kg']))
    return occupied,masses
def context(aid,origin,direction,occupied,masses):
    fork=mode(aid)=='forklift_assisted'
    return PlanningContext(origin,direction,('INBOUND_FORKLIFT_PAIR' if direction=='inbound' else 'OUTBOUND_FORKLIFT_PAIR') if fork else None,
        design_equipment_tags=frozenset(['forklift','approved_load_support','positive_locked_long_cradle'] if fork else ['manual_cart']),
        occupied_slot_ids=frozenset(occupied),module_masses_kg=tuple(sorted((k,float(v)) for k,v in masses.items() if v)))
def chain(route):
    graph=p._graphs[route['graph']];arcs={a['arc_id']:a for a in graph['arcs']};node=route['from_node_id'];length=0
    for ident in route['arc_ids']:
        arc=arcs[ident];assert arc['from_node_id']==node;node=arc['to_node_id'];length+=arc['length_m']
    assert node==route['to_node_id'];near(length,route['length_m']);return length
def flow_cost(row,sid,horizon):
    sku=skus[row['sku_id']];tag=mode(row['archetype_id']);speed=inputs['cost_assumptions'][tag]['speed_m_s'];total=0;legs=[]
    for direction,mix,field in [('inbound','inbound_port_mix','expected_inbound_HU_moves'),('outbound','outbound_port_mix','expected_outbound_HU_moves')]:
        for port,share in sorted(sku[mix].items()):
            verdict=p.admit(dict(sku_id=row['sku_id'],slot_id=sid,transport_tag=tag),context(row['archetype_id'],'v3:service:'+port,direction,set(),{}))
            assert verdict['planning_eligible'] and not verdict['operational_admission'];distance=chain(verdict['route'])
            moves=horizon*sku[field]/sku['stock_handling_units']*share;total+=moves*distance/speed
            legs.append(dict(port_id=port,direction=direction,expected_HU_moves=moves,route=verdict['route']))
    return total,legs
def verify(document):
    assert document['source_kind']=='synthetic_planning_fixture' and document['actual_engine_run'] is False and document['operational_admission'] is False
    assert document['staffing']==inputs['staffing'] and document['source_fingerprints']==p.fingerprints
    assert document['cost_assumptions']==inputs['cost_assumptions'] and document['allowed_differences']==inputs['allowed_differences']
    for binding in document['source_fingerprints']:assert sha(ROOT/binding['path'])==binding['sha256']
    assert sha(BASE/'baseline-input-v3.json')==inputs['baseline_input_sha256'] and sha(BASE/'baseline-assignment-v3.json')==inputs['baseline_assignment_sha256']
    horizon=document['summary']['evaluation_horizon_periods'];assert horizon in (1,2,4,8)
    expected_hash=digest(dict(frozen_inputs=inputs,evaluation_horizon_periods=horizon))
    assert document['comparison_inputs_sha256']==document['baseline_comparison_inputs_sha256']==document['adapted_comparison_inputs_sha256']==expected_hash
    original=baseline['assignments'];final=document['assignments']
    assert len(final)==len({r['handling_unit_id'] for r in final})==530
    assert signature(final)==signature(original)
    assert document['inventory_sha256']==document['baseline_inventory_sha256']==digest(signature(original))
    rows={r['handling_unit_id']:copy.deepcopy(r) for r in original};before=sum(flow_cost(r,r['slot_id'],horizon)[0] for r in rows.values());paid=0;moved=set();route_legs=0
    for index,transfer in enumerate(document['transfers'],1):
        hu=transfer['handling_unit_id'];assert hu not in moved and transfer['sequence']==index
        row=rows[hu];assert transfer['sku_id']==row['sku_id'] and transfer['archetype_id']==row['archetype_id'] and transfer['from_slot_id']==row['slot_id']
        occupied,masses=state(rows);target=p._slots[transfer['to_slot_id']];assert target['slot_id'] not in occupied
        assert target['storage_type']==skus[row['sku_id']]['home_storage_type'] and not target['reserve_only'] and not target['retrieval_blocked']
        occupied.remove(row['slot_id']);masses[row['module_id']]-=Decimal(str(p._cargo[row['archetype_id']]['handling_unit']['gross_mass_kg']))
        tag=mode(row['archetype_id']);access='cart_stop_id' if tag=='manual_cart' else 'vehicle';source=p._slots[row['slot_id']]
        loaded=p.admit(dict(sku_id=row['sku_id'],slot_id=target['slot_id'],transport_tag=tag),context(row['archetype_id'],source['access'][access],'inbound',occupied,masses))
        reverse=p.admit(dict(sku_id=row['sku_id'],slot_id=source['slot_id'],transport_tag=tag),context(row['archetype_id'],target['access'][access],'inbound',occupied,masses))
        assert loaded['planning_eligible'] and reverse['planning_eligible']
        assert transfer['loaded_route']==loaded['route'] and transfer['conservative_reverse_route']==reverse['route']
        distance=chain(loaded['route'])+chain(reverse['route']);route_legs+=2
        handling=inputs['cost_assumptions'][tag]['handling_allowance_s'];near(transfer['handling_allowance_s'],handling)
        cost=distance/inputs['cost_assumptions'][tag]['speed_m_s']+handling;near(cost,transfer['relocation_cost_s'])
        gross=flow_cost(row,source['slot_id'],horizon)[0]-flow_cost(row,target['slot_id'],horizon)[0]
        near(gross,transfer['gross_route_saving_s']);near(gross-cost,transfer['net_saving_s']);assert gross-cost>1e-8
        row.update(slot_id=target['slot_id'],module_id=target['module_id'],placement=loaded['placement']);paid+=cost;moved.add(hu)
    assert len(moved)<=inputs['maximum_transfers']
    assert {r['handling_unit_id']:r['slot_id'] for r in final}=={hu:r['slot_id'] for hu,r in rows.items()}
    occupied,masses=state(rows);after=0;final_by_id={r['handling_unit_id']:r for r in final};flow_legs=0
    for hu,row in rows.items():
        saved=final_by_id[hu];aid=row['archetype_id'];cargo=p._cargo[aid];slot=p._slots[row['slot_id']]
        assert saved['module_id']==slot['module_id'] and saved['model_scale_factor']==1 and saved['quantity_units']==cargo['handling_unit']['units_per_handling_unit']
        mass=cargo['handling_unit']['gross_mass_kg'];v=evaluate(cargo,slot,p._modules[slot['module_id']],transport_tag=mode(aid),module_mass_kg=float(masses[slot['module_id']]-Decimal(str(mass))))
        assert v['design_eligible'] and saved['placement']==v['details']['placement']
        value,legs=flow_cost(row,row['slot_id'],horizon);near(saved['planning_transport_cost_s'],value);assert saved['planning_legs']==legs
        after+=value;flow_legs+=len(legs)
    summary=document['summary'];assert sum(r['quantity_units'] for r in final)==summary['quantity_units']==12256
    assert sum(masses.values())==Decimal('9403.85') and summary['gross_mass_kg']==9403.85
    assert document['module_mass_kg']=={k:float(v) for k,v in sorted(masses.items()) if v}
    assert summary['FLEX_occupied']==0 and summary['occupied_slots']==530 and summary['relocation_count']==len(moved)
    assert summary['no_op']==(not moved)
    near(before,summary['baseline_under_same_shifted_flow_cost_s']);near(after,summary['adapted_under_same_shifted_flow_cost_s']);near(paid,summary['one_off_relocation_cost_s']);near(before-after-paid,summary['net_transport_cost_reduction_s']);assert before-after-paid>=-1e-7
    return dict(horizon_periods=horizon,HUs=530,units=12256,gross_mass_kg=9403.85,flow_legs=flow_legs,relocation_route_legs=route_legs,transfers=len(moved),net_transport_proxy_s=before-after-paid,passed=True)

def main():
    files=['adapted-assignment-v3.json']+[f'adapted-assignment-horizon{h}-v3.json' for h in (2,4,8)]
    reports=[dict(path=name,**verify(read(BASE/name))) for name in files]
    bad=copy.deepcopy(read(BASE/files[1]));bad['assignments'][0]['quantity_units']+=1
    try:verify(bad);raise RuntimeError('Tampered quantity was accepted')
    except AssertionError:pass
    bad=copy.deepcopy(read(BASE/files[1]));bad['transfers'][0]['to_slot_id']=next(r['slot_id'] for r in baseline['assignments'] if r['slot_id']!=bad['transfers'][0]['from_slot_id'])
    try:verify(bad);raise RuntimeError('Occupied destination was accepted')
    except AssertionError:pass
    from build_adapted_assignment import adapt
    normal=copy.deepcopy(inputs);normal['skus']=read(BASE/'baseline-input-v3.json')['skus']
    assert adapt(AdmissionPolicy(),normal)['summary']['no_op']
    assert adapt(AdmissionPolicy(),inputs,handling_multiplier=1e9,horizon_periods=8)['summary']['no_op']
    report=dict(task_id='C11',passed=True,source_kind='synthetic_planning_fixture',actual_engine_run=False,operational_admission=False,evaluations=reports,
        negative_checks=['unit quantity tampering rejected','occupied relocation destination rejected','normal unchanged flow returns no-op','prohibitive relocation handling cost returns no-op'],
        independent_checks=['canonical HU/SKU/lot identities and mass','every final slot/module eligibility and placement','each transfer current occupancy/mass and directed forward/reverse graph arc chain','same material flow/horizon hashes per pair','gross, one-off relocation and net arithmetic recomputed'])
    (ROOT/'docs/adaptive-v3/evidence/C11-independent.json').write_bytes(encoded(report));print(json.dumps(report))

if __name__=='__main__':main()
