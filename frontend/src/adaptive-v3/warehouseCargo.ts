import {decodeV3Table} from './warehouseAdapter';
import {cargoHolderKey,cargoHolderPhysicalKey,holderByDestination,isCargoHolderCatalogue,type CargoHolderCatalogue,type CargoHolderDestination,type CargoHolderFrame} from './warehouseCargoHolders';
import type {InitialCargo, V3Record, WarehouseBundle, WarehouseSlot, XYZ} from './warehouseTypes';

export type CargoDestination =
 | {kind:'storage_slot'; slot_id:string}
 | {kind:'actor'; actor_id:string; anchor_id:string}
 | {kind:'vehicle'; vehicle_id:string; anchor_id:string}
 | {kind:'cart'; cart_id:string; anchor_id:string}
 | {kind:'belt'; cell_id:string};
export type CargoBinding = {handling_unit_id:string; destination:CargoDestination};
export type BoundCargo = CargoBinding & {cargo:InitialCargo; position:XYZ; yaw_rad:number; model_scale_factor:1};
export type CargoBindingReason = 'BINDINGS_OK'|'INVALID_REQUEST'|'UNKNOWN_HU'|'DUPLICATE_HU'|'UNKNOWN_SLOT'
 |'RESERVE_SLOT'|'RETRIEVAL_BLOCKED'|'CARGO_CLASS_FORBIDDEN'|'ORIENTATION_FORBIDDEN'
 |'DIMENSION_CLEARANCE_BUDGET'|'SLOT_OVERWEIGHT'|'SLOT_OCCUPIED'|'MODULE_OVERWEIGHT'
 |'PHYSICAL_HOLDER_NOT_REGISTERED'|'HOLDER_CARGO_FORBIDDEN'|'HOLDER_OVERWEIGHT'|'HOLDER_TOTAL_OVERWEIGHT'
 |'HOLDER_OCCUPIED'|'INVALID_HOLDER_FRAME'|'HOLDER_OUTSIDE_WAREHOUSE';
export type CargoBindingResult = {ok:boolean; reason:CargoBindingReason; handling_unit_id:string|null;
 source_kind:'visual_fixture'; engine_operation:false; operational_admission:false; cost_evaluated:false};
const record = (v:unknown):v is V3Record => !!v && typeof v==='object' && !Array.isArray(v);
const freeze = <T>(v:T):T => {if(v && typeof v==='object'){for(const child of Object.values(v))freeze(child);Object.freeze(v);}return v;};
const result = (ok:boolean,reason:CargoBindingReason,id:string|null=null):CargoBindingResult =>
 Object.freeze({ok,reason,handling_unit_id:id,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,cost_evaluated:false});
const exactKeys = (value:V3Record,keys:string[]) => Object.keys(value).length===keys.length && keys.every(k=>Object.hasOwn(value,k));

/** One immutable HU identity, one destination. This state never performs a physical transfer or engine operation. */
export function createWarehouseCargo(bundle:WarehouseBundle){
 if(!Object.isFrozen(bundle)||bundle.source_kind!=='visual_fixture'||bundle.engine_operation!==false)throw Error('VALIDATED_VISUAL_BUNDLE_REQUIRED');
 const cargo = new Map(bundle.fixture.inputs.initial_stock.map(h=>[h.handling_unit_id,h]));
 const slots = new Map(bundle.layout.slots.map(s=>[s.slot_id,s]));
 const storage = bundle.layout.data.storage as V3Record;
 const slotPolicy = new Map(decodeV3Table(storage.slots).map(s=>[s.slot_id as string,s]));
 const definitions = storage.module_definitions as Record<string,{module_payload:number}>;
 const initial:CargoBinding[] = [...cargo.values()].map(h=>({handling_unit_id:h.handling_unit_id,destination:{kind:'storage_slot',slot_id:h.location.slot_id}}));
 let state = new Map(initial.map(b=>[b.handling_unit_id,freeze(b)]));
 let holders:CargoHolderCatalogue|undefined,resolveFrame:((destination:CargoHolderDestination)=>CargoHolderFrame)|undefined;

 function storagePose(hu:InitialCargo,slot:WarehouseSlot):{position:XYZ;yaw_rad:number}{
  const module=bundle.layout.modules[slot.module_index],policy=slotPolicy.get(slot.slot_id)!;
  // C04 supported_placement: bottom touches the support; front clearance is exactly c.
  // bin_anchor is the usable box centre in XZ, not a cargo bottom/centre target.
  const shift=slot.usable_dimensions_xyz_m[2]/2-(policy.clearance_each_side_m as number)-hu.dimensions_xyz_m[2]/2;
  return {position:[slot.bin_anchor[0]+Math.sin(module.yaw_rad)*shift,slot.bin_anchor[1],slot.bin_anchor[2]+Math.cos(module.yaw_rad)*shift],yaw_rad:module.yaw_rad};
 }
 function registerHolders(catalogue:CargoHolderCatalogue,frameProvider:(destination:CargoHolderDestination)=>CargoHolderFrame){
  if(!isCargoHolderCatalogue(catalogue,bundle)||typeof frameProvider!=='function')throw Error('INVALID_HOLDER_CATALOGUE');
  if([...state.values()].some(b=>b.destination.kind!=='storage_slot'))throw Error('HOLDERS_IN_USE');
  holders=catalogue;resolveFrame=frameProvider;
 }
 function carrierReason(hu:InitialCargo,destination:CargoHolderDestination):CargoBindingReason|null{
  const holder=holders&&holderByDestination(holders,destination);
  if(!holder||!resolveFrame)return 'PHYSICAL_HOLDER_NOT_REGISTERED';
  if(!Object.hasOwn(holder.positions,hu.archetype_id))return 'HOLDER_CARGO_FORBIDDEN';
  const local=holder.positions[hu.archetype_id];
  if(hu.gross_mass_kg>holder.max_payload_kg+1e-9)return 'HOLDER_OVERWEIGHT';
  const tare=local.support_tare_kg??holder.support_tare_kg;
  if(holder.max_total_gross_kg!==null&&hu.gross_mass_kg+tare>holder.max_total_gross_kg+1e-9)return 'HOLDER_TOTAL_OVERWEIGHT';
  return null;
 }
 function carrierPose(hu:InitialCargo,destination:CargoHolderDestination):{reason:CargoBindingReason|null;pose:{position:XYZ;yaw_rad:number}|null}{
  const reason=carrierReason(hu,destination);if(reason)return {reason,pose:null};
  const holder=holderByDestination(holders!,destination)!,local=holder.positions[hu.archetype_id];
  let frame:CargoHolderFrame;
  try{frame=resolveFrame!(holder.destination);}catch{return {reason:'INVALID_HOLDER_FRAME',pose:null};}
  const vector=(v:unknown):v is XYZ=>Array.isArray(v)&&v.length===3&&v.every(x=>typeof x==='number'&&Number.isFinite(x));
  if(!record(frame)||!exactKeys(frame,['position','yaw_rad','scale'])||!vector(frame.position)||!vector(frame.scale)||frame.scale.some(x=>Math.abs(x-1)>1e-9)||typeof frame.yaw_rad!=='number'||!Number.isFinite(frame.yaw_rad))return {reason:'INVALID_HOLDER_FRAME',pose:null};
  if(frame.position.some((n,i)=>n<0||n>[144,8,72][i]))return {reason:'HOLDER_OUTSIDE_WAREHOUSE',pose:null};
  const c=Math.cos(frame.yaw_rad),s=Math.sin(frame.yaw_rad),p=local.position_local;
  const position:XYZ=[frame.position[0]+c*p[0]+s*p[2],frame.position[1]+p[1],frame.position[2]-s*p[0]+c*p[2]],yaw_rad=frame.yaw_rad;
  const d=hu.dimensions_xyz_m,hx=(Math.abs(c)*d[0]+Math.abs(s)*d[2])/2,hz=(Math.abs(s)*d[0]+Math.abs(c)*d[2])/2;
  if(position[0]-hx< -1e-9||position[0]+hx>144+1e-9||position[1]< -1e-9||position[1]+d[1]>8+1e-9||position[2]-hz< -1e-9||position[2]+hz>72+1e-9)return {reason:'HOLDER_OUTSIDE_WAREHOUSE',pose:null};
  return {reason:null,pose:{position,yaw_rad}};
 }
 function inspect(changes:unknown):{admission:CargoBindingResult;next:Map<string,CargoBinding>|null}{
  if(!Array.isArray(changes))return {admission:result(false,'INVALID_REQUEST'),next:null};
  const next=new Map(state),seen=new Set<string>();
  for(const value of changes){
   if(!record(value)||!exactKeys(value,['handling_unit_id','destination'])||typeof value.handling_unit_id!=='string'||!record(value.destination))return {admission:result(false,'INVALID_REQUEST'),next:null};
   const id=value.handling_unit_id,d=value.destination;
   if(!cargo.has(id))return {admission:result(false,'UNKNOWN_HU',id),next:null};
   if(seen.has(id))return {admission:result(false,'DUPLICATE_HU',id),next:null};
   seen.add(id);
   if(d.kind!=='storage_slot'){
    try{cargoHolderKey(d);}catch{return {admission:result(false,'INVALID_REQUEST',id),next:null};}
    if(!holders||!holderByDestination(holders,d))return {admission:result(false,'PHYSICAL_HOLDER_NOT_REGISTERED',id),next:null};
   }else if(!exactKeys(d,['kind','slot_id'])||typeof d.slot_id!=='string')return {admission:result(false,'INVALID_REQUEST',id),next:null};
   next.set(id,freeze(structuredClone(value) as CargoBinding));
  }
  const occupied=new Map<string,number>(),moduleMass=new Map<number,number>(),held=new Set<string>();
  for(const [id,binding] of next){
   const hu=cargo.get(id)!;
   if(binding.destination.kind!=='storage_slot'){
    const reason=carrierReason(hu,binding.destination);if(reason)return {admission:result(false,reason,id),next:null};
    const physical=cargoHolderPhysicalKey(binding.destination);if(held.has(physical))return {admission:result(false,'HOLDER_OCCUPIED',id),next:null};held.add(physical);continue;
   }
   const slot=slots.get(binding.destination.slot_id);
   if(!slot)return {admission:result(false,'UNKNOWN_SLOT',id),next:null};
   const policy=slotPolicy.get(slot.slot_id)!;
   let reason:CargoBindingReason|null=null;
   if(slot.reserve_only)reason='RESERVE_SLOT';
   else if(slot.retrieval_blocked)reason='RETRIEVAL_BLOCKED';
   else if(!(policy.allowed_cargo_archetype_ids as string[]).includes(hu.archetype_id))reason='CARGO_CLASS_FORBIDDEN';
   else if(hu.orientation_id!=='upright_xyz'||!(policy.allowed_orientation_ids as string[]).includes('upright_xyz_in_module'))reason='ORIENTATION_FORBIDDEN';
   else if(hu.dimensions_xyz_m.some((d,i)=>d+2*(policy.clearance_each_side_m as number)>slot.usable_dimensions_xyz_m[i]+1e-9))reason='DIMENSION_CLEARANCE_BUDGET';
   else if(hu.gross_mass_kg>slot.max_payload_kg+1e-9)reason='SLOT_OVERWEIGHT';
   if(reason)return {admission:result(false,reason,id),next:null};
   const count=(occupied.get(slot.slot_id)??0)+1;occupied.set(slot.slot_id,count);
   if(count>slot.max_handling_units)return {admission:result(false,'SLOT_OCCUPIED',id),next:null};
   const mass=(moduleMass.get(slot.module_index)??0)+hu.gross_mass_kg;moduleMass.set(slot.module_index,mass);
   if(mass>definitions[bundle.layout.modules[slot.module_index].family].module_payload+1e-9)return {admission:result(false,'MODULE_OVERWEIGHT',id),next:null};
  }
  for(const [id,binding] of next)if(binding.destination.kind!=='storage_slot'){const checked=carrierPose(cargo.get(id)!,binding.destination);if(checked.reason)return {admission:result(false,checked.reason,id),next:null};}
  return {admission:result(true,'BINDINGS_OK'),next};
 }
 function evaluate(changes:unknown){return inspect(changes).admission;}
 function apply(changes:unknown){const checked=inspect(changes);if(checked.next)state=checked.next;return checked.admission;}
 function snapshot():BoundCargo[]{return freeze([...state.values()].map(binding=>{
  const hu=cargo.get(binding.handling_unit_id)!;
  let pose:{position:XYZ;yaw_rad:number};
  if(binding.destination.kind==='storage_slot')pose=storagePose(hu,slots.get(binding.destination.slot_id)!);
  else {const checked=carrierPose(hu,binding.destination);if(checked.reason||!checked.pose)throw Error(checked.reason??'INVALID_HOLDER_FRAME');pose=checked.pose;}
  return {...binding,cargo:hu,...pose,model_scale_factor:1 as const};
 }));}
 function reset(){state=new Map(initial.map(b=>[b.handling_unit_id,b]));return snapshot();}
 const admitted=inspect([]);if(!admitted.admission.ok)throw Error('INITIAL_'+admitted.admission.reason);
 for(const hu of cargo.values()){
  const slot=slots.get(hu.location.slot_id)!,module=bundle.layout.modules[slot.module_index],p=hu.location.placement,local=p.centre_local_xyz_m;
  const old:XYZ=[module.world_pos[0]+Math.cos(module.yaw_rad)*local[0]+Math.sin(module.yaw_rad)*local[2],module.world_pos[1]+p.bottom_y_m,module.world_pos[2]-Math.sin(module.yaw_rad)*local[0]+Math.cos(module.yaw_rad)*local[2]];
  if(storagePose(hu,slot).position.some((n,i)=>Math.abs(n-old[i])>1e-8))throw Error('INITIAL_PLACEMENT_MISMATCH');
 }
 return Object.freeze({registerHolders,evaluate,apply,snapshot,reset,source_kind:'visual_fixture' as const,engine_operation:false as const,completed_jobs:0 as const});
}
