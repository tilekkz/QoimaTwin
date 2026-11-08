import {decodeV3Table} from './warehouseAdapter';
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
 |'PHYSICAL_HOLDER_NOT_REGISTERED';
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

 function storagePose(hu:InitialCargo,slot:WarehouseSlot):{position:XYZ;yaw_rad:number}{
  const module=bundle.layout.modules[slot.module_index],policy=slotPolicy.get(slot.slot_id)!;
  // C04 supported_placement: bottom touches the support; front clearance is exactly c.
  // bin_anchor is the usable box centre in XZ, not a cargo bottom/centre target.
  const shift=slot.usable_dimensions_xyz_m[2]/2-(policy.clearance_each_side_m as number)-hu.dimensions_xyz_m[2]/2;
  return {position:[slot.bin_anchor[0]+Math.sin(module.yaw_rad)*shift,slot.bin_anchor[1],slot.bin_anchor[2]+Math.cos(module.yaw_rad)*shift],yaw_rad:module.yaw_rad};
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
    const fields:Record<string,string[]>={actor:['kind','actor_id','anchor_id'],vehicle:['kind','vehicle_id','anchor_id'],cart:['kind','cart_id','anchor_id'],belt:['kind','cell_id']};
    const keys=typeof d.kind==='string'&&Object.hasOwn(fields,d.kind)?fields[d.kind]:undefined;
    return {admission:result(false,keys&&exactKeys(d,keys)&&keys.every(k=>typeof d[k]==='string')?'PHYSICAL_HOLDER_NOT_REGISTERED':'INVALID_REQUEST',id),next:null};
   }
   if(!exactKeys(d,['kind','slot_id'])||typeof d.slot_id!=='string')return {admission:result(false,'INVALID_REQUEST',id),next:null};
   next.set(id,freeze(structuredClone(value) as CargoBinding));
  }
  const occupied=new Map<string,number>(),moduleMass=new Map<number,number>();
  for(const [id,binding] of next){
   if(binding.destination.kind!=='storage_slot')return {admission:result(false,'PHYSICAL_HOLDER_NOT_REGISTERED',id),next:null};
   const hu=cargo.get(id)!,slot=slots.get(binding.destination.slot_id);
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
  return {admission:result(true,'BINDINGS_OK'),next};
 }
 function evaluate(changes:unknown){return inspect(changes).admission;}
 function apply(changes:unknown){const checked=inspect(changes);if(checked.next)state=checked.next;return checked.admission;}
 function snapshot():BoundCargo[]{return freeze([...state.values()].map(binding=>{
  const hu=cargo.get(binding.handling_unit_id)!;
  if(binding.destination.kind!=='storage_slot')throw Error('PHYSICAL_HOLDER_NOT_REGISTERED');
  return {...binding,cargo:hu,...storagePose(hu,slots.get(binding.destination.slot_id)!),model_scale_factor:1 as const};
 }));}
 function reset(){state=new Map(initial.map(b=>[b.handling_unit_id,b]));return snapshot();}
 const admitted=inspect([]);if(!admitted.admission.ok)throw Error('INITIAL_'+admitted.admission.reason);
 for(const hu of cargo.values()){
  const slot=slots.get(hu.location.slot_id)!,module=bundle.layout.modules[slot.module_index],p=hu.location.placement,local=p.centre_local_xyz_m;
  const old:XYZ=[module.world_pos[0]+Math.cos(module.yaw_rad)*local[0]+Math.sin(module.yaw_rad)*local[2],module.world_pos[1]+p.bottom_y_m,module.world_pos[2]-Math.sin(module.yaw_rad)*local[0]+Math.cos(module.yaw_rad)*local[2]];
  if(storagePose(hu,slot).position.some((n,i)=>Math.abs(n-old[i])>1e-8))throw Error('INITIAL_PLACEMENT_MISMATCH');
 }
 return Object.freeze({evaluate,apply,snapshot,reset,source_kind:'visual_fixture' as const,engine_operation:false as const,completed_jobs:0 as const});
}
