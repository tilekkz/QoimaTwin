import * as THREE from 'three';
import {isWarehousePalletTransferPlan,type WarehousePalletTransferPlan} from './warehousePalletTransferPlan';
import type {WarehouseActionCatalogue} from './warehouseActionTimeline';
import type {RoutePolicy} from './warehouseRouting';
import type {WarehouseBundle,XYZ} from './warehouseTypes';
import type {WorkerInstance} from './workerRoles';
import type {bindSeatedDriver} from './seatedDriver';
import type {BoundCargo} from './warehouseCargo';
import type {CargoMeshPart,CargoSupportPart} from './warehouseCargoGeometry';

type SeatedBinding=ReturnType<typeof bindSeatedDriver>;
type Sample=ReturnType<WarehousePalletTransferPlan['sample']>;
export type PalletTransferFrame={source_kind:'visual_fixture';engine_operation:false;physical_join:false;native_geometry_admission_required:true;completed_jobs:0;actual_events:readonly never[];at_s:number;phase_id:string;logical_owner:string;bound:BoundCargo;native_root_matrix:readonly number[];reach_relative_matrix:readonly number[];native_part_root_spread_m:number;mesh_instances:readonly {uuid:string;index:number}[];driver:ReturnType<SeatedBinding['snapshot']>};
export type PalletTransferSceneOptions={bundle:WarehouseBundle;catalogue:WarehouseActionCatalogue;policy:RoutePolicy;plan:WarehousePalletTransferPlan;vehicle:THREE.Object3D;actor:WorkerInstance;seated:SeatedBinding;bound:BoundCargo;parts:CargoMeshPart[];onFrame?:(frame:Readonly<PalletTransferFrame>|null)=>void;invalidate?:()=>void;signal?:AbortSignal};
export class PalletTransferSceneError extends Error {constructor(readonly reason:string,readonly details?:Readonly<Record<string,number>>){super(reason);this.name='PalletTransferSceneError';}}
const EPS=2e-6,up=new THREE.Vector3(0,1,0),ownedVehicles=new WeakSet<THREE.Object3D>(),ownedParts=new WeakMap<THREE.InstancedMesh,Set<number>>();
const issued=new WeakMap<object,{bundle:WarehouseBundle;plan:WarehousePalletTransferPlan}>();
export function isWarehousePalletTransferScene(value:unknown,bundle?:WarehouseBundle,plan?:WarehousePalletTransferPlan):value is ReturnType<typeof createWarehousePalletTransferScene>{if(!value||typeof value!=='object')return false;const binding=issued.get(value);return !!binding&&(bundle===undefined||binding.bundle===bundle)&&(plan===undefined||binding.plan===plan);}
const fail=(reason:string,details?:Readonly<Record<string,number>>):never=>{throw new PalletTransferSceneError(reason,details);};
function freeze<T>(value:T):T{if(value&&typeof value==='object'&&!Object.isFrozen(value)){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}
function finite(matrix:THREE.Matrix4){return matrix.elements.every(Number.isFinite)&&Math.abs(matrix.determinant())>1e-12;}
function frame(matrix:THREE.Matrix4){const position=new THREE.Vector3(),quaternion=new THREE.Quaternion(),scale=new THREE.Vector3();matrix.decompose(position,quaternion,scale);quaternion.normalize();if(!finite(matrix)||scale.toArray().some(n=>Math.abs(n-1)>EPS)||up.clone().applyQuaternion(quaternion).distanceTo(up)>EPS)fail('NON_UNIT_OR_TILTED_FRAME');return {position:position.toArray() as XYZ,yaw_rad:Math.atan2(2*(quaternion.w*quaternion.y+quaternion.x*quaternion.z),1-2*(quaternion.y**2+quaternion.z**2)),quaternion};}
function pose(position:readonly number[],yaw:number){return new THREE.Matrix4().compose(new THREE.Vector3(...position),new THREE.Quaternion().setFromAxisAngle(up,yaw),new THREE.Vector3(1,1,1));}
function sameOrientation(a:THREE.Quaternion,b:THREE.Quaternion){return 1-Math.abs(a.dot(b))<1e-10;}
function descendant(node:THREE.Object3D,ancestor:THREE.Object3D){for(let n:THREE.Object3D|null=node;n;n=n.parent)if(n===ancestor)return true;return false;}
type Local={node:THREE.Object3D;parent:THREE.Object3D|null;position:THREE.Vector3;quaternion:THREE.Quaternion;scale:THREE.Vector3};
const save=(node:THREE.Object3D):Local=>({node,parent:node.parent,position:node.position.clone(),quaternion:node.quaternion.clone(),scale:node.scale.clone()});
function restore(rows:Local[]){for(const r of rows){r.node.position.copy(r.position);r.node.quaternion.copy(r.quaternion);r.node.scale.copy(r.scale);}}
function sameLocal(r:Local){return r.node.parent===r.parent&&r.node.position.equals(r.position)&&r.node.quaternion.equals(r.quaternion)&&r.node.scale.equals(r.scale);}

/** Private Scene-object adapter only: no new native object, timer, stock state or admission. */
export function createWarehousePalletTransferScene(o:PalletTransferSceneOptions){
 const {bundle,catalogue,policy,plan,vehicle,actor,seated,bound,parts}=o;
 if(!bundle||typeof bundle!=='object'||!catalogue||typeof catalogue!=='object'||!policy||typeof policy!=='object'||!isWarehousePalletTransferPlan(plan,bundle,catalogue,policy))fail('INVALID_PLAN');
 if(o.signal?.aborted)fail('ABORTED');
 if(!vehicle?.isObject3D||vehicle.name!=='vehicle__FL02'||ownedVehicles.has(vehicle))fail('INVALID_OR_BUSY_VEHICLE');
 if(!actor||actor.actorId!=='F02'||actor.role!=='forklift_driver'||actor.disposed||actor.root.userData.semanticId!=='F02'||seated?.actor!==actor||!descendant(actor.root,vehicle))fail('INVALID_DRIVER_BINDING');
 if(plan.request.vehicle_id!=='FL02'||plan.request.actor_id!=='F02'||bound?.handling_unit_id!==plan.request.handling_unit_id||bound.cargo!==plan.cargo||bound.model_scale_factor!==1||bound.destination.kind!=='storage_slot'||bound.destination.slot_id!==plan.cargo.location.slot_id)fail('INVALID_CARGO_BINDING');
 if(!Array.isArray(parts)||parts.length===0)fail('MISSING_CARGO_PARTS');
 const originalBound=JSON.stringify(bound),initialSample=plan.sample(0),attach=plan.phases.find(p=>p.phase_id==='source_lift_attached')!.start_s,release=plan.phases.find(p=>p.phase_id==='target_controlled_withdraw')!.start_s;
 const required=['joint__carriage','joint__reach','joint__fork_L','joint__fork_R','joint__rear_steer_L','joint__rear_steer_R','joint__wheel_front_L','joint__wheel_front_R','joint__wheel_rear_L','joint__wheel_rear_R'];
 const joints=new Map(required.map(name=>{const node=vehicle.getObjectByName(name);if(!node||!node.matrixAutoUpdate)fail('MISSING_NATIVE_JOINT:'+name);return [name,node] as const;}));
 const carriage=joints.get('joint__carriage')!,reach=joints.get('joint__reach')!;
 if(!descendant(reach,carriage)||!['L','R'].every(side=>descendant(joints.get('joint__fork_'+side)!,reach)))fail('INVALID_NATIVE_HIERARCHY');
 const original:Local[]=[];vehicle.traverse(n=>{if(!n.matrixAutoUpdate)fail('MANUAL_NATIVE_MATRIX');if(![...n.position.toArray(),...n.quaternion.toArray(),...n.scale.toArray()].every(Number.isFinite)||n.scale.toArray().some(v=>Math.abs(v)<1e-12))fail('INVALID_NATIVE_TRANSFORM');original.push(save(n));});
 const structure=original.map(({node})=>({node,children:[...node.children],visible:node.visible,geometry:node instanceof THREE.Mesh?node.geometry:null,material:node instanceof THREE.Mesh?node.material:null}));
 const bases=new Map(original.map(r=>[r.node,r]));
 vehicle.updateWorldMatrix(true,true);const start=frame(vehicle.matrixWorld),expectedStart=pose(initialSample.body.position,initialSample.body.yaw_rad);
 if(start.position.some((v,i)=>Math.abs(v-initialSample.body.position[i])>EPS)||!sameOrientation(start.quaternion,frame(expectedStart).quaternion)||actor.root.getWorldScale(new THREE.Vector3()).toArray().some(n=>Math.abs(n-1)>EPS))fail('INVALID_START_FRAME');
 const sourceExpected=pose(plan.source_pose.position,plan.source_pose.yaw_rad),sourceFrame=frame(sourceExpected);
 if(bound.position.some((v,i)=>Math.abs(v-sourceFrame.position[i])>EPS)||!sameOrientation(frame(pose(bound.position,bound.yaw_rad)).quaternion,sourceFrame.quaternion))fail('INVALID_CARGO_START');
 const used=new Map<THREE.InstancedMesh,Set<number>>();
 const rows=parts.map(part=>{
  const {mesh,index,sourceMatrix}=part;if(!(mesh instanceof THREE.InstancedMesh)||descendant(mesh,vehicle)||!Number.isInteger(index)||index<0||index>=mesh.count||mesh.userData.semanticKind!=='HU'||mesh.userData.semanticIds?.[index]!==bound.handling_unit_id||!(sourceMatrix instanceof THREE.Matrix4)||!finite(sourceMatrix))fail('INVALID_CARGO_PART');
  const seen=used.get(mesh)??new Set<number>();if(seen.has(index)||ownedParts.get(mesh)?.has(index))fail('DUPLICATE_OR_BUSY_CARGO_PART');seen.add(index);used.set(mesh,seen);
  mesh.updateWorldMatrix(true,false);if(!finite(mesh.matrixWorld))fail('INVALID_CARGO_MESH_FRAME');const matrix=new THREE.Matrix4();mesh.getMatrixAt(index,matrix);
  return {part,mesh,index,sourceRef:sourceMatrix,source:sourceMatrix.clone(),geometry:mesh.geometry,material:mesh.material,attribute:mesh.instanceMatrix,array:mesh.instanceMatrix.array,count:mesh.count,meshLocal:save(mesh),meshWorld:mesh.matrixWorld.clone(),original:matrix.clone(),expected:new Float32Array(mesh.instanceMatrix.array.slice(index*16,index*16+16)),world:mesh.matrixWorld.clone().multiply(matrix),correction:new THREE.Matrix4()};
 });
 const sourceRoot=rows[0].world.clone().multiply(rows[0].source.clone().invert()),nativeStart=frame(sourceRoot);
 if(nativeStart.position.some((v,i)=>Math.abs(v-sourceFrame.position[i])>EPS)||!sameOrientation(nativeStart.quaternion,sourceFrame.quaternion))fail('NATIVE_CARGO_START_MISMATCH');
 function spread(root:THREE.Matrix4,worlds:THREE.Matrix4[]){const p=new THREE.Vector3().setFromMatrixPosition(root);let maximum=0;worlds.forEach((world,i)=>{const r=world.clone().multiply(rows[i].source.clone().invert());maximum=Math.max(maximum,p.distanceTo(new THREE.Vector3().setFromMatrixPosition(r)));if(!sameOrientation(frame(r).quaternion,frame(root).quaternion))fail('INCOHERENT_NATIVE_PARTS');});return maximum;}
 const initialSpread=spread(sourceRoot,rows.map(r=>r.world));if(initialSpread>EPS)fail('INCOHERENT_NATIVE_PARTS',{maximum_spread_m:initialSpread});for(const r of rows)r.correction.copy(sourceRoot).invert().multiply(r.world);
 const forkSupportParts:CargoSupportPart[]=[];for(const side of ['L','R'])joints.get('joint__fork_'+side)!.traverseVisible(n=>{if(n instanceof THREE.Mesh)forkSupportParts.push(Object.freeze({mesh:n}));});if(!forkSupportParts.length)fail('MISSING_NATIVE_FORK_SUPPORT');
 function driver(){const d=seated.snapshot(),errors=[d.seat_error_m,d.grip_error_m?.L,d.grip_error_m?.R,d.sole_error_m?.L,d.sole_error_m?.R];if(d.actorId!=='F02'||d.role!=='forklift_driver'||d.disposed||d.assignment!=='seated_existing_actor'||errors.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>EPS))fail('INVALID_DRIVER_CONTACTS');return d;}
 driver();
 function body(sample:Sample){
  restore(original);const world=pose(sample.body.position,sample.body.yaw_rad);if(vehicle.parent){vehicle.parent.updateWorldMatrix(true,false);world.premultiply(vehicle.parent.matrixWorld.clone().invert());}world.decompose(vehicle.position,vehicle.quaternion,vehicle.scale);
  carriage.position.y=sample.joints.fork_top_m;reach.position.z=bases.get(reach)!.position.z+sample.joints.extension_m;
  for(const [side,sign] of [['L',-1],['R',1]] as const){joints.get('joint__fork_'+side)!.position.x=sign*sample.joints.fork_halfspacing_m;const steer=joints.get('joint__rear_steer_'+side)!;steer.quaternion.copy(bases.get(steer)!.quaternion).multiply(new THREE.Quaternion().setFromAxisAngle(up,sample.joints.rear_steer_rad[side]));for(const axle of ['front','rear'] as const){const wheel=joints.get('joint__wheel_'+axle+'_'+side)!;wheel.quaternion.copy(bases.get(wheel)!.quaternion).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),sample.wheel_angles_rad[`${axle}_${side}`]));}}
  vehicle.updateWorldMatrix(true,true);
 }
 const relative=new THREE.Matrix4(),targetRoot=new THREE.Matrix4();
 try{body(plan.sample(attach));relative.copy(reach.matrixWorld).invert().multiply(sourceRoot);body(plan.sample(release));targetRoot.multiplyMatrices(reach.matrixWorld,relative);const target=frame(targetRoot),expected=frame(pose(plan.target_pose.position,plan.target_pose.yaw_rad));if(target.position.some((v,i)=>Math.abs(v-expected.position[i])>EPS)||!sameOrientation(target.quaternion,expected.quaternion))fail('NATIVE_RELEASE_MISMATCH');}
 finally{restore(original);vehicle.updateWorldMatrix(true,true);}
 let expectedLocal=original.map(r=>save(r.node)),expectedVehicleWorld=vehicle.matrixWorld.clone(),current:Readonly<PalletTransferFrame>|null=null,disposed=false,released=false,busy=false;
 const claim=()=>{ownedVehicles.add(vehicle);for(const r of rows){const set=ownedParts.get(r.mesh)??new Set<number>();set.add(r.index);ownedParts.set(r.mesh,set);}};
 function relinquish(){ownedVehicles.delete(vehicle);for(const r of rows){const set=ownedParts.get(r.mesh);set?.delete(r.index);if(!set?.size)ownedParts.delete(r.mesh);}o.signal?.removeEventListener('abort',abort);}
 function usable(){if(disposed||released)fail('DISPOSED');if(busy)fail('REENTRANT_APPLY');if(o.signal?.aborted)fail('ABORTED');}
 function unchanged(){
  vehicle.updateWorldMatrix(true,true);if(!vehicle.matrixWorld.equals(expectedVehicleWorld))fail('CHANGED_NATIVE_BINDING');
  if(structure.some(r=>r.node.visible!==r.visible||r.node.children.length!==r.children.length||r.children.some((n,i)=>r.node.children[i]!==n)||(r.node instanceof THREE.Mesh&&(r.node.geometry!==r.geometry||r.node.material!==r.material))))fail('CHANGED_NATIVE_BINDING');
  if(actor.disposed||actor.role!=='forklift_driver'||actor.actorId!=='F02'||actor.root.userData.semanticId!=='F02'||seated.actor!==actor||!descendant(actor.root,vehicle)||JSON.stringify(bound)!==originalBound||expectedLocal.some(r=>!sameLocal(r))||parts.length!==rows.length)fail('CHANGED_NATIVE_BINDING');
  rows.forEach((r,i)=>{r.mesh.updateWorldMatrix(true,false);if(parts[i]!==r.part||r.part.mesh!==r.mesh||r.part.index!==r.index||r.part.sourceMatrix!==r.sourceRef||!r.part.sourceMatrix.equals(r.source)||r.mesh.geometry!==r.geometry||r.mesh.material!==r.material||r.mesh.instanceMatrix!==r.attribute||r.mesh.instanceMatrix.array!==r.array||r.mesh.count!==r.count||r.mesh.userData.semanticKind!=='HU'||r.mesh.userData.semanticIds?.[r.index]!==bound.handling_unit_id||!sameLocal(r.meshLocal)||!r.mesh.matrixWorld.equals(r.meshWorld)||r.expected.some((n,i)=>n!==r.array[r.index*16+i]))fail('CHANGED_NATIVE_BINDING');});driver();
 }
 function originalCargo(){for(const r of rows){r.mesh.setMatrixAt(r.index,r.original);r.expected.set(r.original.elements);r.mesh.instanceMatrix.needsUpdate=true;}refreshBounds();}
 function refreshBounds(){for(const mesh of used.keys()){mesh.computeBoundingBox();mesh.computeBoundingSphere();}}
 function worlds(){return rows.map(r=>{const m=new THREE.Matrix4();r.mesh.getMatrixAt(r.index,m);return r.meshWorld.clone().multiply(m);});}
 function capture(sample:Sample):Readonly<PalletTransferFrame>{const matrices=worlds(),root=matrices[0].clone().multiply(rows[0].source.clone().invert()),actual=frame(root);const destination=sample.cargo.logical_owner.startsWith('vehicle:')?{kind:'vehicle' as const,vehicle_id:'FL02',anchor_id:'forks'}:{kind:'storage_slot' as const,slot_id:sample.at_s<release?plan.cargo.location.slot_id:plan.request.destination_slot_id};const binding:BoundCargo={handling_unit_id:bound.handling_unit_id,destination,cargo:bound.cargo,position:actual.position,yaw_rad:actual.yaw_rad,model_scale_factor:1};return freeze({source_kind:'visual_fixture' as const,engine_operation:false as const,physical_join:false as const,native_geometry_admission_required:true as const,completed_jobs:0 as const,actual_events:[] as never[],at_s:sample.at_s,phase_id:sample.phase_id,logical_owner:sample.cargo.logical_owner,bound:binding,native_root_matrix:root.toArray(),reach_relative_matrix:relative.toArray(),native_part_root_spread_m:spread(root,matrices),mesh_instances:rows.map(r=>({uuid:r.mesh.uuid,index:r.index})),driver:driver()});}
 function apply(seconds:number){
  usable();const sample=plan.sample(seconds);unchanged();const previous=current,previousLocal=original.map(r=>save(r.node)),previousMatrices=rows.map(r=>r.expected.slice());busy=true;
  try{
   if(sample.at_s===0){restore(original);vehicle.updateWorldMatrix(true,true);originalCargo();}
   else {body(sample);if(sample.at_s<attach)originalCargo();else {const root=sample.at_s<release?reach.matrixWorld.clone().multiply(relative):targetRoot;for(const r of rows){const world=root.clone().multiply(r.correction),local=r.meshWorld.clone().invert().multiply(world);if(!finite(local))fail('INVALID_NATIVE_MATRIX');r.mesh.setMatrixAt(r.index,local);r.expected.set(r.mesh.instanceMatrix.array.slice(r.index*16,r.index*16+16));r.mesh.instanceMatrix.needsUpdate=true;const actual=r.meshWorld.clone().multiply(new THREE.Matrix4().fromArray(r.expected));if(new THREE.Vector3().setFromMatrixPosition(actual).distanceTo(new THREE.Vector3().setFromMatrixPosition(world))>EPS)fail('INSTANCE_PRECISION_BUDGET');}refreshBounds();}}
   const next=capture(sample);expectedLocal=original.map(r=>save(r.node));expectedVehicleWorld=vehicle.matrixWorld.clone();o.onFrame?.(next);o.invalidate?.();if(o.signal?.aborted)fail('ABORTED');unchanged();current=next;return next;
  }catch(error){restore(previousLocal);vehicle.updateWorldMatrix(true,true);rows.forEach((r,i)=>{r.mesh.setMatrixAt(r.index,new THREE.Matrix4().fromArray(previousMatrices[i]));r.expected.set(previousMatrices[i]);r.mesh.instanceMatrix.needsUpdate=true;});refreshBounds();current=previous;expectedLocal=original.map(r=>save(r.node));expectedVehicleWorld=vehicle.matrixWorld.clone();try{o.onFrame?.(previous);}catch{/* Preserve the original refusal. */}throw error;}
  finally{busy=false;if(o.signal?.aborted)try{dispose();}catch{/* The apply refusal remains primary. */}}
 }
 function reset(){usable();unchanged();restore(original);vehicle.updateWorldMatrix(true,true);originalCargo();expectedLocal=original.map(r=>save(r.node));expectedVehicleWorld=vehicle.matrixWorld.clone();current=null;o.onFrame?.(null);o.invalidate?.();}
 function dispose(){if(disposed||released)return;if(busy)fail('REENTRANT_APPLY');disposed=true;restore(original);vehicle.updateWorldMatrix(true,true);originalCargo();current=null;relinquish();try{o.onFrame?.(null);}finally{o.invalidate?.();}}
 function abort(){if(!busy)try{dispose();}catch{/* Abort always completes native ownership cleanup. */}}
 function releaseAtEnd(){usable();unchanged();if(current?.at_s!==plan.duration_s)fail('TERMINAL_POSE_REQUIRED');released=true;relinquish();return current;}
 claim();o.signal?.addEventListener('abort',abort,{once:true});if(o.signal?.aborted){try{dispose();}catch{/* Preserve the abort refusal. */}fail('ABORTED');}
 const controller={apply,snapshot:()=>current,reset,dispose,releaseAtEnd,forkSupportParts:Object.freeze(forkSupportParts)};issued.set(controller,{bundle,plan});return Object.freeze(controller);
}
