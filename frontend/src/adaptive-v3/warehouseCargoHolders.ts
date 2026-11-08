import {checkVisualWorkerCapability} from './workerProfiles';
import type {CargoDestination} from './warehouseCargo';
import type {V3Record,WarehouseBundle,XYZ} from './warehouseTypes';

export type CargoHolderDestination=Exclude<CargoDestination,{kind:'storage_slot'}>;
export type CargoHolderDefinition={
 destination:CargoHolderDestination;
 positions:Record<string,{position_local:XYZ;yaw_local_rad:0;support_tare_kg?:number}>;
 max_handling_units:1;
 max_payload_kg:number;
 support_tare_kg:number;
 max_total_gross_kg:number|null;
 source_refs:Record<string,string>;
};
export type CargoHolderFrame={position:XYZ;yaw_rad:number;scale:XYZ};
export type CargoHolderCatalogue={
 source_kind:'visual_fixture';engine_operation:false;operational_admission:false;
 fixture_id:string;layout_content_hash:string;holders:CargoHolderDefinition[];
 scope:string;
};
const issued=new WeakMap<object,WarehouseBundle>();
const fields={actor:['kind','actor_id','anchor_id'],vehicle:['kind','vehicle_id','anchor_id'],cart:['kind','cart_id','anchor_id'],belt:['kind','cell_id']} as const;
const physicalId={actor:'actor_id',vehicle:'vehicle_id',cart:'cart_id',belt:'cell_id'} as const;
const expectedAnchors={actor:'two-hand-small',vehicle:'forks',cart:'upper-tote'} as const;
const vehicleCargo=new Set(['HEAVY_BOX','PALLET_LOAD','IBC','LONG_BUNDLE','DRUM','FRAGILE_CRATE']);
const fixedCargo:Record<string,{dimensions:XYZ;mass:number}>={
 SMALL_CARTON:{dimensions:[.32,.24,.24],mass:.94},STANDARD_CARTON:{dimensions:[.6,.4,.3],mass:6.35},
 HEAVY_BOX:{dimensions:[.8,.65,.6],mass:200},PALLET_LOAD:{dimensions:[1.2,1.35,1],mass:455},
 IBC:{dimensions:[1.2,1.16,1],mass:654},LONG_BUNDLE:{dimensions:[4.2,.52,.65],mass:200},
 DRUM:{dimensions:[.68,.95,.68],mass:180},FRAGILE_CRATE:{dimensions:[1.1,.95,.85],mass:88},
};
const object=(value:unknown):value is V3Record=>!!value&&typeof value==='object'&&!Array.isArray(value)&&[Object.prototype,null].includes(Object.getPrototypeOf(value));
const keys=(value:V3Record,names:readonly string[])=>Object.keys(value).length===names.length&&names.every(n=>Object.hasOwn(value,n));
const finite=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n);
const vector=(v:unknown):v is XYZ=>Array.isArray(v)&&v.length===3&&v.every(finite);
function freeze<T>(value:T):T{if(value&&typeof value==='object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}
function requireValue(condition:unknown,reason:string):asserts condition{if(!condition)throw Error(reason);}

/** Closed canonical shape. Anchor IDs cannot introduce transform or scale overrides. */
export function cargoHolderKey(value:unknown):string{
 requireValue(object(value)&&typeof value.kind==='string'&&Object.hasOwn(fields,value.kind),'INVALID_HOLDER_DESTINATION');
 const kind=value.kind as keyof typeof fields,names=fields[kind];
 requireValue(keys(value,names)&&names.every(n=>typeof value[n]==='string'&&(value[n] as string).length>0&&(value[n] as string).length<200),'INVALID_HOLDER_DESTINATION');
 return JSON.stringify(names.map(n=>value[n]));
}
export function cargoHolderPhysicalKey(destination:CargoHolderDestination):string{
 cargoHolderKey(destination);const kind=destination.kind;
 return JSON.stringify([kind,(destination as unknown as V3Record)[physicalId[kind]]]);
}
export function isCargoHolderCatalogue(value:unknown,bundle?:WarehouseBundle):value is CargoHolderCatalogue{
 return !!value&&typeof value==='object'&&issued.has(value)&&(!bundle||issued.get(value)===bundle);
}
export function holderByDestination(catalogue:CargoHolderCatalogue,destination:unknown):CargoHolderDefinition|undefined{
 requireValue(isCargoHolderCatalogue(catalogue),'INVALID_HOLDER_CATALOGUE');
 const key=cargoHolderKey(destination);return catalogue.holders.find(h=>cargoHolderKey(h.destination)===key);
}
function manualAllowed(bundle:WarehouseBundle,id:string,mass:number){
 const worker=bundle.registry.workers.find(w=>w.actor_id===id);
 return worker&&worker.baseline_role!=='forklift_driver'&&checkVisualWorkerCapability(bundle.profiles,id,{source_kind:'visual_fixture',engine_operation:false,target_role:worker.baseline_role,handler:'manual',cargo_mass_kg:mass,vehicle_id:null,required_equipment:[]}).eligible;
}

/** Declared binding catalogue only. The scene must verify native assets/contacts before issuing definitions. */
export function compileCargoHolders(bundle:WarehouseBundle,value:unknown):CargoHolderCatalogue{
 requireValue(Object.isFrozen(bundle)&&bundle.source_kind==='visual_fixture'&&bundle.engine_operation===false,'VALIDATED_VISUAL_BUNDLE_REQUIRED');
 requireValue(Array.isArray(value),'INVALID_HOLDER_DEFINITIONS');
 const definitions:CargoHolderDefinition[]=[],seen=new Set<string>();
 const conveyor=bundle.layout.data.conveyor as V3Record,cellIds=new Set((conveyor.cells as V3Record[]).map(c=>c.cell_id));
 const payload=conveyor.payload_admission as {allowed:string[];maximum_footprint_m:[number,number];maximum_height_m:number};
 for(const raw of value){
  requireValue(object(raw)&&keys(raw,['destination','positions','max_handling_units','max_payload_kg','support_tare_kg','max_total_gross_kg','source_refs']),'INVALID_HOLDER_DEFINITION');
  cargoHolderKey(raw.destination);const destination=raw.destination as CargoHolderDestination;
  const physical=cargoHolderPhysicalKey(destination);requireValue(!seen.has(physical),'DUPLICATE_PHYSICAL_HOLDER');seen.add(physical);
  if(destination.kind!=='belt')requireValue(destination.anchor_id===expectedAnchors[destination.kind],'UNKNOWN_HOLDER_ANCHOR');
  requireValue(raw.max_handling_units===1&&finite(raw.max_payload_kg)&&raw.max_payload_kg>0&&finite(raw.support_tare_kg)&&raw.support_tare_kg>=0&&(raw.max_total_gross_kg===null||finite(raw.max_total_gross_kg)&&raw.max_total_gross_kg>raw.support_tare_kg),'INVALID_HOLDER_CAPACITY');
  requireValue(object(raw.positions)&&Object.keys(raw.positions).length>0,'INVALID_HOLDER_POSITIONS');
  requireValue(object(raw.source_refs)&&Object.keys(raw.source_refs).length>0&&Object.entries(raw.source_refs).every(([path,hash])=>/^[A-Za-z0-9_./-]+$/.test(path)&&!path.startsWith('/')&&!path.split('/').includes('..')&&typeof hash==='string'&&/^[a-f0-9]{64}$/.test(hash)),'INVALID_HOLDER_SOURCE_REFS');
  if(destination.kind==='actor'){
   requireValue(manualAllowed(bundle,destination.actor_id,.94),'INELIGIBLE_ACTOR_HOLDER');
   requireValue(raw.max_payload_kg<=15&&raw.support_tare_kg===0&&(raw.max_total_gross_kg===null||raw.max_total_gross_kg<=15),'ACTOR_HOLDER_CAPACITY_FORBIDDEN');
  }else if(destination.kind==='vehicle'){
   const vehicle=bundle.registry.vehicles.find(v=>v.vehicle_id===destination.vehicle_id),worker=vehicle&&bundle.registry.workers.find(w=>w.actor_id===vehicle.driver_actor_id);
   requireValue(vehicle&&worker&&worker.assigned_vehicle_id===vehicle.vehicle_id&&checkVisualWorkerCapability(bundle.profiles,worker.actor_id,{source_kind:'visual_fixture',engine_operation:false,target_role:'forklift_driver',handler:'forklift',cargo_mass_kg:1,vehicle_id:vehicle.vehicle_id,required_equipment:['forklift']}).eligible,'INELIGIBLE_VEHICLE_HOLDER');
   requireValue(raw.max_payload_kg<=1000&&raw.max_total_gross_kg!==null&&raw.max_total_gross_kg<=1000,'VEHICLE_HOLDER_CAPACITY_FORBIDDEN');
   requireValue(raw.support_tare_kg===0||raw.support_tare_kg===40,'VEHICLE_SUPPORT_TARE_MISMATCH');
  }else if(destination.kind==='cart'){
   requireValue(destination.cart_id==='C01'&&Object.hasOwn(raw.source_refs,'frontend/public/models/v3/picking-cart-tote-fixture.glb'),'UNKNOWN_CART_FIXTURE');
   requireValue(raw.support_tare_kg===3&&raw.max_payload_kg<=12&&raw.max_total_gross_kg!==null&&raw.max_total_gross_kg<=15,'CART_TOTE_CAPACITY_FORBIDDEN');
  }else{
   requireValue(cellIds.has(destination.cell_id),'UNKNOWN_BELT_CELL');
   requireValue(raw.max_payload_kg<=15&&raw.support_tare_kg===0&&(raw.max_total_gross_kg===null||raw.max_total_gross_kg<=15),'BELT_HOLDER_CAPACITY_FORBIDDEN');
  }
  for(const [archetype,pose]of Object.entries(raw.positions)){
   requireValue(Object.hasOwn(fixedCargo,archetype),'UNKNOWN_HOLDER_CARGO');
   requireValue(object(pose)&&(keys(pose,['position_local','yaw_local_rad'])||keys(pose,['position_local','yaw_local_rad','support_tare_kg']))&&vector(pose.position_local)&&pose.yaw_local_rad===0,'INVALID_HOLDER_LOCAL_POSE');
   if(destination.kind==='vehicle')requireValue((pose.support_tare_kg??raw.support_tare_kg)===(archetype==='LONG_BUNDLE'?40:0),'VEHICLE_SUPPORT_TARE_MISMATCH');
   else requireValue(!Object.hasOwn(pose,'support_tare_kg'),'HOLDER_PROFILE_TARE_OVERRIDE_FORBIDDEN');
   const canonical=fixedCargo[archetype],record=bundle.fixture.inputs.archetypes.find(a=>a.archetype_id===archetype),hu=record?.handling_unit as V3Record|undefined;
   requireValue(hu&&JSON.stringify(hu.dimensions_xyz_m)===JSON.stringify(canonical.dimensions)&&hu.gross_mass_kg===canonical.mass,'HOLDER_CARGO_SOURCE_MISMATCH');
   if(destination.kind==='actor'||destination.kind==='cart')requireValue(archetype==='SMALL_CARTON','HOLDER_CARGO_CLASS_FORBIDDEN');
   if(destination.kind==='vehicle')requireValue(vehicleCargo.has(archetype),'HOLDER_CARGO_CLASS_FORBIDDEN');
   if(destination.kind==='belt')requireValue(['SMALL_CARTON','STANDARD_CARTON'].includes(archetype)&&payload.allowed.includes(archetype)&&canonical.dimensions[0]<=payload.maximum_footprint_m[0]+1e-9&&canonical.dimensions[2]<=payload.maximum_footprint_m[1]+1e-9&&canonical.dimensions[1]<=payload.maximum_height_m+1e-9,'HOLDER_CARGO_CLASS_FORBIDDEN');
  }
  definitions.push(structuredClone(raw) as unknown as CargoHolderDefinition);
 }
 const catalogue=freeze({source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,fixture_id:bundle.fixture.fixture_id,layout_content_hash:bundle.layout.layout_content_hash,holders:definitions,scope:'Declared immutable single-cargo holder bindings only; native physical admission and resource/action proof remain independently required.'});
 issued.set(catalogue,bundle);return catalogue;
}
