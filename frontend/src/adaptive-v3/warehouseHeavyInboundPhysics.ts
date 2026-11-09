import * as THREE from 'three';
import type {WarehouseBundle,XYZ} from './warehouseTypes';

export const HEAVY_INBOUND_PALLET_PI_PROFILE='v3:visual-profile:PALLET455:captured-relative-pi:1';
export const HEAVY_INBOUND_NATIVE_EPS_M=2e-6;
const up=new THREE.Vector3(0,1,0),EPS=HEAVY_INBOUND_NATIVE_EPS_M;
const bodyBounds={min:[-.6,0,-1.5],max:[.6,2.1,1.5]};
const palletBounds={min:[-.6,.7,.5],max:[.6,2.05,1.5]};
function requireValue(value:unknown,reason:string):asserts value{if(!value)throw Error(reason);}
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
function unit(matrix:THREE.Matrix4){
 requireValue(matrix.elements.every(finite)&&Math.abs(matrix.determinant())>1e-12,'INVALID_NATIVE_FRAME');
 const position=new THREE.Vector3(),quaternion=new THREE.Quaternion(),scale=new THREE.Vector3();matrix.decompose(position,quaternion,scale);
 requireValue(scale.toArray().every(v=>Math.abs(v-1)<=1e-9)&&up.clone().applyQuaternion(quaternion).distanceTo(up)<=1e-9,'NON_UNIT_OR_TILTED_NATIVE_FRAME');
 return{position,quaternion};
}
const matrix=(p:XYZ,yaw:number)=>new THREE.Matrix4().compose(new THREE.Vector3(...p),new THREE.Quaternion().setFromAxisAngle(up,yaw),new THREE.Vector3(1,1,1));
function transform(p:XYZ,origin:XYZ,yaw:number):XYZ{return new THREE.Vector3(...p).applyMatrix4(matrix(origin,yaw)).toArray();}

/** Exact first-case frames. Source inventory and published C08 are never edited. */
export function heavyInboundPalletEndpoints(bundle:WarehouseBundle){
 const id='v3:slot:HEAVY_E:001:L1:B1',slot=bundle.layout.slots.find(s=>s.slot_id===id);
 requireValue(slot&&!slot.retrieval_blocked&&!slot.reserve_only&&slot.vehicle_node_index!==null,'TARGET_HEAVY_SLOT_UNAVAILABLE');
 requireValue(!bundle.fixture.inputs.initial_stock.some(h=>h.location.slot_id===id),'TARGET_HEAVY_SLOT_OCCUPIED');
 const module=bundle.layout.modules[slot.module_index],p=module.world_pos,yaw=module.yaw_rad;
 requireValue(module.family==='HEAVY'&&p.every((v,i)=>Math.abs(v-[118.3,0,17.5][i])<1e-9)&&Math.abs(yaw-Math.PI/2)<1e-9,'SOURCE_HEAVY_FRAME_CHANGED');
 return Object.freeze({profile_id:HEAVY_INBOUND_PALLET_PI_PROFILE,actor_id:'F01',vehicle_id:'FL01',archetype_id:'PALLET_LOAD',gross_mass_kg:455,quantity_units:24,dimensions_xyz_m:[1.2,1.35,1],
  stage:{cell_id:'v3:n2:staging:IN_W_BULK:01',support_id:'v3:visual-heavy-inbound:support:IN_W_BULK:01',support_position:[16,0,14.11] as XYZ,published_support_position:[16,0,13.95] as XYZ,proposed_support_delta:[0,0,.16] as XYZ,support_placement_is_new_visual_variant:true,support_yaw_rad:0,HU_position:[16,.18,14] as XYZ,HU_yaw_rad:Math.PI,engage_position:[16,0,12.6] as XYZ,prepared_position:[16,0,11.55] as XYZ,vehicle_yaw_rad:0},
  target:{slot_id:id,module_id:module.module_id,support_position:[...p] as XYZ,support_yaw_rad:yaw,HU_position:transform([0,.18,.1],p,yaw),HU_yaw_rad:yaw,engage_position:transform([0,0,1.5],p,yaw),prepared_position:transform([0,0,2.55],p,yaw),vehicle_yaw_rad:yaw+Math.PI,graph_node_id:bundle.layout.vehicle.nodes[slot.vehicle_node_index!].node_id,graph_position:[...bundle.layout.vehicle.nodes[slot.vehicle_node_index!].world_pos] as XYZ},
  controls:{low_fork_top_m:.18,travel_fork_top_m:.7,reach_extended_m:.4,reach_travel_m:0,fork_halfspacing_m:.4,controlled_withdrawal_m:1.05},
  unchanged_C08:{path:'docs/v3/contract-proposals/vehicle-handling-v3.json',sha256:'22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4',component_bounds_local_m:[bodyBounds,palletBounds],travel_capacity_kg:1000,extended_capacity_kg:800,maximum_single_fork_share_kg:500},
  source_kind:'visual_fixture',engine_operation:false,operational_admission:false});
}

export type HeavyInboundPalletCapture=Readonly<{profile_id:typeof HEAVY_INBOUND_PALLET_PI_PROFILE;reach_relative_matrix:readonly number[];cargo_world_before:readonly number[];maximum_attach_matrix_residual:number}>;
/** Capture the actual same cargo world matrix at engagement. The new opt-in π
 * variant preserves that matrix exactly; it does not reuse the old relative0 selector. */
export function captureHeavyInboundPallet(reachWorld:THREE.Matrix4,cargoWorld:THREE.Matrix4,profileId:string):HeavyInboundPalletCapture{
 requireValue(profileId===HEAVY_INBOUND_PALLET_PI_PROFILE,'EXPLICIT_PALLET_PI_PROFILE_REQUIRED');unit(reachWorld);unit(cargoWorld);
 const relative=reachWorld.clone().invert().multiply(cargoWorld),frame=unit(relative),pi=new THREE.Quaternion(0,1,0,0);
 requireValue(1-Math.abs(frame.quaternion.dot(pi))<1e-10,'PALLET_RELATIVE_PI_REQUIRED');
 requireValue(Math.abs(frame.position.x)<=EPS&&Math.abs(frame.position.y)<=EPS&&Math.abs(frame.position.z-.6)<=EPS,'PALLET_NATIVE_CAPTURE_OFFSET_MISMATCH');
 const after=reachWorld.clone().multiply(relative),residual=Math.max(...after.elements.map((v,i)=>Math.abs(v-cargoWorld.elements[i])));
 requireValue(residual<=1e-9,'PALLET_ATTACH_WORLD_JUMP');
 return Object.freeze({profile_id:HEAVY_INBOUND_PALLET_PI_PROFILE,reach_relative_matrix:Object.freeze(relative.toArray()),cargo_world_before:Object.freeze(cargoWorld.toArray()),maximum_attach_matrix_residual:residual});
}
export function sampleHeavyInboundPalletCapture(capture:HeavyInboundPalletCapture,reachWorld:THREE.Matrix4){
 requireValue(capture.profile_id===HEAVY_INBOUND_PALLET_PI_PROFILE,'INVALID_PALLET_CAPTURE');unit(reachWorld);
 return reachWorld.clone().multiply(new THREE.Matrix4().fromArray(capture.reach_relative_matrix));
}

type EnvelopeInput={profile_id:string;vehicle:THREE.Object3D;cargo:THREE.Object3D;fork_top_m:number;extension_m:number;driver?:{actorId:string;role:string;disposed:boolean;seat_error_m:number;grip_error_m:Record<string,number>;sole_error_m:Record<string,number>}};
/** Every current native vertex, including the seated driver, must be contained
 * by the unchanged C08 components at travel. Float32 boundary excess is reported
 * explicitly at the existing 2µm native tolerance, not hidden by a new profile. */
export function checkHeavyInboundPalletNativeEnvelope(o:EnvelopeInput){
 requireValue(o.profile_id===HEAVY_INBOUND_PALLET_PI_PROFILE,'EXPLICIT_PALLET_PI_PROFILE_REQUIRED');
 requireValue(finite(o.fork_top_m)&&Math.abs(o.fork_top_m-.7)<=EPS&&finite(o.extension_m)&&Math.abs(o.extension_m)<=EPS,'HIGH_RETRACTED_TRAVEL_REQUIRED');
 o.vehicle.updateWorldMatrix(true,true);o.cargo.updateWorldMatrix(true,true);unit(o.vehicle.matrixWorld);unit(o.cargo.matrixWorld);
 const inverse=o.vehicle.matrixWorld.clone().invert(),frame=unit(inverse.clone().multiply(o.cargo.matrixWorld));
 requireValue(frame.position.distanceTo(new THREE.Vector3(0,.7,1))<=EPS&&1-Math.abs(frame.quaternion.dot(new THREE.Quaternion(0,1,0,0)))<1e-10,'PALLET_PI_TRAVEL_FRAME_MISMATCH');
 const inspect=(root:THREE.Object3D,bounds:typeof bodyBounds)=>{let vertices=0,maximum=0;let worst:{node:string;vertex:number;axis:number;point:XYZ}|null=null;const p=new THREE.Vector3();
  root.traverse(node=>{if(!(node instanceof THREE.Mesh))return;const positions=node.geometry.getAttribute('position');for(let i=0;i<positions.count;i++){node.getVertexPosition(i,p);p.applyMatrix4(node.matrixWorld).applyMatrix4(inverse);const a=p.toArray();for(let axis=0;axis<3;axis++){const excess=Math.max(bounds.min[axis]-a[axis],a[axis]-bounds.max[axis],0);if(excess>maximum){maximum=excess;worst={node:node.name,vertex:i,axis,point:[...a] as XYZ};}}vertices++;}});
  requireValue(vertices>0,'NO_NATIVE_ENVELOPE_VERTICES');return{vertices,maximum_nominal_bounds_excess_m:maximum,within_existing_native_tolerance:maximum<=EPS,worst};};
 const body=inspect(o.vehicle,bodyBounds),cargo=inspect(o.cargo,palletBounds);
 const d=o.driver,driver=d?d.actorId==='F01'&&d.role==='forklift_driver'&&!d.disposed&&[d.seat_error_m,d.grip_error_m.L,d.grip_error_m.R,d.sole_error_m.L,d.sole_error_m.R].every(v=>finite(v)&&v>=0&&v<=EPS):false;
 return{passed:body.within_existing_native_tolerance&&cargo.within_existing_native_tolerance&&driver,profile_id:HEAVY_INBOUND_PALLET_PI_PROFILE,body,cargo,driver_contacts_passed:driver,gross_mass_kg:455,travel_rating_passed:455<=1000,extended_rating_passed:455<=800,single_fork_share_kg:227.5,native_tolerance_m:EPS,old_C08_modified:false,source_kind:'visual_fixture',engine_operation:false,operational_admission:false};
}
