import pickupSource from './pallet-pickup-cycle.json';
import {isWarehouseActionCatalogue,type WarehouseActionCatalogue} from './warehouseActionTimeline';
import {createWarehouseRouter,type RoutePolicy,type RoutePlan} from './warehouseRouting';
import {compileVehicleRoutePreview,type VehicleRoutePreview} from './warehouseRoutePose';
import {createWarehouseCargo,type CargoBindingReason} from './warehouseCargo';
import type {WarehouseBundle,XYZ,InitialCargo} from './warehouseTypes';

/** This module issues reference data only. No Scene, timer, stock ledger or native admission. */
const scope=Object.freeze({source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,physical_join:false as const,native_orientation_and_clearance_admission_required:true as const,native_admission_requires:true as const,completed_jobs:0 as const,cost_evaluated:false as const});
export type PalletTransferRequest={handling_unit_id:string;destination_slot_id:string;actor_id:string;vehicle_id:string};
export type PalletTransferReason='PLAN_OK'|'INVALID_REQUEST'|'INVALID_SOURCE'|'INVALID_POLICY'|'UNKNOWN_HU'|'WRONG_PAIR'|'UNSUPPORTED_CASE'|'ROUTE_UNAVAILABLE'|CargoBindingReason;
export class PalletTransferError extends Error {constructor(readonly reason:'INVALID_PLAN'|'INVALID_TIME'){super(reason);this.name='PalletTransferError';}}
type Wheels={front_L:number;front_R:number;rear_L:number;rear_R:number};
type Controls={position:XYZ;yaw_rad:number;fork_top_m:number;extension_m:number;wheel_angles_rad:Wheels};
export type PalletTransferPhase={phase_id:string;start_s:number;end_s:number;kind:'route'|'handling';timing_basis:'W03_route_preview'|'explanatory_assumption';from:Controls;to:Controls;attached:boolean;released:boolean};
export type PalletTransferInterval={resource_id:string;start_s:number;end_s:number;quantity:1;capacity:1;exclusive:true;semantics:'planned_only_half_open'};
export type PalletTransferSample=typeof scope&{at_s:number;phase_id:string;body:{position:XYZ;yaw_rad:number};joints:{fork_top_m:number;extension_m:number;fork_halfspacing_m:number;virtual_steer_rad:number;rear_steer_rad:{L:number;R:number}};wheel_angles_rad:Wheels;cargo:{handling_unit_id:string;logical_owner:string;position:XYZ;yaw_rad:number;scale:1;quantity_units:number;gross_mass_kg:number};population:{handling_units:530;units:number;gross_mass_kg:number;workers:24;vehicles:2};actual_events:readonly never[]};
type DeepReadonly<T>=T extends (...args:never[])=>unknown?T:T extends object?{readonly [K in keyof T]:DeepReadonly<T[K]>}:T;
type PlanData=typeof scope&{request:PalletTransferRequest;fixture_id:string;layout_content_hash:string;duration_s:number;source_hashes:Record<string,string>;cargo:InitialCargo;source_pose:{position:XYZ;yaw_rad:number};target_pose:{position:XYZ;yaw_rad:number};reference_relative:{translation:XYZ;quaternion:[number,number,number,number];yaw_rad:number;scale:1;native_capture_required:true};routes:{empty:RoutePlan;loaded:RoutePlan};phases:PalletTransferPhase[];intervals:PalletTransferInterval[];resource_validation_before_route_cost:true;actual_reservations:0;actual_events:never[];sample:(at_s:number)=>DeepReadonly<PalletTransferSample>};
export type WarehousePalletTransferPlan=DeepReadonly<PlanData>;
export type PalletTransferCompilation=DeepReadonly<typeof scope&{ok:boolean;reason:PalletTransferReason;plan:WarehousePalletTransferPlan|null}>;
const issued=new WeakMap<object,{bundle:WarehouseBundle;catalogue:WarehouseActionCatalogue;policy:RoutePolicy}>();
function freeze<T>(v:T):T{if(v&&typeof v==='object'&&!Object.isFrozen(v)){for(const child of Object.values(v))freeze(child);Object.freeze(v);}return v;}
const pickup=freeze(structuredClone(pickupSource));
const zero=():Wheels=>({front_L:0,front_R:0,rear_L:0,rear_R:0});
const add=(a:Wheels,b:Wheels):Wheels=>({front_L:a.front_L+b.front_L,front_R:a.front_R+b.front_R,rear_L:a.rear_L+b.rear_L,rear_R:a.rear_R+b.rear_R});
const wrap=(v:number)=>Math.atan2(Math.sin(v),Math.cos(v));
const keys=['handling_unit_id','destination_slot_id','actor_id','vehicle_id'];
function request(v:unknown):v is PalletTransferRequest {
 if(!v||typeof v!=='object'||![Object.prototype,null].includes(Object.getPrototypeOf(v)))return false;
 const descriptors=Object.getOwnPropertyDescriptors(v);
 return Reflect.ownKeys(descriptors).length===keys.length&&keys.every(k=>Object.hasOwn(descriptors,k)&&Object.hasOwn(descriptors[k],'value')&&typeof descriptors[k].value==='string');
}
export function isWarehousePalletTransferPlan(value:unknown,bundle?:WarehouseBundle,catalogue?:WarehouseActionCatalogue,policy?:RoutePolicy):value is WarehousePalletTransferPlan {
 if(!value||typeof value!=='object')return false;const state=issued.get(value);return !!state&&(!bundle||state.bundle===bundle)&&(!catalogue||state.catalogue===catalogue)&&(!policy||state.policy===policy);
}
export function sampleWarehousePalletTransferPlan(plan:WarehousePalletTransferPlan,at_s:number):DeepReadonly<PalletTransferSample>{
 if(!isWarehousePalletTransferPlan(plan))throw new PalletTransferError('INVALID_PLAN');return plan.sample(at_s);
}

/** Exact issued catalogue + exact bundle; W03 itself checks policy issuance. No caller motion/proof overrides. */
export function compileWarehousePalletTransferPlan(bundle:WarehouseBundle,catalogue:WarehouseActionCatalogue,policy:RoutePolicy,value:unknown):PalletTransferCompilation {
 const reject=(reason:PalletTransferReason):PalletTransferCompilation=>freeze({...scope,ok:false,reason,plan:null});
 if(!bundle||typeof bundle!=='object'||!Object.isFrozen(bundle)||!isWarehouseActionCatalogue(catalogue,bundle))return reject('INVALID_SOURCE');
 if(!request(value))return reject('INVALID_REQUEST');
 const q={...value};
 const hu=bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===q.handling_unit_id);
 if(!hu)return reject('UNKNOWN_HU');
 const worker=bundle.registry.workers.find(w=>w.actor_id===q.actor_id),vehicle=bundle.registry.vehicles.find(v=>v.vehicle_id===q.vehicle_id);
 if(q.actor_id!=='F02'||q.vehicle_id!=='FL02'||worker?.assigned_vehicle_id!==q.vehicle_id||vehicle?.driver_actor_id!==q.actor_id)return reject('WRONG_PAIR');
 // All target feasibility and exclusive identity availability precede route minimization.
 const cargo=createWarehouseCargo(bundle),changes=[{handling_unit_id:hu.handling_unit_id,destination:{kind:'storage_slot' as const,slot_id:q.destination_slot_id}}];
 const admission=cargo.evaluate(changes);if(!admission.ok)return reject(admission.reason);
 if(hu.handling_unit_id!=='v3:HU:initial:DEMO_172:01'||q.destination_slot_id!=='v3:slot:HEAVY_E:009:L1:B1')return reject('UNSUPPORTED_CASE');
 for(const id of ['actor:'+q.actor_id,'vehicle:'+q.vehicle_id,'HU:'+hu.handling_unit_id])if(!catalogue.resources.some(r=>r.resource_id===id&&r.capacity===1&&r.available))return reject('INVALID_SOURCE');
 const source=cargo.snapshot().find(h=>h.handling_unit_id===hu.handling_unit_id)!;
 // The private cargo instance is only a reference-pose calculator; it cannot mutate the warehouse.
 if(!cargo.apply(changes).ok)return reject('INVALID_SOURCE');
 const target=cargo.snapshot().find(h=>h.handling_unit_id===hu.handling_unit_id)!;
 const a=bundle.layout.slots.find(s=>s.slot_id===hu.location.slot_id)!,b=bundle.layout.slots.find(s=>s.slot_id===q.destination_slot_id)!;
 if(a.vehicle_node_index===null||b.vehicle_node_index===null)return reject('ROUTE_UNAVAILABLE');
 let router:ReturnType<typeof createWarehouseRouter>;try{router=createWarehouseRouter(bundle,policy);}catch{return reject('INVALID_POLICY');}
 const pair=policy.equipment_pairs.find(p=>p.actor_id===q.actor_id&&p.vehicle_id===q.vehicle_id),port=policy.ports.find(p=>p.equipment_pair_ref===pair?.pair_id&&p.port_id==='OUT_E_B2B');
 if(!pair||!port)return reject('INVALID_POLICY');
 const graph=bundle.layout.vehicle,start='v3:service:'+port.port_id,from=graph.nodes[a.vehicle_node_index],to=graph.nodes[b.vehicle_node_index];
 const base={source_kind:'visual_fixture' as const,engine_operation:false as const,mode:'forklift' as const,actor_id:q.actor_id,vehicle_id:q.vehicle_id,service_port_id:null,closed_arc_ids:[]};
 const empty=router.route({...base,from_node_id:start,to_node_id:from.node_id,cargo_archetype_id:null});
 const loaded=router.route({...base,from_node_id:from.node_id,to_node_id:to.node_id,cargo_archetype_id:hu.archetype_id});
 if(!empty.ok||!loaded.ok)return reject('ROUTE_UNAVAILABLE');
 const emptyPreview=compileVehicleRoutePreview(bundle,empty),loadedPreview=compileVehicleRoutePreview(bundle,loaded);
 const load=policy.loads.find(l=>l.archetype_id===hu.archetype_id)!;
 const high=load.fork_top_travel_y_m as number,low=hu.location.placement.bottom_y_m,extension=pickup.keys.find(k=>k.phase==='controlled_insert')!.reach;
 const heading=from.yaw_rad!,forward:XYZ=[Math.sin(heading),0,Math.cos(heading)];
 // The accepted closed fixture supplies controls only; these new intervals do not execute its clip.
 const engagement=(pose:typeof source):XYZ=>[pose.position[0]-forward[0]*pickup.stock_centre_z_m,0,pose.position[2]-forward[2]*pickup.stock_centre_z_m];
 const sourceEngage=engagement(source),targetEngage=engagement(target),initialOffset=pickup.keys[0].root_z;
 const prepared=(p:XYZ):XYZ=>[p[0]+forward[0]*initialOffset,0,p[2]+forward[2]*initialOffset];
 const sourcePrepared=prepared(sourceEngage),targetPrepared=prepared(targetEngage);
 // Explicit native Float32 bind reference, NOT an actual Scene capture or admitted holder.
 const reachBind=Math.fround(.04)+Math.fround(.36),delta:XYZ=[source.position[0]-sourceEngage[0],source.position[1]-low,source.position[2]-sourceEngage[2]];
 const relative:XYZ=[Math.cos(heading)*delta[0]-Math.sin(heading)*delta[2],delta[1],Math.sin(heading)*delta[0]+Math.cos(heading)*delta[2]-reachBind-extension];
 const relativeYaw=wrap(source.yaw_rad-heading);
 const phases:PalletTransferPhase[]=[],previews=new Map<string,VehicleRoutePreview>();let time=0;
 let current:Controls={position:[...emptyPreview.sample(0).position],yaw_rad:emptyPreview.sample(0).yaw_rad,fork_top_m:high,extension_m:0,wheel_angles_rad:zero()};
 function handling(id:string,duration:number,position:XYZ,fork:number,reach:number,attached:boolean,released=false){
  const distance=position.reduce((sum,v,i)=>sum+(v-current.position[i])*forward[i],0),rolling={front_L:distance/.3,front_R:distance/.3,rear_L:distance/.225,rear_R:distance/.225};
   const next:Controls={position:[...position],yaw_rad:current.yaw_rad,fork_top_m:fork,extension_m:reach,wheel_angles_rad:add(current.wheel_angles_rad,rolling)};
  phases.push({phase_id:id,start_s:time,end_s:time+duration,kind:'handling',timing_basis:'explanatory_assumption',from:current,to:next,attached,released});time+=duration;current=next;
 }
 function route(id:string,preview:VehicleRoutePreview,attached:boolean){
   const first=preview.sample(0),last=preview.sample(preview.duration_s),yawShift=current.yaw_rad-first.yaw_rad;
  const next:Controls={position:[...last.position],yaw_rad:last.yaw_rad+yawShift,fork_top_m:high,extension_m:0,wheel_angles_rad:add(current.wheel_angles_rad,last.wheel_angles_rad)};
  phases.push({phase_id:id,start_s:time,end_s:time+preview.duration_s,kind:'route',timing_basis:'W03_route_preview',from:current,to:next,attached,released:false});previews.set(id,preview);time+=preview.duration_s;current=next;
 }
 route('empty_approach',emptyPreview,false);
 handling('source_connector_high_retracted',.25,sourcePrepared,high,0,false);
 handling('source_extend_high',2,sourcePrepared,high,extension,false);
 handling('source_lower_extended',2,sourcePrepared,low,extension,false);
 handling('source_controlled_insert',4,sourceEngage,low,extension,false);
 handling('source_lift_attached',2,sourceEngage,high,extension,true);
 handling('source_retract_loaded',2,sourceEngage,high,0,true);
 handling('source_reverse_high_retracted',2,sourcePrepared,high,0,true);
 handling('source_return_to_graph',.25,[...from.world_pos],high,0,true);
 route('loaded_route',loadedPreview,true);
 handling('target_connector_high_retracted',.25,targetPrepared,high,0,true);
 handling('target_approach_high_retracted',2,targetEngage,high,0,true);
 handling('target_extend_loaded',2,targetEngage,high,extension,true);
 handling('target_setdown',2,targetEngage,low,extension,true);
 handling('target_controlled_withdraw',4,targetPrepared,low,extension,false,true);
 handling('target_raise_empty',2,targetPrepared,high,extension,false,true);
 handling('target_retract_empty',2,targetPrepared,high,0,false,true);
 handling('target_return_to_graph',.25,[...to.world_pos],high,0,false,true);
 const resources=['actor:'+q.actor_id,'vehicle:'+q.vehicle_id,'HU:'+hu.handling_unit_id,'slot:'+q.destination_slot_id,'handling-space:'+a.slot_id,'handling-space:'+b.slot_id];
 for(const r of [empty,loaded])for(const id of r.arc_ids){const arc=graph.arcs.find(a=>a.arc_id===id)!;for(const group of arc.fields.source_reservation_group_ids as string[])resources.push(group);}
 // Conservative whole-plan claims prevent internal conflicting planned use. They acquire nothing.
 const intervals:PalletTransferInterval[]=[...new Set(resources)].sort().map(resource_id=>({resource_id,start_s:0,end_s:time,quantity:1,capacity:1,exclusive:true,semantics:'planned_only_half_open'}));
 const population={handling_units:530 as const,units:bundle.fixture.inputs.initial_stock.reduce((s,h)=>s+h.quantity_units,0),gross_mass_kg:bundle.fixture.inputs.initial_stock.reduce((s,h)=>s+h.gross_mass_kg,0),workers:24 as const,vehicles:2 as const};
 function sample(seconds:number):DeepReadonly<PalletTransferSample>{
  if(typeof seconds!=='number'||!Number.isFinite(seconds))throw new PalletTransferError('INVALID_TIME');
  const at_s=Math.max(0,Math.min(time,seconds)),phase=phases.find(p=>at_s>=p.start_s&&at_s<p.end_s)??phases.at(-1)!,u=Math.min(1,(at_s-phase.start_s)/(phase.end_s-phase.start_s)),smooth=u*u*(3-2*u);
  const lerp=(a:number,b:number)=>a+(b-a)*smooth;
  let position=phase.from.position.map((v,i)=>lerp(v,phase.to.position[i])) as XYZ,yaw=lerp(phase.from.yaw_rad,phase.to.yaw_rad),wheel=Object.fromEntries(Object.keys(zero()).map(k=>[k,lerp(phase.from.wheel_angles_rad[k as keyof Wheels],phase.to.wheel_angles_rad[k as keyof Wheels])])) as Wheels,virtual=0,rear={L:0,R:0};
  if(phase.kind==='route'){const preview=previews.get(phase.phase_id)!,p=preview.sample(at_s-phase.start_s),first=preview.sample(0);position=[...p.position];yaw=p.yaw_rad+phase.from.yaw_rad-first.yaw_rad;wheel=add(phase.from.wheel_angles_rad,p.wheel_angles_rad);virtual=p.virtual_steer_rad;rear={...p.rear_steer_rad};}
  const fork=lerp(phase.from.fork_top_m,phase.to.fork_top_m),reach=lerp(phase.from.extension_m,phase.to.extension_m),fixed=phase.released?target:source;
  const localZ=reachBind+reach+relative[2],c=Math.cos(yaw),s=Math.sin(yaw);
  const cargoPosition:XYZ=phase.attached?[position[0]+c*relative[0]+s*localZ,fork+relative[1],position[2]-s*relative[0]+c*localZ]:[...fixed.position];
  return freeze({...scope,at_s,phase_id:phase.phase_id,body:{position,yaw_rad:yaw},joints:{fork_top_m:fork,extension_m:reach,fork_halfspacing_m:pickup.fork_halfspacing_m,virtual_steer_rad:virtual,rear_steer_rad:rear},wheel_angles_rad:wheel,cargo:{handling_unit_id:hu!.handling_unit_id,logical_owner:phase.attached?'vehicle:'+q.vehicle_id:'slot:'+(phase.released?b.slot_id:a.slot_id),position:cargoPosition,yaw_rad:phase.attached?yaw+relativeYaw:fixed.yaw_rad,scale:1 as const,quantity_units:hu!.quantity_units,gross_mass_kg:hu!.gross_mass_kg},population,actual_events:[]});
 }
 const policySources=(policy as RoutePolicy&{source_hashes:Record<string,string>}).source_hashes;
 const plan=freeze({...scope,request:q,fixture_id:bundle.fixture.fixture_id,layout_content_hash:bundle.layout.layout_content_hash,duration_s:time,source_hashes:{...catalogue.source_hashes,...policySources},cargo:hu,source_pose:{position:source.position,yaw_rad:source.yaw_rad},target_pose:{position:target.position,yaw_rad:target.yaw_rad},reference_relative:{translation:relative,quaternion:[0,1,0,0] as [number,number,number,number],yaw_rad:relativeYaw,scale:1 as const,native_capture_required:true as const},routes:{empty,loaded},phases,intervals,resource_validation_before_route_cost:true as const,actual_reservations:0 as const,actual_events:[] as never[],sample});
 issued.set(plan,{bundle,catalogue,policy});return freeze({...scope,ok:true,reason:'PLAN_OK' as const,plan});
}
