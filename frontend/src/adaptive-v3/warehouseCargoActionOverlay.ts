import {createWarehouseCargo,type BoundCargo} from './warehouseCargo';
import {isWarehousePalletTransferPlan,type WarehousePalletTransferPlan} from './warehousePalletTransferPlan';
import {isWarehousePalletTransferScene,type createWarehousePalletTransferScene,type PalletTransferFrame} from './warehousePalletTransferScene';
import type {WarehouseBundle} from './warehouseTypes';

type NativeTransfer=ReturnType<typeof createWarehousePalletTransferScene>;
/** One display binding over the immutable stock ledger, issued by the actual native controller. */
export function createWarehouseCargoActionOverlay(bundle:WarehouseBundle,readBase:()=>BoundCargo[]){
 const canonical=JSON.stringify(createWarehouseCargo(bundle).snapshot());
 let issued:{plan:WarehousePalletTransferPlan;native:NativeTransfer}|null=null,current:Readonly<PalletTransferFrame>|null=null;
 const refuse=(reason:string):never=>{throw Error(reason);};
 function base(){const rows=readBase();if(JSON.stringify(rows)!==canonical)refuse('ACTION_REQUIRES_INITIAL_CARGO_BINDINGS');return rows;}
 function bind(plan:WarehousePalletTransferPlan,native:NativeTransfer){
  if(issued)refuse('CARGO_ACTION_BUSY');
  if(!isWarehousePalletTransferPlan(plan,bundle)||!isWarehousePalletTransferScene(native,bundle,plan)||native.snapshot()!==null)refuse('INVALID_CARGO_ACTION_BINDING');
  base();issued={plan,native};current=null;
 }
 function sync(){
  if(!issued)refuse('CARGO_ACTION_NOT_BOUND');base();
  const next=issued!.native.snapshot();
  if(next){
   const {plan}=issued!,expected=plan.sample(next.at_s),bound=next.bound;
   const owner=bound.destination.kind==='vehicle'?'vehicle:'+bound.destination.vehicle_id:bound.destination.kind==='storage_slot'?'slot:'+bound.destination.slot_id:'';
   if(!Object.isFrozen(next)||next.source_kind!=='visual_fixture'||next.engine_operation!==false||next.physical_join!==false||next.completed_jobs!==0||next.actual_events.length!==0||next.phase_id!==expected.phase_id||next.logical_owner!==expected.cargo.logical_owner||owner!==next.logical_owner||bound.handling_unit_id!==plan.request.handling_unit_id||bound.cargo!==plan.cargo||bound.model_scale_factor!==1)refuse('INCOHERENT_CARGO_ACTION_FRAME');
  }
  current=next;return current;
 }
 function clear(){if(issued&&issued.native.snapshot()!==null)refuse('RESTORE_NATIVE_CARGO_BEFORE_CLEAR');issued=null;current=null;}
 function values(){const rows=issued?base():readBase();return current?rows.map(row=>row.handling_unit_id===current!.bound.handling_unit_id?current!.bound:row):rows;}
 return Object.freeze({bind,sync,clear,values,frame:()=>current,busy:()=>issued!==null});
}
