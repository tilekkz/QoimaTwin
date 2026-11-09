import type {WarehouseBundle,WarehouseArc,XYZ} from './warehouseTypes';
import {decodeV3Table} from './warehouseAdapter';
import {sampleVehicleArc,compileVehicleRoutePreview,rearWheelAngles,type VehicleRoutePreview} from './warehouseRoutePose';
import type {RoutePlan} from './warehouseRouting';

/** One same-HU visual fixture; it does not issue engine events or native admission. */
export type HeavyInboundLocation={kind:'upstream'|'staging_cell'|'vehicle'|'storage_slot';id:string};
export type HeavyInboundWheels={front_L:number;front_R:number;rear_L:number;rear_R:number};
export type HeavyInboundControls={position:XYZ;yaw_rad:number;fork_top_m:number;extension_m:number;wheel_angles_rad:HeavyInboundWheels};
export type HeavyInboundRouteGeometry={kind:'line'}|{kind:'vehicle_arc';arc:WarehouseArc}|{kind:'source_route';route:RoutePlan};
export type HeavyInboundPhase={phase_id:string;start_s:number;end_s:number;kind:'receipt'|'handling'|'route'|'hold';from:HeavyInboundControls;to:HeavyInboundControls;path:HeavyInboundRouteGeometry;cargo_location:HeavyInboundLocation;attached:boolean;cargo_visible:boolean;steer_from_rad?:number;steer_to_rad?:number;timing_basis:'source_action_keys'|'bounded_visual_assumption'|'source_route_geometry'};
export type HeavyInboundLease={resource_id:string;start_s:number;end_s:number;quantity:1;capacity:1;semantics:'planned_half_open'};
export type HeavyInboundEvent={event_id:string;at_s:number;kind:'receipt'|'attach'|'setdown'|'putaway';handling_unit_id:string;from:HeavyInboundLocation;to:HeavyInboundLocation};
export type HeavyInboundReceipt={handling_unit_id:string;sku_id:string;archetype_id:'PALLET_LOAD';dimensions_xyz_m:XYZ;gross_mass_kg:455;quantity_units:24;lot_id:string;request_id:string;model_scale_factor:1};
export type HeavyInboundFixture={schema_id:'qoima.connected-heavy-inbound.v1';fixture_id:string;source_kind:'visual_fixture';engine_operation:false;source_hashes:Record<string,string>;business_input_sha256:string;receipt:HeavyInboundReceipt;actor_id:'F01';vehicle_id:'FL01';stage_cell_id:string;destination_slot_id:string;source_pose:{position:XYZ;yaw_rad:number};target_pose:{position:XYZ;yaw_rad:number};cargo_relative:{position:XYZ;yaw_rad:number};staging:{support_id:string;position:XYZ;yaw_rad:number}[];phases:HeavyInboundPhase[];events:HeavyInboundEvent[];leases:HeavyInboundLease[];native_proof_scope:string;assumptions:string[]};
export type HeavyInboundSample={source_kind:'visual_fixture';engine_operation:false;operational_admission:false;at_s:number;duration_s:number;phase_id:string;actor_id:'F01';vehicle_id:'FL01';body:{position:XYZ;yaw_rad:number};joints:{fork_top_m:number;extension_m:number;fork_halfspacing_m:number;virtual_steer_rad:number;rear_steer_rad:{L:number;R:number}};wheel_angles_rad:HeavyInboundWheels;cargo:{handling_unit_id:string;logical_owner:string;location:HeavyInboundLocation;position:XYZ;yaw_rad:number;quaternion:[number,number,number,number];scale:1;quantity_units:24;gross_mass_kg:455;visible:boolean;attached:boolean};ledger:{baseline_handling_units:530;external_handling_units:1;total_handling_units:531;onsite_handling_units:number;upstream_handling_units:number;units:number;gross_mass_kg:number;workers:24;vehicles:2;stage_capacity:2;stage_occupied:number;events:HeavyInboundEvent[];leases:HeavyInboundLease[]};completed_visual_jobs:0|1;actual_engine_events:readonly never[]};
export type WarehouseHeavyInboundPlan={readonly fixture:Readonly<HeavyInboundFixture>;readonly duration_s:number;readonly business_input_sha256:string;readonly attach_at_s:number;readonly release_at_s:number;readonly receipt_at_s:number;sample:(at_s:number)=>Readonly<HeavyInboundSample>};
const issued=new WeakSet<object>();
const freeze=<T>(v:T):T=>{if(v&&typeof v==='object'&&!Object.isFrozen(v)){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;};
const wrap=(n:number)=>Math.atan2(Math.sin(n),Math.cos(n));
const validXYZ=(v:unknown):v is XYZ=>Array.isArray(v)&&v.length===3&&v.every(n=>typeof n==='number'&&Number.isFinite(n));
function requireValue(v:unknown,reason:string):asserts v{if(!v)throw Error(reason);}
const near=(a:XYZ,b:XYZ,t=2e-6)=>a.every((v,i)=>Math.abs(v-b[i])<=t);
const wheelKeys=['front_L','front_R','rear_L','rear_R'] as const;
export function isWarehouseHeavyInboundPlan(value:unknown):value is WarehouseHeavyInboundPlan{return !!value&&typeof value==='object'&&issued.has(value);}

/** Compile a finite visual timeline. C04 placement rules are checked before any route sample. */
export function compileWarehouseHeavyInboundPlan(bundle:WarehouseBundle,input:HeavyInboundFixture):WarehouseHeavyInboundPlan{
 requireValue(Object.isFrozen(bundle)&&bundle.source_kind==='visual_fixture'&&bundle.engine_operation===false,'VALIDATED_VISUAL_BUNDLE_REQUIRED');
 const f=structuredClone(input),r=f.receipt,stock=bundle.fixture.inputs.initial_stock;
 requireValue(f.schema_id==='qoima.connected-heavy-inbound.v1'&&f.source_kind==='visual_fixture'&&f.engine_operation===false,'INVALID_HEAVY_FIXTURE');
 requireValue(stock.length===530&&bundle.registry.workers.length===24&&bundle.registry.vehicles.length===2,'SOURCE_POPULATION_CHANGED');
 requireValue(r.handling_unit_id==='v3:HU:W11:external:01'&&!stock.some(h=>h.handling_unit_id===r.handling_unit_id)&&r.sku_id==='DEMO_172'&&r.archetype_id==='PALLET_LOAD'&&r.gross_mass_kg===455&&r.quantity_units===24&&r.model_scale_factor===1&&near(r.dimensions_xyz_m,[1.2,1.35,1],1e-12),'EXACT_EXTERNAL_PALLET_REQUIRED');
 requireValue(f.actor_id==='F01'&&f.vehicle_id==='FL01'&&bundle.registry.workers.find(w=>w.actor_id==='F01')?.assigned_vehicle_id==='FL01'&&bundle.registry.vehicles.find(v=>v.vehicle_id==='FL01')?.driver_actor_id==='F01','SOURCE_EQUIPMENT_PAIR_REQUIRED');
 requireValue(f.stage_cell_id==='v3:n2:staging:IN_W_BULK:01'&&f.destination_slot_id==='v3:slot:HEAVY_E:001:L1:B1','UNSUPPORTED_TERMINAL');
 requireValue(f.staging.length===2&&[16,22].every((x,i)=>{const s=f.staging[i],id=i===0?'v3:visual-heavy-inbound:support:IN_W_BULK:01':'v3:n2:support:IN_W_BULK:02';return s.support_id===id&&near(s.position,[x,0,i===0?14.11:13.95],1e-10)&&s.yaw_rad===0;}),'EXACT_TWO_STAGE_SUPPORTS_REQUIRED');
 const slot=bundle.layout.slots.find(s=>s.slot_id===f.destination_slot_id);requireValue(slot&&!slot.reserve_only&&!slot.retrieval_blocked&&!stock.some(h=>h.location.slot_id===slot.slot_id),'TARGET_SLOT_UNAVAILABLE');
 const module=bundle.layout.modules[slot.module_index],storage=bundle.layout.data.storage as Record<string,unknown>,policy=decodeV3Table(storage.slots).find(s=>s.slot_id===slot.slot_id)!;
 requireValue(module.family==='HEAVY'&&(policy.allowed_cargo_archetype_ids as string[]).includes(r.archetype_id)&&(policy.allowed_orientation_ids as string[]).includes('upright_xyz_in_module'),'CARGO_STORAGE_POLICY_REFUSED');
 const clearance=policy.clearance_each_side_m as number;
 requireValue(r.dimensions_xyz_m.every((d,i)=>d+2*clearance<=slot.usable_dimensions_xyz_m[i]+1e-9)&&r.gross_mass_kg<=slot.max_payload_kg,'CARGO_STORAGE_BUDGET_REFUSED');
 const defs=storage.module_definitions as Record<string,{module_payload:number}>,existingMass=stock.filter(h=>bundle.layout.slots.find(s=>s.slot_id===h.location.slot_id)?.module_index===slot.module_index).reduce((n,h)=>n+h.gross_mass_kg,0);
 requireValue(existingMass+r.gross_mass_kg<=defs[module.family].module_payload,'MODULE_PAYLOAD_EXCEEDED');
 const shift=slot.usable_dimensions_xyz_m[2]/2-clearance-r.dimensions_xyz_m[2]/2,expected:XYZ=[slot.bin_anchor[0]+Math.sin(module.yaw_rad)*shift,slot.bin_anchor[1],slot.bin_anchor[2]+Math.cos(module.yaw_rad)*shift];
 requireValue(near(f.target_pose.position,expected,1e-10)&&Math.abs(wrap(f.target_pose.yaw_rad-module.yaw_rad))<1e-10,'TARGET_C04_POSE_MISMATCH');
 requireValue(near(f.source_pose.position,[16,.18,14],1e-10)&&Math.abs(wrap(f.source_pose.yaw_rad-Math.PI))<1e-10&&near(f.cargo_relative.position,[0,0,1],1e-10)&&Math.abs(wrap(f.cargo_relative.yaw_rad-Math.PI))<1e-10,'SAME_HU_CAPTURE_FRAME_REQUIRED');
 const previews=new Map<string,VehicleRoutePreview>(),ids=new Set<string>();let end=0;
 for(const p of f.phases){
  requireValue(!ids.has(p.phase_id)&&p.start_s===end&&Number.isFinite(p.end_s)&&p.end_s>p.start_s,'INVALID_PHASE_INTERVAL');ids.add(p.phase_id);end=p.end_s;
  for(const c of [p.from,p.to])requireValue(validXYZ(c.position)&&c.position[1]===0&&c.position[0]>=0&&c.position[0]<=144&&c.position[2]>=0&&c.position[2]<=72&&Number.isFinite(c.yaw_rad)&&c.fork_top_m>=.18&&c.fork_top_m<=.7&&c.extension_m>=0&&c.extension_m<=.4&&wheelKeys.every(k=>Number.isFinite(c.wheel_angles_rad[k])),'INVALID_VEHICLE_CONTROLS');
  requireValue(p.attached===(p.cargo_location.kind==='vehicle')&&(!p.attached||p.cargo_location.id==='FL01')&&p.cargo_visible===(p.cargo_location.kind!=='upstream'),'INVALID_CARGO_OWNER');
  if(p.path.kind==='source_route'){const q=p.path.route;requireValue(q.ok&&q.actor_id==='F01'&&q.vehicle_id==='FL01'&&q.cargo_archetype_id==='PALLET_LOAD','INVALID_SOURCE_ROUTE');const preview=compileVehicleRoutePreview(bundle,q);requireValue(Math.abs(preview.duration_s-(p.end_s-p.start_s))<1e-8,'SOURCE_ROUTE_DURATION_MISMATCH');previews.set(p.phase_id,preview);}
 }
 requireValue(f.phases.length>0&&f.business_input_sha256.length===64,'EMPTY_HEAVY_PLAN');
 const events=f.events,receipt=events.find(e=>e.kind==='receipt'),attach=events.find(e=>e.kind==='attach'),release=events.find(e=>e.kind==='setdown');
 requireValue(events.length===3&&receipt&&attach&&release&&receipt.at_s<attach.at_s&&attach.at_s<release.at_s&&release.at_s<=end,'INVALID_SAME_HU_EVENT_CHAIN');
 let owner:HeavyInboundLocation={kind:'upstream',id:'IN_W_BULK'},previous=-1;const eventIDs=new Set<string>();
 for(const e of events){requireValue(!eventIDs.has(e.event_id)&&e.handling_unit_id===r.handling_unit_id&&e.at_s>=previous&&e.at_s>=0&&e.at_s<=end&&e.from.kind===owner.kind&&e.from.id===owner.id,'INVALID_EVENT_LEDGER');eventIDs.add(e.event_id);owner=e.to;previous=e.at_s;}
 requireValue(owner.kind==='storage_slot'&&owner.id===f.destination_slot_id,'PUTAWAY_NOT_TERMINAL');
 for(const l of f.leases)requireValue(l.quantity===1&&l.capacity===1&&l.start_s>=0&&l.end_s<=end&&l.end_s>l.start_s,'INVALID_RESOURCE_LEASE');
 for(let i=0;i<f.leases.length;i++)for(let j=i+1;j<f.leases.length;j++){const a=f.leases[i],b=f.leases[j];requireValue(a.resource_id!==b.resource_id||Math.min(a.end_s,b.end_s)<=Math.max(a.start_s,b.start_s),'RESOURCE_CONFLICT');}
 for(const resource of ['actor:F01','vehicle:FL01','HU:'+r.handling_unit_id,'slot:'+f.destination_slot_id])requireValue(f.leases.some(l=>l.resource_id===resource&&l.start_s===0&&l.end_s===end),'RESOURCE_LEASE_MISSING');
 requireValue(f.leases.some(l=>l.resource_id==='stage:'+f.stage_cell_id&&l.start_s===receipt.at_s&&l.end_s===attach.at_s),'STAGE_LEASE_MISSING');
 const units=stock.reduce((n,h)=>n+h.quantity_units,0)+24,mass=stock.reduce((n,h)=>n+h.gross_mass_kg,0)+455;
 function sample(seconds:number):Readonly<HeavyInboundSample>{
  requireValue(typeof seconds==='number'&&Number.isFinite(seconds),'INVALID_TIME');const at_s=Math.max(0,Math.min(end,seconds)),p=f.phases.find(p=>at_s>=p.start_s&&at_s<p.end_s)??f.phases.at(-1)!,u=Math.max(0,Math.min(1,(at_s-p.start_s)/(p.end_s-p.start_s))),smooth=u*u*(3-2*u),lerp=(a:number,b:number)=>a+(b-a)*smooth;
  let position=p.from.position.map((v,i)=>lerp(v,p.to.position[i])) as XYZ,yaw=lerp(p.from.yaw_rad,p.to.yaw_rad),virtual=lerp(p.steer_from_rad??0,p.steer_to_rad??p.steer_from_rad??0),rear=rearWheelAngles(virtual),wheel=Object.fromEntries(wheelKeys.map(k=>[k,lerp(p.from.wheel_angles_rad[k],p.to.wheel_angles_rad[k])])) as HeavyInboundWheels;
  if(p.path.kind!=='line'){const a=p.path.kind==='vehicle_arc'?sampleVehicleArc(p.path.arc,smooth):previews.get(p.phase_id)!.sample(at_s-p.start_s),first=p.path.kind==='vehicle_arc'?sampleVehicleArc(p.path.arc,0):previews.get(p.phase_id)!.sample(0);position=[...a.position];yaw=a.yaw_rad+p.from.yaw_rad-first.yaw_rad;virtual=a.virtual_steer_rad;rear={...a.rear_steer_rad};wheel=Object.fromEntries(wheelKeys.map(k=>[k,p.from.wheel_angles_rad[k]+a.wheel_angles_rad[k]])) as HeavyInboundWheels;}
  const fork=lerp(p.from.fork_top_m,p.to.fork_top_m),extension=lerp(p.from.extension_m,p.to.extension_m),relative=f.cargo_relative.position,localZ=relative[2]+extension,c=Math.cos(yaw),s=Math.sin(yaw),fixed=p.cargo_location.kind==='storage_slot'?f.target_pose:f.source_pose,cargoPosition:XYZ=p.attached?[position[0]+c*relative[0]+s*localZ,fork+relative[1],position[2]-s*relative[0]+c*localZ]:[...fixed.position],cargoYaw=p.attached?yaw+f.cargo_relative.yaw_rad:fixed.yaw_rad;
  const occurred=events.filter(e=>e.at_s<=at_s),location=occurred.at(-1)?.to??{kind:'upstream' as const,id:'IN_W_BULK'},received=occurred.some(e=>e.kind==='receipt');
  requireValue(location.kind===p.cargo_location.kind&&location.id===p.cargo_location.id,'PHASE_LEDGER_OWNER_MISMATCH');
  return freeze({source_kind:'visual_fixture',engine_operation:false,operational_admission:false,at_s,duration_s:end,phase_id:p.phase_id,actor_id:'F01',vehicle_id:'FL01',body:{position,yaw_rad:yaw},joints:{fork_top_m:fork,extension_m:extension,fork_halfspacing_m:.4,virtual_steer_rad:virtual,rear_steer_rad:rear},wheel_angles_rad:wheel,cargo:{handling_unit_id:r.handling_unit_id,logical_owner:location.kind+':'+location.id,location:structuredClone(location),position:cargoPosition,yaw_rad:cargoYaw,quaternion:[0,Math.sin(cargoYaw/2),0,Math.cos(cargoYaw/2)],scale:1,quantity_units:24,gross_mass_kg:455,visible:p.cargo_visible,attached:p.attached},ledger:{baseline_handling_units:530,external_handling_units:1,total_handling_units:531,onsite_handling_units:530+(received?1:0),upstream_handling_units:received?0:1,units,gross_mass_kg:mass,workers:24,vehicles:2,stage_capacity:2,stage_occupied:location.kind==='staging_cell'?1:0,events:structuredClone(occurred),leases:structuredClone(f.leases.filter(l=>at_s>=l.start_s&&at_s<l.end_s))},completed_visual_jobs:at_s===end?1:0,actual_engine_events:[]});
 }
 freeze(f);
 for(let i=0;i<f.phases.length;i++){const p=f.phases[i];if(i){const previous=f.phases[i-1];requireValue(near(p.from.position,previous.to.position,1e-9)&&Math.abs(wrap(p.from.yaw_rad-previous.to.yaw_rad))<1e-9&&Math.abs(p.from.fork_top_m-previous.to.fork_top_m)<1e-9&&Math.abs(p.from.extension_m-previous.to.extension_m)<1e-9,'DISCONNECTED_VEHICLE_PHASES');const a=sample(Math.max(0,p.start_s-1e-8)),b=sample(p.start_s);requireValue(near(a.body.position,b.body.position)&&Math.abs(wrap(a.body.yaw_rad-b.body.yaw_rad))<1e-7&&wheelKeys.every(k=>Math.abs(a.wheel_angles_rad[k]-b.wheel_angles_rad[k])<1e-6),'VEHICLE_WORLD_JUMP');requireValue(near(a.cargo.position,b.cargo.position)&&Math.abs(wrap(a.cargo.yaw_rad-b.cargo.yaw_rad))<1e-7,'CARGO_WORLD_JUMP');}sample(p.start_s);sample((p.start_s+p.end_s)/2);}
 sample(end);const plan=freeze({fixture:f,duration_s:end,business_input_sha256:f.business_input_sha256,attach_at_s:attach.at_s,release_at_s:release.at_s,receipt_at_s:receipt.at_s,sample});issued.add(plan);return plan;
}
export function sampleWarehouseHeavyInboundPlan(plan:WarehouseHeavyInboundPlan,at_s:number){requireValue(isWarehouseHeavyInboundPlan(plan),'INVALID_HEAVY_PLAN');return plan.sample(at_s);}
