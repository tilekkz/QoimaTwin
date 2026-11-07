from pathlib import Path
import sys,json,math,hashlib,copy
from dataclasses import replace
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'tools/visual/v3'))
from admission_policy import AdmissionPolicy,PlanningContext
p=AdmissionPolicy();artifact=json.loads((root/'docs/v3/contract-proposals/admission-policy-v3.json').read_text(encoding='utf-8'))
paths=[];rejects=[]
for case in artifact['checks']['positive_cases']:
    aid=case['archetype_id'];request=case['request'];fork=aid not in ['SMALL_CARTON','STANDARD_CARTON']
    tags=frozenset(['forklift','approved_load_support','positive_locked_long_cradle'] if fork else ['manual_cart'])
    for direction in ['inbound','outbound']:
        origin='v3:service:'+('IN_W_BULK' if fork else 'IN_E_PARCEL') if direction=='inbound' else 'v3:service:'+('OUT_E_B2B' if fork else 'OUT_S_EXPRESS')
        ctx=PlanningContext(origin,direction,('INBOUND_FORKLIFT_PAIR' if direction=='inbound' else 'OUTBOUND_FORKLIFT_PAIR') if fork else None,design_equipment_tags=tags)
        calls=[];r=p.admit(request,ctx,lambda f:calls.append(f) or f['route_length_m'])
        assert r['planning_eligible'] and len(calls)==1 and not r['operational_admission'],(aid,direction,r)
        route=r['route'];graph=p._graphs[route['graph']];arcs={a['arc_id']:a for a in graph['arcs']}
        node=route['from_node_id'];length=0
        for arc_id in route['arc_ids']:
            a=arcs[arc_id];assert a['from_node_id']==node;node=a['to_node_id'];length+=a['length_m']
            if fork:
                assert aid in a['allowed_cargo_archetype_ids'] and ctx.equipment_pair_ref in a['equipment_pair_refs']
                assert set(a['allowed_geometry_profile_ids']) & {p._loads[aid]['main_geometry_profile_id'],p._loads[aid]['local_geometry_profile_id']}
            else:assert 'manual_cart' in a['allowed_modes']
        assert node==route['to_node_id'] and math.isclose(length,route['length_m'],abs_tol=1e-9)
        assert math.isclose(r['cost'],length,abs_tol=1e-9)
        assert r['decision_trace'].index('all_hard_gates_passed')<r['decision_trace'].index('route_and_placement_score')
        paths.append(dict(archetype_id=aid,direction=direction,arcs=len(route['arc_ids']),length_m=length))
        # A caller cannot mutate canonical templates or a cached path via a result.
        expected_dimensions=list(r['canonical']['HU_dimensions_xyz_m'])
        expected_ids=list(r['route']['arc_ids'])
        r['canonical']['HU_dimensions_xyz_m'][0]=.001;r['route']['arc_ids'].clear()
        fresh=p.admit(request,ctx)
        assert fresh['canonical']['HU_dimensions_xyz_m']==expected_dimensions
        assert fresh['route']['arc_ids']==expected_ids
    # A failing gate must not execute even the weighted route calculation.
    ctx=PlanningContext('v3:service:IN_W_BULK' if fork else 'v3:service:IN_E_PARCEL',equipment_pair_ref='INBOUND_FORKLIFT_PAIR' if fork else None,design_equipment_tags=tags)
    previous=p._shortest_route
    def forbidden(*args,**kwargs):raise AssertionError('Rejected candidate reached weighted route or score')
    p._shortest_route=forbidden
    cases=[(dict(request,HU_mass_kg=.01),ctx,'CARGO_OVERRIDE_FORBIDDEN'),
        (request,replace(ctx,handler_design_available=False),'HANDLER_UNAVAILABLE'),
        (dict(request,sku_id=[]),ctx,'INVALID_REQUEST'),
        (request,replace(ctx,origin_node_id=[]),'INVALID_CONTEXT')]
    if fork and aid!='PALLET_LOAD':cases.append((request,replace(ctx,origin_node_id='v3:service:IN_N_STANDARD'),'PORT_CARGO_FORBIDDEN'))
    for req,context,reason in cases:
        r=p.admit(req,context,forbidden);assert r['reason']==reason and not r['cost_evaluated'],r
        rejects.append(dict(archetype_id=aid,reason=reason,weighted_route_calls=0,score_calls=0))
    p._shortest_route=previous
report=dict(passed=True,actual_paths=paths,paths_verified=len(paths),returned_template_and_path_isolation_cases=len(paths),negative_weighted_route_and_callback_guards=rejects,negative_guards=len(rejects),source_fingerprints=p.fingerprints)
dest=root/'docs/adaptive-v3/evidence/C09-independent.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(passed=True,actual_paths=len(paths),negative_guards=len(rejects))))
