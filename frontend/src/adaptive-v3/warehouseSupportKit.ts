import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import bindings from './warehouseSupportBindings.json';
import type {XYZ} from './warehouseTypes';

export type WarehouseCarryPose={
 source_kind:'visual_fixture';engine_operation:false;actual_engine_run:false;units:'m';worker_asset:'worker-manual';
 worker_root:{position:XYZ;yaw_rad:0;scale:XYZ};
 cargo:{handling_unit_ref:string;archetype_id:'SMALL_CARTON';dimensions_xyz_m:XYZ;gross_mass_kg:.94;quantity_units:24;position_m:XYZ;yaw_rad:0;scale:XYZ};
 jointEulerXYZ:Record<string,XYZ>;jointTranslations:Record<string,XYZ>;
 contacts:{side:'L'|'R';local_hand_m:XYZ;world_contact_m:XYZ;target_m:XYZ}[];
 input_hashes:Record<string,string>;
};
export type WarehouseTravelProfile={
 archetype_id:string;fork_top_travel_y_m:number;fork_centres_x_m:[number,number];
 cargo_bounds_local_m:{min:XYZ;max:XYZ};handling_unit_dimensions_xyz_m:XYZ;
 HU_gross_mass_kg:number;attachment_mass_kg:number;total_lifted_mass_kg:number;
 declared_capacity_at_this_centre_kg:number;extended_handling_capacity_kg:number;
 scale_factor:1;orientation_id:'upright_xyz';[key:string]:unknown;
};
export type WarehouseLongCradleDesign={
 mass_kg:40;mount_origin_in_vehicle_m:XYZ;own_dimensions_xyz_m:XYZ;
 positive_pin_design:{open_retraction_m:number;[key:string]:unknown};[key:string]:unknown;
};
type VehicleSupport={schema_version:'0.2.0';operational_admission:false;loads:WarehouseTravelProfile[];long_cradle_design:WarehouseLongCradleDesign;[key:string]:unknown};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const triple=(v:unknown):v is XYZ=>Array.isArray(v)&&v.length===3&&v.every(finite);
const equal=(value:unknown,expected:number[])=>triple(value)&&value.every((n,i)=>n===expected[i]);
function requireValue(condition:unknown,reason:string):asserts condition{if(!condition)throw Error(reason);}
function freeze<T>(value:T):T{if(value&&typeof value==='object'){for(const v of Object.values(value))freeze(v);Object.freeze(value);}return value;}
const carryJoints=['shoulder_lift','upper_arm','elbow_swivel','forearm','palm_roll','hand'].flatMap(n=>['L','R'].map(s=>'joint__'+n+'_'+s));

/** Static reviewed SMALL side clamp only; this does not admit a moving action. */
export function validateWarehouseCarryPose(value:unknown):WarehouseCarryPose{
 requireValue(object(value)&&value.source_kind==='visual_fixture'&&value.engine_operation===false&&value.actual_engine_run===false&&value.units==='m'&&value.worker_asset==='worker-manual','INVALID_STATIC_CARRY_POSE');
 const root=value.worker_root,cargo=value.cargo,joints=value.jointEulerXYZ,translations=value.jointTranslations,hashes=value.input_hashes;
 requireValue(object(root)&&equal(root.position,[0,0,0])&&root.yaw_rad===0&&equal(root.scale,[1,1,1]),'INVALID_STATIC_CARRY_ROOT');
 requireValue(object(cargo)&&cargo.handling_unit_ref==='v3:HU:initial:DEMO_001:01'&&cargo.archetype_id==='SMALL_CARTON'&&equal(cargo.dimensions_xyz_m,[.32,.24,.24])&&cargo.gross_mass_kg===.94&&cargo.quantity_units===24&&equal(cargo.position_m,[0,.85,.4])&&cargo.yaw_rad===0&&equal(cargo.scale,[1,1,1]),'INVALID_STATIC_CARRY_CARGO');
 requireValue(object(joints)&&Object.keys(joints).length===carryJoints.length&&carryJoints.every(n=>triple(joints[n])),'INVALID_STATIC_CARRY_JOINTS');
 requireValue(object(translations)&&Object.keys(translations).length===2&&['L','R'].every(s=>equal(translations['joint__finger_thumb_'+s],[0,0,-.005])),'INVALID_STATIC_CARRY_THUMBS');
 requireValue(Array.isArray(value.contacts)&&value.contacts.length===2&&value.contacts.every((c,i)=>object(c)&&c.side===['L','R'][i]&&triple(c.local_hand_m)&&triple(c.world_contact_m)&&triple(c.target_m)),'INVALID_STATIC_CARRY_CONTACTS');
 requireValue(object(hashes)&&hashes['frontend/public/models/v3/worker-manual.glb']===bindings.manual.sha256,'STATIC_CARRY_MODEL_MISMATCH');
 return freeze(value as unknown as WarehouseCarryPose);
}
function validateVehicleSupport(value:unknown):VehicleSupport{
 requireValue(object(value)&&value.schema_version==='0.2.0'&&value.operational_admission===false&&Array.isArray(value.loads)&&value.loads.length===6,'INVALID_VEHICLE_SUPPORT');
 const expected=new Set(['HEAVY_BOX','PALLET_LOAD','IBC','LONG_BUNDLE','DRUM','FRAGILE_CRATE']);
 for(const load of value.loads){
  requireValue(object(load)&&typeof load.archetype_id==='string'&&expected.delete(load.archetype_id)&&load.scale_factor===1&&load.orientation_id==='upright_xyz','INVALID_VEHICLE_SUPPORT_FAMILY');
  requireValue(finite(load.fork_top_travel_y_m)&&Array.isArray(load.fork_centres_x_m)&&load.fork_centres_x_m.length===2&&load.fork_centres_x_m.every(finite)&&triple(load.handling_unit_dimensions_xyz_m),'INVALID_VEHICLE_SUPPORT_POSE');
  requireValue(object(load.cargo_bounds_local_m)&&triple(load.cargo_bounds_local_m.min)&&triple(load.cargo_bounds_local_m.max),'INVALID_VEHICLE_SUPPORT_BOUNDS');
  requireValue(['HU_gross_mass_kg','attachment_mass_kg','total_lifted_mass_kg','declared_capacity_at_this_centre_kg','extended_handling_capacity_kg'].every(n=>finite(load[n])),'INVALID_VEHICLE_SUPPORT_MASS');
  requireValue(load.total_lifted_mass_kg===(load.HU_gross_mass_kg as number)+(load.attachment_mass_kg as number),'INVALID_VEHICLE_SUPPORT_TOTAL');
 }
 requireValue(object(value.long_cradle_design)&&value.long_cradle_design.mass_kg===40&&equal(value.long_cradle_design.mount_origin_in_vehicle_m,[0,.65,1])&&object(value.long_cradle_design.positive_pin_design),'INVALID_LONG_CRADLE_DESIGN');
 return freeze(value as unknown as VehicleSupport);
}
function aborted(signal:AbortSignal){if(signal.aborted)throw new DOMException('Support kit cancelled','AbortError');}
function disposeTemplates(roots:THREE.Object3D[]){
 const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>();
 for(const root of roots)root.traverse(n=>{if(n instanceof THREE.Mesh){geometries.add(n.geometry);for(const m of Array.isArray(n.material)?n.material:[n.material]){materials.add(m);for(const v of Object.values(m))if(v instanceof THREE.Texture)textures.add(v);}}});
 for(const t of textures)t.dispose();for(const m of materials)m.dispose();for(const g of geometries)g.dispose();
 for(const root of roots){root.removeFromParent();root.clear();}
}

/** Optional isolated assets. A failed/cancelled kit never owns the base warehouse resources. */
export async function loadWarehouseSupportKit(signal:AbortSignal){
 const base=import.meta.env.BASE_URL,loader=new GLTFLoader(),roots:THREE.Group[]=[];
 const sourceRefs=freeze(Object.fromEntries(Object.values(bindings).map(b=>['frontend/public/'+b.path,b.sha256])));
 let disposed=false;
 function dispose(){if(disposed)return;disposed=true;disposeTemplates(roots);}
 async function read(binding:{path:string;sha256:string;bytes:number}){
  aborted(signal);const response=await fetch(base+binding.path,{signal,cache:'no-store'});
  if(!response.ok)throw Error(response.status===404?'В локальном пакете нет комплекта опор V3.':'Комплект опор временно недоступен.');
  const bytes=await response.arrayBuffer();aborted(signal);
  const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
  if(bytes.byteLength!==binding.bytes||sha!==binding.sha256)throw Error('Комплект опор изменился после проверки: '+binding.path);
  aborted(signal);return bytes;
 }
 async function model(binding:{path:string;sha256:string;bytes:number;asset_id:string}){
  const bytes=await read(binding),gltf=await loader.parseAsync(bytes,base+'models/v3/');roots.push(gltf.scene);aborted(signal);
  let tagged=false;gltf.scene.traverse(n=>{if(n.userData.asset_id===binding.asset_id&&n.userData.namespace==='v3')tagged=true;});
  if(!tagged)throw Error('В комплекте опор отсутствует интерфейс '+binding.asset_id);return gltf.scene;
 }
 try{
  const carryPose=validateWarehouseCarryPose(JSON.parse(new TextDecoder().decode(await read(bindings.carryPose))));
  const vehicleSupport=validateVehicleSupport(JSON.parse(new TextDecoder().decode(await read(bindings.vehicleSupport))));
  const manual=await model(bindings.manual),cart=await model(bindings.cart),cradle=await model(bindings.cradle),restraint=await model(bindings.restraint);
  aborted(signal);
  return Object.freeze({manual,cart,cradle,restraint,carryPose,vehicleSupport,travelProfiles:vehicleSupport.loads,longCradleDesign:vehicleSupport.long_cradle_design,sourceRefs,dispose,get disposed(){return disposed;}});
 }catch(error){dispose();throw error;}
}
export type WarehouseSupportKit=Awaited<ReturnType<typeof loadWarehouseSupportKit>>;

/** Apply exact accepted joint transforms and return an idempotent restoration of every joint. */
export function applyCarryPose(root:THREE.Object3D,pose:WarehouseCarryPose){
 validateWarehouseCarryPose(pose);
 const joints=new Map<string,THREE.Object3D>(),saved=new Map<THREE.Object3D,{position:THREE.Vector3;quaternion:THREE.Quaternion}>();
 root.traverse(n=>{if(n.name.startsWith('joint__')){joints.set(n.name,n);saved.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone()});}});
 for(const name of [...Object.keys(pose.jointEulerXYZ),...Object.keys(pose.jointTranslations)])requireValue(joints.has(name),'MISSING_STATIC_CARRY_JOINT_'+name);
 const rotations=new Map<THREE.Object3D,THREE.Quaternion>();
 for(const [name,angles]of Object.entries(pose.jointEulerXYZ)){
  const node=joints.get(name)!,axis=node.userData.custom_axis_runtime;
  if(axis!==undefined){requireValue(triple(axis)&&new THREE.Vector3(...axis).lengthSq()>1e-12,'INVALID_STATIC_CARRY_AXIS');rotations.set(node,new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...axis).normalize(),angles[0]));}
  else rotations.set(node,new THREE.Quaternion().setFromEuler(new THREE.Euler(...angles,'XYZ')));
 }
 for(const [node,q]of rotations)node.quaternion.copy(q);
 // Candidate thumb positions are absolute local coordinates, not additions to the bind position.
 for(const [name,position]of Object.entries(pose.jointTranslations))joints.get(name)!.position.fromArray(position);
 root.updateWorldMatrix(true,true);
 function restore(){for(const [node,rest]of saved){node.position.copy(rest.position);node.quaternion.copy(rest.quaternion);}root.updateWorldMatrix(true,true);}
 return Object.freeze({restore,joints,snapshot:()=>[...joints].map(([name,node])=>({name,position:node.position.toArray(),quaternion:node.quaternion.toArray()})),source_kind:'visual_fixture' as const,engine_operation:false as const,actions_scheduled:0 as const});
}
