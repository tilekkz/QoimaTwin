"""C09 planning admission. Hard compatibility and reachability precede scoring.

Never grants execution admission or invents actual M/P contact/lock evidence.
Candidates identify immutable C03/C02 templates; their dimensions and mass are
not writable request parameters. Only a successfully gated candidate can reach
the shortest-route calculation and the caller's placement-cost callback.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import copy
from dataclasses import dataclass, replace
import heapq
import json
import math
from pathlib import Path

from storage_eligibility import evaluate, read, sha, encoded, valid_number
from build_vehicle_handling import arc_reason, rated_mass_eligible

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'docs/v3/contract-proposals'
INPUTS=[BASE/n for n in ['cargo-catalog-v3.json','sku-catalog-v3.json',
    'storage-slots-v3.json','layout-links-v3.json','vehicle-handling-v3.json',
    'port-resource-policy-v3.json']]
OUT=BASE/'admission-policy-v3.json'


@dataclass(frozen=True)
class PlanningContext:
    """Engine-owned design snapshot; not a runtime reservation/availability claim."""
    origin_node_id: str
    direction: str = 'inbound'
    equipment_pair_ref: str | None = None
    handler_design_available: bool = True
    design_equipment_tags: frozenset[str] = frozenset()
    occupied_slot_ids: frozenset[str] = frozenset()
    module_masses_kg: tuple[tuple[str,float], ...] = ()
    unavailable_arc_ids: frozenset[str] = frozenset()


def distance_score(features):
    return features['route_length_m']


class AdmissionPolicy:
    def __init__(self):
        catalog,sku,storage,links,vehicle,resources=[read(p) for p in INPUTS]
        self.fingerprints=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in INPUTS]
        self._cargo={r['archetype_id']:r for r in catalog['records']}
        self._skus={r['sku_id']:r for r in sku['skus']}
        self._slots={r['slot_id']:r for r in storage['slots']}
        self._modules={r['module_id']:r for r in storage['modules']}
        self._graphs={k:links[k+'_graph'] for k in ['walk','vehicle']}
        self._nodes={k:{n['node_id']:n for n in g['nodes']} for k,g in self._graphs.items()}
        self._vehicle=vehicle
        self._loads={r['archetype_id']:r for r in vehicle['loads']}
        self._pairs={r['pair_id']:r for r in resources['forklift_pairs']}
        self._ports={r['port_id']:r for r in vehicle['ports']}
        self._route_cache={}
        self._reachability_cache={}
        self._shortest_cache={}
        for index,row in enumerate(catalog['records']):
            for entry in sku['skus']:
                if entry['archetype_id']==row['archetype_id']:
                    assert entry['cargo_template_pointer']==f'/records/{index}'
                    assert entry['model_scale_factor']==1
        for graph in self._graphs.values():
            ids={n['node_id'] for n in graph['nodes']}
            assert len(ids)==len(graph['nodes'])
            assert len({a['arc_id'] for a in graph['arcs']})==len(graph['arcs'])
            for a in graph['arcs']:
                assert a['from_node_id'] in ids and a['to_node_id'] in ids
                assert valid_number(a['length_m']) and a['length_m']>0

    def _filtered_adjacency(self,graph_kind,aid,mode,pair,blocked):
        key=(graph_kind,aid,mode,pair,blocked)
        if key in self._route_cache:return self._route_cache[key]
        adjacency=defaultdict(list)
        for arc in self._graphs[graph_kind]['arcs']:
            if arc['arc_id'] in blocked:continue
            if graph_kind=='vehicle':
                if pair not in arc['equipment_pair_refs'] or arc_reason(self._loads[aid],arc):continue
            elif mode not in arc['allowed_modes']:continue
            adjacency[arc['from_node_id']].append(arc)
        self._route_cache[key]=adjacency
        return adjacency

    @staticmethod
    def _reachable(adjacency,start,end):
        """Unweighted existence gate; does not calculate a route/placement score."""
        seen={start}; pending=deque([start])
        while pending:
            node=pending.popleft()
            if node==end:return True
            for arc in adjacency.get(node,[]):
                nxt=arc['to_node_id']
                if nxt not in seen:seen.add(nxt);pending.append(nxt)
        return False

    @staticmethod
    def _shortest_route(adjacency,start,end):
        distances={start:0.0};parents={};pending=[(0.0,start)]
        while pending:
            distance,node=heapq.heappop(pending)
            if distance!=distances[node]:continue
            if node==end:break
            for arc in adjacency.get(node,[]):
                nxt=arc['to_node_id'];new_distance=distance+arc['length_m']
                if new_distance<distances.get(nxt,math.inf):
                    distances[nxt]=new_distance;parents[nxt]=arc
                    heapq.heappush(pending,(new_distance,nxt))
        assert end in distances,'Reachability gate must precede shortest route'
        route=[];node=end
        while node!=start:
            arc=parents[node];route.append(arc['arc_id']);node=arc['from_node_id']
        return dict(arc_ids=list(reversed(route)),length_m=distances[end])

    def admit(self,request,context,score=distance_score):
        trace=[]
        def result(ok,reason,**details):
            return dict(planning_eligible=ok,reason=reason,planning_only=True,
                operational_admission=False,actual_mesh_actions_verified=False,
                cost_evaluated=False,decision_trace=list(trace),**details)
        if not isinstance(request,dict) or not isinstance(context,PlanningContext):
            return result(False,'INVALID_REQUEST')
        if set(request)-{'sku_id','slot_id','orientation_id','transport_tag'}:
            return result(False,'CARGO_OVERRIDE_FORBIDDEN')
        if any(type(v) is not str for v in request.values()):return result(False,'INVALID_REQUEST')
        if type(context.origin_node_id) is not str or type(context.direction) is not str or context.equipment_pair_ref is not None and type(context.equipment_pair_ref) is not str:
            return result(False,'INVALID_CONTEXT')
        if any(type(values) is not frozenset or any(type(v) is not str for v in values) for values in
            [context.design_equipment_tags,context.occupied_slot_ids,context.unavailable_arc_ids]):
            return result(False,'INVALID_CONTEXT')
        trace.append('canonical_identity')
        sku=self._skus.get(request.get('sku_id'))
        slot=self._slots.get(request.get('slot_id'))
        if sku is None:return result(False,'UNKNOWN_SKU')
        if slot is None:return result(False,'UNKNOWN_SLOT')
        cargo=self._cargo[sku['archetype_id']];aid=cargo['archetype_id']
        tag=request.get('transport_tag',cargo['handling']['modes'][0]['transport_tag'])
        if context.direction not in ['inbound','outbound'] or type(context.handler_design_available) is not bool:
            return result(False,'INVALID_CONTEXT')
        try:
            masses=dict(context.module_masses_kg)
            if len(masses)!=len(context.module_masses_kg) or any(not valid_number(v) or v<0 for v in masses.values()):
                return result(False,'INVALID_OCCUPANCY')
        except (TypeError,ValueError):return result(False,'INVALID_OCCUPANCY')
        trace.append('storage_type_orientation_dimensions_mass_capacity_handler')
        verdict=evaluate(cargo,slot,self._modules[slot['module_id']],
            orientation_id=request.get('orientation_id','upright_xyz'),transport_tag=tag,
            occupied_units=int(slot['slot_id'] in context.occupied_slot_ids),
            module_mass_kg=masses.get(slot['module_id'],0),
            handler_available=context.handler_design_available)
        if not verdict['design_eligible']:return result(False,verdict['reason'],compatibility=verdict)
        option=next(o for o in slot['conditional_handler_options'] if o['transport_tag']==tag and aid in o['allowed_cargo_archetype_ids'])
        trace.append('declared_equipment_and_rating')
        if not set(option['required_equipment_tags'])<=context.design_equipment_tags:
            return result(False,'HANDLER_UNAVAILABLE')
        forklift=tag=='forklift_assisted'
        graph_kind='vehicle' if forklift else 'walk'
        mode='manual_cart' if tag=='manual_cart' else 'pedestrian'
        if forklift:
            pair=self._pairs.get(context.equipment_pair_ref)
            if not pair or pair['eligible_direction']!=context.direction:return result(False,'HANDLER_UNAVAILABLE')
            load=self._loads.get(aid)
            if not load:return result(False,'HANDLER_UNAVAILABLE')
            if not rated_mass_eligible(self._vehicle,load['total_lifted_mass_kg'],load['load_centre_from_fork_heel_m']):
                return result(False,'OVERWEIGHT')
            if not rated_mass_eligible(self._vehicle,load['total_lifted_mass_kg'],load['extended_handling_rating_arm_from_fixed_Z04_m']):
                return result(False,'OVERWEIGHT')
            target=slot['access'].get('vehicle')
        else:
            target=slot['access'].get('cart_stop_id' if tag=='manual_cart' else 'worker_node_id')
        nodes=self._nodes[graph_kind]
        origin=nodes.get(context.origin_node_id)
        if origin is None or target not in nodes:return result(False,'PATH_UNAVAILABLE')
        if not forklift and any(mode not in n.get('allowed_modes',['manual_cart','pedestrian']) for n in [origin,nodes[target]]):
            return result(False,'PATH_UNAVAILABLE')
        trace.append('port_permission')
        port=self._ports.get(origin.get('port_id'))
        if port:
            if port['direction']!=context.direction or aid not in port['allowed_cargo_archetype_ids']:
                return result(False,'PORT_CARGO_FORBIDDEN')
            if forklift and (aid not in port['forklift_cargo_archetype_ids'] or port['equipment_pair_ref']!=context.equipment_pair_ref):
                return result(False,'HANDLER_UNAVAILABLE')
        trace.append('filtered_path_existence')
        adjacency=self._filtered_adjacency(graph_kind,aid,mode,context.equipment_pair_ref,context.unavailable_arc_ids)
        start,end=(context.origin_node_id,target) if context.direction=='inbound' else (target,context.origin_node_id)
        route_key=(graph_kind,aid,mode,context.equipment_pair_ref,context.unavailable_arc_ids,start,end)
        if route_key not in self._reachability_cache:
            self._reachability_cache[route_key]=self._reachable(adjacency,start,end)
        if not self._reachability_cache[route_key]:return result(False,'PATH_UNAVAILABLE')
        trace.append('all_hard_gates_passed')
        if route_key not in self._shortest_cache:
            route=self._shortest_route(adjacency,start,end)
            self._shortest_cache[route_key]=(tuple(route['arc_ids']),route['length_m'])
        cached_ids,length=self._shortest_cache[route_key]
        route=dict(arc_ids=list(cached_ids),length_m=length)
        trace.append('route_and_placement_score')
        features=dict(sku_id=sku['sku_id'],slot_id=slot['slot_id'],archetype_id=aid,
            HU_gross_mass_kg=cargo['handling_unit']['gross_mass_kg'],
            HU_dimensions_xyz_m=list(cargo['handling_unit']['dimensions_xyz_m']),
            route_length_m=route['length_m'],transport_tag=tag)
        cost=score(copy.deepcopy(features))
        if not valid_number(cost) or cost<0:
            r=result(False,'INVALID_SCORE');r['cost_evaluated']=True;return r
        r=result(True,'PLANNING_COMPATIBLE',cost=float(cost),score_unit='caller_defined; default metres',
            canonical=features,route=dict(graph=graph_kind,from_node_id=start,to_node_id=end,**route),
            placement=verdict['details']['placement'],
            execution_requirements=['Bound actual M/P mesh/support/contact/retention/lock and action evidence',
                'Runtime actor/equipment/staging/traffic reservation and source-labelled jobs'])
        r['cost_evaluated']=True
        return r


def probes(policy):
    positives=[];negatives=[]
    for aid in policy._cargo:
        sku=next(s for s in policy._skus.values() if s['archetype_id']==aid)
        cargo=policy._cargo[aid];forklift=aid not in ['SMALL_CARTON','STANDARD_CARTON']
        tag='forklift_assisted' if forklift else 'manual_cart'
        context=PlanningContext('v3:service:IN_W_BULK' if forklift else 'v3:service:IN_E_PARCEL',
            equipment_pair_ref='INBOUND_FORKLIFT_PAIR' if forklift else None,
            design_equipment_tags=frozenset(['forklift','approved_load_support','positive_locked_long_cradle'] if forklift else ['manual_cart']))
        chosen=None
        for slot in policy._slots.values():
            calls=[]
            request=dict(sku_id=sku['sku_id'],slot_id=slot['slot_id'],transport_tag=tag)
            verdict=policy.admit(request,context,lambda f:calls.append(f) or f['route_length_m'])
            assert len(calls)==int(verdict['cost_evaluated'])
            if verdict['planning_eligible']:
                assert len(calls)==1 and not verdict['operational_admission']
                chosen=(request,context,verdict);break
        assert chosen,aid
        request,context,verdict=chosen
        positives.append(dict(archetype_id=aid,request=request,verdict=verdict))
        def negative(name,expected,req=None,ctx=None):
            calls=[];r=policy.admit(req or request,ctx or context,lambda f:calls.append(f) or -1)
            assert not r['planning_eligible'] and r['reason']==expected,(name,r)
            assert not calls and not r['cost_evaluated'] and 'route_and_placement_score' not in r['decision_trace']
            negatives.append(dict(case_id=f'{aid}:{name}',reason=r['reason'],score_calls=0,passed=True))
        negative('mass_override','CARGO_OVERRIDE_FORBIDDEN',dict(request,HU_mass_kg=.01))
        negative('scale_override','CARGO_OVERRIDE_FORBIDDEN',dict(request,scale_factor=.1))
        negative('orientation','ORIENTATION_FORBIDDEN',dict(request,orientation_id='unlisted_90deg'))
        negative('handler_absent','HANDLER_UNAVAILABLE',ctx=replace(context,handler_design_available=False))
        negative('equipment_absent','HANDLER_UNAVAILABLE',ctx=replace(context,design_equipment_tags=frozenset()))
        negative('occupied_slot','SLOT_CAPACITY',ctx=replace(context,occupied_slot_ids=frozenset([request['slot_id']])))
        module=policy._slots[request['slot_id']]['module_id']
        negative('module_overweight','OVERWEIGHT',ctx=replace(context,module_masses_kg=((module,1e9),)))
        negative('origin_missing','PATH_UNAVAILABLE',ctx=replace(context,origin_node_id='nonexistent-node'))
        arcs=policy._graphs['vehicle' if forklift else 'walk']['arcs']
        negative('all_paths_closed','PATH_UNAVAILABLE',ctx=replace(context,unavailable_arc_ids=frozenset(a['arc_id'] for a in arcs)))
        if forklift:
            negative('wrong_pair','HANDLER_UNAVAILABLE',ctx=replace(context,equipment_pair_ref='OUTBOUND_FORKLIFT_PAIR'))
        wrong=next(s for s in policy._slots.values() if s['storage_type'] not in cargo['compatibility']['storage_type_tags'] and not s['retrieval_blocked'])
        negative('wrong_type','CARGO_TYPE_MISMATCH',dict(request,slot_id=wrong['slot_id']))
        blocked=next(s for s in policy._slots.values() if s['retrieval_blocked'])
        negative('blocked_reserve','HEIGHT_ACCESS_UNAVAILABLE',dict(request,slot_id=blocked['slot_id']))
        calls=[];bad=policy.admit(request,context,lambda f:calls.append(f) or float('nan'))
        assert len(calls)==1 and bad['reason']=='INVALID_SCORE' and bad['cost_evaluated']
    return dict(passed=True,positive_cases=positives,negative_cases=negatives,
        negative_score_calls=0,invalid_post_eligibility_score_cases=8)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    policy=AdmissionPolicy();checks=probes(policy)
    document=dict(schema_id='qoima.admission-policy.v3-planning',schema_version='0.1.0',source_kind='synthetic_design',
        operational_admission=False,planning_only=True,source_fingerprints=policy.fingerprints,
        decision_order=['canonical_identity','storage_type_orientation_dimensions_mass_capacity_handler',
            'declared_equipment_and_rating','port_permission','filtered_path_existence',
            'all_hard_gates_passed','route_and_placement_score'],
        scope='Canonical SKU/HU to slot planning gate. No inventory creation, real actor availability, support/lock/action or execution admission.',
        checks=checks)
    if args.check_only:assert OUT.read_bytes()==encoded(document),'Policy/probes differ from saved current inputs'
    else:
        OUT.write_bytes(encoded(document))
        evidence=dict(task_id='C09',owner='root',status='VERIFY',artifact=dict(path=OUT.relative_to(ROOT).as_posix(),sha256=sha(OUT),bytes=OUT.stat().st_size),
            builder_sha256=sha(Path(__file__)),positive_cases=len(checks['positive_cases']),
            negative_cases=len(checks['negative_cases']),negative_score_calls=0,
            actual_model_actions_verified=False,operational_admission=False)
        (ROOT/'docs/adaptive-v3/evidence/C09.json').write_bytes(encoded(evidence))
    print(json.dumps(dict(passed=True,positive_cases=len(checks['positive_cases']),negative_cases=len(checks['negative_cases']),negative_score_calls=0,invalid_score_cases=8)))


if __name__=='__main__':main()
