import type {WarehouseArc,WarehouseBundle,WarehouseGraph,V3Record} from './warehouseTypes';

export type RouteMode='pedestrian'|'manual_cart'|'forklift';
export type RouteQuery={source_kind:'visual_fixture';engine_operation:false;mode:RouteMode;actor_id:string;vehicle_id:string|null;cargo_archetype_id:string|null;from_node_id:string;to_node_id:string;service_port_id:string|null;closed_arc_ids:string[]};
export type RoutePolicy={schema_id:string;source_kind:'visual_fixture';engine_operation:false;operational_admission:false;layout_content_hash:string;layout_sha256:string;bare_geometry_subset_groups:{profile_id:string;component_subset_verified:true;arc_ids:string[]}[];loads:V3Record[];loaded_arc_eligibility:{archetype_id:string;allowed_arc_ids:string[]}[];ports:V3Record[];rating_design:V3Record;equipment_pairs:{pair_id:string;actor_id:string;vehicle_id:string;eligible_direction:string}[]};
export type RouteReason='ROUTE_OK'|'ALREADY_THERE'|'INVALID_REQUEST'|'CARGO_OVERRIDE_FORBIDDEN'|'UNKNOWN_WORKER'|'WRONG_VEHICLE_PAIR'|'HANDLER_UNAVAILABLE'|'UNKNOWN_CARGO'|'MANUAL_OVERWEIGHT'|'UNKNOWN_NODE'|'UNKNOWN_ARC'|'UNKNOWN_PORT'|'PORT_CARGO_FORBIDDEN'|'PORT_PAIR_FORBIDDEN'|'PORT_ENDPOINT_MISMATCH'|'RATING_EXCEEDED'|'NO_PATH';
export type RoutePlan={ok:boolean;reason:RouteReason;source_kind:'visual_fixture';engine_operation:false;operational_admission:false;cost_evaluated:boolean;graph:'walk'|'vehicle';from_node_id:string;to_node_id:string;arc_ids:string[];length_m:number|null;mode:RouteMode;actor_id:string;vehicle_id:string|null;cargo_archetype_id:string|null;geometry_basis:'canonical_walk'|'bare_component_subset'|'C08_immutable_load';resource_admission_required:true;actual_action_admission_required:true};
const admittedPolicies=new WeakSet<RoutePolicy>();
const record=(v:unknown):v is V3Record=>typeof v==='object'&&v!==null&&!Array.isArray(v);
function freeze<T>(v:T):T{if(v&&typeof v==='object'){for(const item of Object.values(v))freeze(item);Object.freeze(v);}return v;}
export async function validateRoutePolicy(text:string,bundle:WarehouseBundle):Promise<RoutePolicy>{
 const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,'0')).join('');
 if(digest!=='24ad87f197d14b1c681814b43b2c8841ca145c6b92515af744f3cb4473d35337')throw Error('POLICY_HASH_MISMATCH');
 const p=JSON.parse(text) as RoutePolicy;if(p.schema_id!=='qoima.visual-route-policy.v3'||p.source_kind!=='visual_fixture'||p.engine_operation!==false||p.operational_admission!==false||p.layout_content_hash!==bundle.layout.layout_content_hash||p.layout_sha256!==bundle.fixture.layout_ref.sha256)throw Error('POLICY_LAYOUT_MISMATCH');
 const admitted=freeze(p);admittedPolicies.add(admitted);return admitted;
}

type QueueItem={distance:number;node:number};
/** Small stable binary heap; source-ID tie breaking is independent of table/arc iteration order. */
function queue(graph:WarehouseGraph){
 const items:QueueItem[]=[],less=(a:QueueItem,b:QueueItem)=>a.distance<b.distance||a.distance===b.distance&&graph.nodes[a.node].node_id<graph.nodes[b.node].node_id;
 return {get size(){return items.length;},push(item:QueueItem){let i=items.push(item)-1;while(i>0){const parent=(i-1)>>1;if(!less(items[i],items[parent]))break;[items[i],items[parent]]=[items[parent],items[i]];i=parent;}},pop(){const first=items[0],last=items.pop()!;if(items.length){items[0]=last;let i=0;for(;;){let next=i;const a=2*i+1,b=a+1;if(a<items.length&&less(items[a],items[next]))next=a;if(b<items.length&&less(items[b],items[next]))next=b;if(next===i)break;[items[i],items[next]]=[items[next],items[i]];i=next;}}return first;}};
}

/** Geometry query only. Neither a path nor an allowed port point starts a warehouse operation. */
export function createWarehouseRouter(bundle:WarehouseBundle,policy:RoutePolicy){
 if(!admittedPolicies.has(policy)||policy.source_kind!=='visual_fixture'||policy.engine_operation!==false||policy.operational_admission!==false||bundle.source_kind!=='visual_fixture'||bundle.engine_operation!==false||policy.layout_content_hash!==bundle.layout.layout_content_hash)throw Error('POLICY_LAYOUT_MISMATCH');
 const cargo=new Map(bundle.fixture.inputs.archetypes.map(c=>[c.archetype_id,c])),workers=new Map(bundle.registry.workers.map(w=>[w.actor_id,w])),profiles=new Map(bundle.profiles.profiles.map(p=>[p.worker_id,p])),loads=new Map(policy.loads.map(l=>[l.archetype_id,l])),eligible=new Map(policy.loaded_arc_eligibility.map(r=>[r.archetype_id,new Set(r.allowed_arc_ids)])),bare=new Set(policy.bare_geometry_subset_groups.filter(g=>g.component_subset_verified).flatMap(g=>g.arc_ids));
 const graphs={walk:bundle.layout.walk,vehicle:bundle.layout.vehicle},indices={walk:new Map(graphs.walk.nodes.map((n,i)=>[n.node_id,i])),vehicle:new Map(graphs.vehicle.nodes.map((n,i)=>[n.node_id,i]))};
 const keys=['source_kind','engine_operation','mode','actor_id','vehicle_id','cargo_archetype_id','from_node_id','to_node_id','service_port_id','closed_arc_ids'];
 function route(value:unknown):RoutePlan{
  const q=value as RouteQuery,vehicle=record(q)&&q.mode==='forklift',kind=vehicle?'vehicle':'walk',basis=vehicle?(q.cargo_archetype_id===null?'bare_component_subset':'C08_immutable_load'):'canonical_walk';
  const result=(ok:boolean,reason:RouteReason,arc_ids:string[]=[],length_m:number|null=null,cost_evaluated=false):RoutePlan=>freeze({ok,reason,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,cost_evaluated,graph:kind,from_node_id:q?.from_node_id??'',to_node_id:q?.to_node_id??'',arc_ids,length_m,mode:q?.mode,actor_id:q?.actor_id??'',vehicle_id:q?.vehicle_id??null,cargo_archetype_id:q?.cargo_archetype_id??null,geometry_basis:basis,resource_admission_required:true,actual_action_admission_required:true});
  if(record(q)&&Object.keys(q).some(k=>!keys.includes(k)))return result(false,'CARGO_OVERRIDE_FORBIDDEN');
  if(!record(q)||q.source_kind!=='visual_fixture'||q.engine_operation!==false||!['pedestrian','manual_cart','forklift'].includes(q.mode)||typeof q.actor_id!=='string'||typeof q.from_node_id!=='string'||typeof q.to_node_id!=='string'||!(q.vehicle_id===null||typeof q.vehicle_id==='string')||!(q.cargo_archetype_id===null||typeof q.cargo_archetype_id==='string')||!(q.service_port_id===null||typeof q.service_port_id==='string')||!Array.isArray(q.closed_arc_ids)||q.closed_arc_ids.some(id=>typeof id!=='string')||new Set(q.closed_arc_ids).size!==q.closed_arc_ids.length)return result(false,'INVALID_REQUEST');
  const worker=workers.get(q.actor_id),profile=profiles.get(q.actor_id);if(!worker||!profile)return result(false,'UNKNOWN_WORKER');
  const pair=vehicle?policy.equipment_pairs.find(p=>p.actor_id===q.actor_id&&p.vehicle_id===q.vehicle_id):undefined;
  if(vehicle&&(!pair||worker.assigned_vehicle_id!==q.vehicle_id)||!vehicle&&q.vehicle_id!==null)return result(false,'WRONG_VEHICLE_PAIR');
  if(q.mode==='manual_cart'&&!profile.allowed_equipment.includes('picking-cart'))return result(false,'HANDLER_UNAVAILABLE');
  const template=q.cargo_archetype_id===null?null:cargo.get(q.cargo_archetype_id);if(q.cargo_archetype_id!==null&&!template)return result(false,'UNKNOWN_CARGO');
  const hu=template?.handling_unit as V3Record|undefined,load=q.cargo_archetype_id===null?null:loads.get(q.cargo_archetype_id);
  if(template&&!vehicle){if(!profile.allowed_handlers.includes('manual'))return result(false,'HANDLER_UNAVAILABLE');if((hu!.gross_mass_kg as number)>bundle.profiles.handling_policy.manual_mass_limit_kg)return result(false,'MANUAL_OVERWEIGHT');}
  if(template&&vehicle&&!load)return result(false,'HANDLER_UNAVAILABLE');
  if(load){const rating=policy.rating_design,mass=load.total_lifted_mass_kg as number,arms=[load.load_centre_from_fork_heel_m,load.extended_handling_rating_arm_from_fixed_Z04_m] as number[];if(arms.some(arm=>!Number.isFinite(arm)||arm<=0||mass>Math.min(rating.nominal_capacity_kg as number,(rating.moment_budget_kg_m as number)/arm))||mass/2>(rating.maximum_single_fork_share_kg as number))return result(false,'RATING_EXCEEDED');}
  const graph=graphs[kind],from=indices[kind].get(q.from_node_id),to=indices[kind].get(q.to_node_id);if(from===undefined||to===undefined)return result(false,'UNKNOWN_NODE');if(!vehicle&&[from,to].some(i=>Array.isArray(graph.nodes[i].attributes.allowed_modes)&&!(graph.nodes[i].attributes.allowed_modes as string[]).includes(q.mode)))return result(false,'NO_PATH');
  const allArcs=new Set(graph.arcs.map(a=>a.arc_id));if(q.closed_arc_ids.some(id=>!allArcs.has(id)))return result(false,'UNKNOWN_ARC');
  if(q.service_port_id!==null){const port=policy.ports.find(p=>p.port_id===q.service_port_id);if(!port)return result(false,'UNKNOWN_PORT');const endpoint='v3:service:'+q.service_port_id;if((port.direction==='inbound'?q.from_node_id:q.to_node_id)!==endpoint)return result(false,'PORT_ENDPOINT_MISMATCH');if(template&&!(port.allowed_cargo_archetype_ids as string[]).includes(q.cargo_archetype_id!))return result(false,'PORT_CARGO_FORBIDDEN');if(vehicle&&port.equipment_pair_ref!==pair!.pair_id)return result(false,'PORT_PAIR_FORBIDDEN');if(vehicle&&template&&!(port.forklift_cargo_archetype_ids as string[]).includes(q.cargo_archetype_id!))return result(false,'PORT_CARGO_FORBIDDEN');}
  const closed=new Set(q.closed_arc_ids),allowed=q.cargo_archetype_id===null?bare:eligible.get(q.cargo_archetype_id),adjacency:WarehouseArc[][]=Array.from({length:graph.nodes.length},()=>[]);
  for(const arc of graph.arcs){if(closed.has(arc.arc_id))continue;const f=arc.fields;if(vehicle){if(!(f.equipment_pair_refs as string[]).includes(pair!.pair_id)||!allowed?.has(arc.arc_id)||q.cargo_archetype_id!==null&&f.cargo_transport_supported===false)continue;}else if(!(f.allowed_modes as string[]).includes(q.mode))continue;adjacency[arc.from_node_index].push(arc);}
  for(const arcs of adjacency)arcs.sort((a,b)=>a.arc_id<b.arc_id?-1:a.arc_id>b.arc_id?1:0);
  // Reachability and hard constraints are checked before any distance minimization.
  const seen=new Set([from]),pending=[from];for(let i=0;i<pending.length&&!seen.has(to);i++)for(const arc of adjacency[pending[i]])if(!seen.has(arc.to_node_index)){seen.add(arc.to_node_index);pending.push(arc.to_node_index);}
  if(!seen.has(to))return result(false,'NO_PATH');if(from===to)return result(true,'ALREADY_THERE',[],0,false);
  const distances=new Map([[from,0]]),parents=new Map<number,WarehouseArc>(),heap=queue(graph);heap.push({distance:0,node:from});
  while(heap.size){const current=heap.pop();if(current.distance!==distances.get(current.node))continue;if(current.node===to)break;for(const arc of adjacency[current.node]){const next=current.distance+arc.length_m;if(next<(distances.get(arc.to_node_index)??Infinity)){distances.set(arc.to_node_index,next);parents.set(arc.to_node_index,arc);heap.push({distance:next,node:arc.to_node_index});}}}
  const route:string[]=[];let node=to;while(node!==from){const arc=parents.get(node)!;route.push(arc.arc_id);node=arc.from_node_index;}route.reverse();return result(true,'ROUTE_OK',route,distances.get(to)!,true);
 }
 return Object.freeze({route});
}
