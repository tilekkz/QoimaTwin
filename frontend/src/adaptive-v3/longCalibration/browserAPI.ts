import * as THREE from 'three';
import type {WorkerInstance} from '../workerRoles';
import {applyWorkerRole} from '../workerRoles';
import {rigSignature,createWorldFrameGuard} from './rig';
import {RIG_PINS} from './rig-pins';
import {validateWorkerRegistry, workerById} from '../workerRegistry';
import {validateWorkerProfiles, checkVisualWorkerCapability} from '../workerProfiles';
import {bindSeatedDriver, validateSeatedDriverPose} from '../seatedDriver';
import {PINNED} from './pinned-data';
import {bytesHash, digest, freeze, requireThat, nodes, unique, geometryIdentity, controlsIdentity, capture, restore} from './native';
import {canonical,geometryJSON,controlsJSON} from './native';
import {webHash} from './hash';
import {createGeometryGuard,createLiveGuard,binaryGeometryHash,binaryGeometryBytes,validateDrawRanges,createNodeReferenceGuard} from './identity';
import {BINARY_PINS} from './binary-pins';

export type Vec3 = readonly [number,number,number];
export type Quat = readonly [number,number,number,number];
export type WheelId = 'front_L'|'front_R'|'rear_L'|'rear_R';
export interface WheelDefinition { readonly id:WheelId; readonly joint:string; readonly parent:string; readonly axle_vehicle_m:Vec3; readonly axis:Vec3; readonly radius_m:number; readonly sign:1; }
export interface Crossing { readonly id:'IN_W_BULK'|'OUT_E_B2B'; readonly actor_id:'F01'|'F02'; readonly vehicle_id:'FL01'|'FL02'; readonly duration_s:number; readonly path_length_m:number; readonly gate_travel_m:readonly [number,number]; readonly origin_m:Vec3; readonly inward:Vec3; readonly heading:Quat; readonly forward_projection:number; }
export interface LongTimeline { readonly schema_id:'qoima.long-straight-calibration.v1'; readonly source_kind:'visual_fixture'; readonly engine_operation:false; readonly runtime_scene_joined:false; readonly source_pickup_executed:false; readonly wheels:readonly WheelDefinition[]; readonly crossings:readonly Crossing[]; readonly [key:string]:unknown; }
export interface ModelDescriptor { readonly schema_id:'qoima.long-native-descriptor.v1'; readonly asset_sha256:string; readonly geometry_sha256:string; readonly controls_sha256:string; readonly root_node:'forklift_root'; readonly wheels:readonly WheelDefinition[]; readonly [key:string]:unknown; }
declare const verifiedModel: unique symbol;
declare const validatedTimeline: unique symbol;
export interface VerifiedLongModel { readonly [verifiedModel]:true; readonly root:THREE.Object3D; readonly descriptor:ModelDescriptor; }
export type ValidatedTimeline = LongTimeline & {readonly [validatedTimeline]:true};
const models = new WeakSet<object>(), timelines = new WeakSet<object>();
const sourceTokens=new WeakSet<object>();
const activeRoots = new WeakSet<THREE.Object3D>(), activeActors = new WeakSet<WorkerInstance>();
const activeIds = new Set<string>();

/** Byte identity is separate from loader registration. No production loader is registered here. */
export function verifyLongModel(root:THREE.Object3D, assetBytes:Uint8Array, descriptor:unknown):VerifiedLongModel {
  validateDrawRanges([root]);
  requireThat(digest(descriptor) === PINNED.descriptor_sha256, 'Descriptor identity mismatch');
  const d = descriptor as ModelDescriptor;
  requireThat(bytesHash(assetBytes) === d.asset_sha256, 'Wrong LONG asset/variant hash');
  requireThat(geometryIdentity(root) === d.geometry_sha256, 'Native geometry identity mismatch');
  requireThat(bytesHash(binaryGeometryBytes([root]))===BINARY_PINS.model,'Native compact binary identity mismatch');
  requireThat(controlsIdentity(root) === d.controls_sha256, 'Native control/hierarchy identity mismatch');
  const result = Object.freeze({root,descriptor:freeze(structuredClone(d))}) as VerifiedLongModel;
  models.add(result); return result;
}
export function validateLongTimeline(value:unknown):ValidatedTimeline {
  requireThat(digest(value) === PINNED.timeline_sha256, 'Timeline scope/path/axis/radius/sign identity mismatch');
  const result = freeze(structuredClone(value)) as ValidatedTimeline; timelines.add(result); return result;
}
function crossingFor(t:ValidatedTimeline, id:Crossing['id']):Crossing {
  requireThat(timelines.has(t), 'Timeline must be validated');
  const c=t.crossings.find(c=>c.id===id); requireThat(c,'Unknown crossing'); return c;
}
export interface AbsoluteSample { readonly crossing_id:Crossing['id']; readonly distance_m:number; readonly seconds:number; readonly position:Vec3; readonly heading:Quat; readonly signed_forward_distance_m:number; readonly wheels:readonly {readonly id:WheelId;readonly angle_rad:number;readonly quaternion:Quat}[]; }
/** Pure absolute oracle. Never reads live transforms or accumulates frame deltas. */
export function sampleDistance(t:ValidatedTimeline, id:Crossing['id'], distance:number):AbsoluteSample {
  const c=crossingFor(t,id);
  requireThat(Number.isFinite(distance) && distance>=0 && distance<=c.path_length_m,'Distance outside crossing');
  const fraction=distance/c.path_length_m, w=c.gate_travel_m[0]+fraction*(c.gate_travel_m[1]-c.gate_travel_m[0]);
  const signed=distance*c.forward_projection;
  return freeze({crossing_id:id,distance_m:distance,seconds:fraction*c.duration_s,position:c.origin_m.map((x,i)=>x+c.inward[i]*w) as unknown as Vec3,heading:[...c.heading] as unknown as Quat,signed_forward_distance_m:signed,wheels:t.wheels.map(w=>({id:w.id,angle_rad:w.sign*signed/w.radius_m,quaternion:new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...w.axis),w.sign*signed/w.radius_m).toArray() as Quat}))});
}
export function sampleTime(t:ValidatedTimeline, id:Crossing['id'], seconds:number):AbsoluteSample {
  const c=crossingFor(t,id);
  requireThat(Number.isFinite(seconds) && seconds>=0 && seconds<=c.duration_s,'Time outside crossing');
  return sampleDistance(t,id,c.path_length_m*(seconds/c.duration_s));
}
export interface NativeSources { readonly registry_json:string; readonly profiles_json:string; readonly pose_json:string; readonly worker_asset_sha256:string; readonly forklift_asset_sha256:string; readonly pose_spec_sha256:string; }
export interface CalibrationInput {
  readonly model:VerifiedLongModel; readonly timeline:ValidatedTimeline; readonly crossing_id:Crossing['id'];
  /** Instance IDs are the actual canonical registry pair, not aliases. */
  readonly actor:WorkerInstance; readonly actor_instance_id:'F01'|'F02'; readonly vehicle_instance_id:'FL01'|'FL02'; readonly sources:VerifiedLongSources;
  readonly source_kind:'visual_fixture'; readonly engine_operation:false; readonly runtime_scene_joined:false; readonly source_pickup_executed:false;
}
export interface LongCalibration {
  seekTime(seconds:number):AbsoluteSample; seekDistance(distance:number):AbsoluteSample;
  /** apply accepts only oracle-equivalent samples, including unwrapped phases. */
  apply(sample:AbsoluteSample):AbsoluteSample;
  cancel():void; dispose():void; readonly disposed:boolean;
  seatedSnapshot():ReturnType<ReturnType<typeof bindSeatedDriver>['snapshot']>;
}
function validateSources(s:NativeSources, actor:WorkerInstance, c:Crossing) {
  // Canonical same-role call checks the factory's private WeakMap before its
  // inert return. Structural wrappers cannot satisfy issuance provenance.
  applyWorkerRole(actor,actor.role);
  requireThat(sourceTokens.has(s), 'Sources require async byte verification');
  requireThat(bytesHash(s.registry_json)===PINNED.registry_sha256 && bytesHash(s.profiles_json)===PINNED.profiles_sha256 && bytesHash(s.pose_json)===PINNED.pose_sha256,'Registry/profile/pose source hash mismatch');
  requireThat(s.worker_asset_sha256===PINNED.worker_sha256 && s.forklift_asset_sha256===PINNED.forklift_sha256 && s.pose_spec_sha256===PINNED.pose_spec_sha256,'Native source loader hash mismatch');
  const registry=validateWorkerRegistry(JSON.parse(s.registry_json));
  const profiles=validateWorkerProfiles(JSON.parse(s.profiles_json),registry,PINNED.registry_sha256);
  const pose=validateSeatedDriverPose(JSON.parse(s.pose_json));
  requireThat(pose.worker_glb_sha256===s.worker_asset_sha256,'Pose worker asset mismatch');
  requireThat(registry.actor_count===24 && registry.vehicle_count===2 && workerById(registry,c.actor_id).assigned_vehicle_id===c.vehicle_id,'Original pair/count mismatch');
  requireThat(actor.actorId===c.actor_id && actor.root.userData.actorId===c.actor_id && actor.role==='forklift_driver' && !actor.disposed,'Actor identity/role mismatch');
  requireThat(rigSignature(actor.root)===RIG_PINS[c.actor_id],'Native actor rig/anchor identity mismatch');
  requireThat(geometryIdentity(actor.root)===PINNED.actor_geometry[c.actor_id],'Native worker geometry identity mismatch');
  requireThat(bytesHash(binaryGeometryBytes([actor.root]))===BINARY_PINS.actors[c.actor_id],'Native worker compact byte identity mismatch');
  requireThat(checkVisualWorkerCapability(profiles,c.actor_id,{source_kind:'visual_fixture',engine_operation:false,target_role:'forklift_driver',handler:'forklift',cargo_mass_kg:240,vehicle_id:c.vehicle_id,required_equipment:['forklift']}).eligible,'Source capability rejected');
  return pose;
}
function validateNative(root:THREE.Object3D, actor:WorkerInstance, d:ModelDescriptor, pose:ReturnType<typeof validateSeatedDriverPose>) {
  requireThat(geometryIdentity(root)===d.geometry_sha256 && controlsIdentity(root)===d.controls_sha256,'Model changed after verification');
  requireThat(bytesHash(binaryGeometryBytes([root]))===BINARY_PINS.model,'Model compact binary identity changed after verification');
  const vehicle=unique(root,d.root_node);
  requireThat(!nodes(root).includes(actor.root) && !nodes(actor.root).includes(root),'Overlapping model and actor');
  for(let n:THREE.Object3D|null=vehicle;n;n=n.parent) requireThat(n.scale.toArray().every(x=>x===1) && (n===vehicle || (n.position.lengthSq()===0 && n.quaternion.equals(new THREE.Quaternion()))),'Nonidentity fixture ancestor');
  for(const w of d.wheels) {
    const joint=unique(vehicle,w.joint); requireThat(joint.parent===unique(vehicle,w.parent),'Wrong wheel parent');
    requireThat(joint.userData.rotation_axis_runtime==='X' && joint.userData.wheel_radius_m===w.radius_m && w.axis.join(',')==='1,0,0','Native wheel axis/radius metadata mismatch');
    const axle=vehicle.worldToLocal(joint.getWorldPosition(new THREE.Vector3()));
    requireThat(axle.distanceTo(new THREE.Vector3(...w.axle_vehicle_m))<1e-12 && joint.quaternion.equals(new THREE.Quaternion()) && joint.scale.toArray().every(x=>x===1),'Wrong native axle/baseline');
  }
  for(const name of ['anchor_driver_seat','anchor_footrest_L','anchor_footrest_R','anchor_steering_grip_L','anchor_steering_grip_R']) unique(vehicle,name);
  for(const name of [...Object.keys(pose.driver.jointEulerXYZ),'anchor_seat_contact','anchor_hand_grip_L','anchor_hand_grip_R','anchor_foot_floor_L','anchor_foot_floor_R']) unique(actor.root,name);
  requireThat(nodes(root).concat(nodes(actor.root)).every(n=>n.matrixAutoUpdate && n.matrixWorldAutoUpdate && n.scale.toArray().every(x=>Number.isFinite(x))) && actor.root.scale.toArray().every(x=>x===1),'Unsupported matrix mode/actor scale');
  return vehicle;
}
/** PRE-HELD visual calibration ownership only; no jobs, pickup or source workflow. */
export function createLongCalibration(input:CalibrationInput):LongCalibration {
  requireThat(input.source_kind==='visual_fixture' && input.engine_operation===false && input.runtime_scene_joined===false && input.source_pickup_executed===false,'Unsupported operation scope');
  requireThat(models.has(input.model),'Model must be verified');
  const {root,descriptor}=input.model, actor=input.actor, c=crossingFor(input.timeline,input.crossing_id);
  validateDrawRanges([root,actor.root]);
  requireThat(input.actor_instance_id===c.actor_id && input.vehicle_instance_id===c.vehicle_id,'Wrong instance IDs');
  const keys=['actor:'+c.actor_id,'vehicle:'+c.vehicle_id];
  requireThat(!activeRoots.has(root) && !activeActors.has(actor) && keys.every(k=>!activeIds.has(k)),'Calibration instance conflict');
  const pose=validateSources(input.sources,actor,c), frameCheck=createWorldFrameGuard(root), vehicle=validateNative(root,actor,descriptor,pose);
  const baseline=capture([root,actor.root]), roots=[root,actor.root];
  let disposed=false, busy=true, live:ReturnType<typeof createLiveGuard>|undefined, seated:ReturnType<typeof bindSeatedDriver>|undefined;
  const geometryCheck=createGeometryGuard(roots);
  function enter(){requireThat(!disposed && !busy,'Disposed/reentrant calibration');busy=true;}
  function current(){ frameCheck();requireThat(!actor.disposed && actor.role==='forklift_driver','Concurrent actor role/disposal mutation'); live!.check();geometryCheck(); }
  class ContactError extends Error {}
  function checkedSeat(){const s=seated!.snapshot();const errors=[s.seat_error_m,...Object.values(s.grip_error_m),...Object.values(s.sole_error_m)];if(!errors.every(e=>Number.isFinite(e)&&e<2e-5))throw new ContactError('Native driver contact exceeds established 20um threshold');return s;}
  function releaseOwnership(){activeRoots.delete(root);activeActors.delete(actor);keys.forEach(k=>activeIds.delete(k));}
  function abortInvalidContacts(){try{seated?.release();}finally{restore(baseline);disposed=true;releaseOwnership();}}
  function cleanup(){
    if(disposed)return; requireThat(!busy,'Reentrant cleanup'); busy=true;
    try { try {seated?.release();} finally {restore(baseline);disposed=true;} }
    finally { activeRoots.delete(root);activeActors.delete(actor);keys.forEach(k=>activeIds.delete(k));busy=false; }
  }
  activeRoots.add(root);activeActors.add(actor);keys.forEach(k=>activeIds.add(k));
  try {
    for(const a of PINNED.attachments) { const node=unique(root,a.node); unique(vehicle,a.parent).add(node);node.position.fromArray(a.p);node.quaternion.fromArray(a.q);node.scale.fromArray(a.scale); }
    seated=bindSeatedDriver(vehicle,actor,pose);checkedSeat(); root.updateMatrixWorld(true); live=createLiveGuard(roots); busy=false;
  } catch(error) { seated?.release();restore(baseline);activeRoots.delete(root);activeActors.delete(actor);keys.forEach(k=>activeIds.delete(k));throw error; }
  function apply(sample:AbsoluteSample):AbsoluteSample {
    // All input and live-state checks precede the first mutating write.
    enter();
    try {
      const expected=sampleDistance(input.timeline,c.id,sample.distance_m);
      requireThat(canonical(sample)===canonical(expected),'Sample differs from absolute oracle');
      current(); const rollback=capture(roots);
      try {
        vehicle.position.fromArray(expected.position);vehicle.quaternion.fromArray(expected.heading);
        for(const w of expected.wheels) unique(vehicle,'joint__wheel_'+w.id).quaternion.fromArray(w.quaternion);
        seated!.reset();checkedSeat();root.updateMatrixWorld(true);live!.refreshTransforms();return expected;
      } catch(error) {if(error instanceof ContactError)abortInvalidContacts();else{restore(rollback);live!.refreshTransforms();}throw error;}
    } finally {busy=false;}
  }
  return Object.freeze({apply,seekTime:(s:number)=>apply(sampleTime(input.timeline,c.id,s)),seekDistance:(d:number)=>apply(sampleDistance(input.timeline,c.id,d)),cancel:cleanup,dispose:cleanup,get disposed(){return disposed;},seatedSnapshot(){enter();try{current();return checkedSeat();}catch(error){if(error instanceof ContactError)abortInvalidContacts();throw error;}finally{busy=false;}}});
}

/** Browser preparation copies bytes and verifies WebCrypto SHA-256 before issuing a token.
 * The legacy synchronous verifier above is a slow correctness-boundary helper only. */
export async function prepareLongModel(root:THREE.Object3D,assetBytes:Uint8Array,descriptor:unknown):Promise<VerifiedLongModel>{
  validateDrawRanges([root]);
  const d=freeze(structuredClone(descriptor)) as ModelDescriptor;
  const references=createNodeReferenceGuard([root]),check=createGeometryGuard([root]),control=controlsJSON(root);
  const hashes=await Promise.all([webHash(canonical(d)),webHash(assetBytes),webHash(geometryJSON(root)),webHash(control),binaryGeometryHash([root])]);
  requireThat(hashes[0]===PINNED.descriptor_sha256,'Descriptor identity mismatch');
  requireThat(hashes[1]===d.asset_sha256,'Wrong LONG asset/variant hash');
  requireThat(hashes[2]===d.geometry_sha256,'Native geometry identity mismatch');
  requireThat(hashes[3]===d.controls_sha256,'Native control/hierarchy identity mismatch');
  requireThat(hashes[4]===BINARY_PINS.model,'Compact binary geometry identity mismatch');
  references();check();requireThat(controlsJSON(root)===control,'Model changed during async verification');
  const result=Object.freeze({root,descriptor:d}) as VerifiedLongModel;models.add(result);return result;
}
export interface SourceBytes extends NativeSources {readonly worker_bytes:Uint8Array;readonly forklift_bytes:Uint8Array;readonly pose_spec_bytes:Uint8Array;}
declare const verifiedSources:unique symbol;
export type VerifiedLongSources=NativeSources&{readonly [verifiedSources]:true};
export async function prepareLongSources(value:SourceBytes):Promise<VerifiedLongSources>{
  const s=Object.freeze({registry_json:value.registry_json,profiles_json:value.profiles_json,pose_json:value.pose_json,worker_asset_sha256:value.worker_asset_sha256,forklift_asset_sha256:value.forklift_asset_sha256,pose_spec_sha256:value.pose_spec_sha256});
  const expected=[PINNED.registry_sha256,PINNED.profiles_sha256,PINNED.pose_sha256,PINNED.worker_sha256,PINNED.forklift_sha256,PINNED.pose_spec_sha256];
  const actual=await Promise.all([s.registry_json,s.profiles_json,s.pose_json,value.worker_bytes,value.forklift_bytes,value.pose_spec_bytes].map(webHash));
  requireThat(actual.every((h,i)=>h===expected[i]),'Source JSON/asset/spec bytes mismatch');
  requireThat(s.worker_asset_sha256===actual[3]&&s.forklift_asset_sha256===actual[4]&&s.pose_spec_sha256===actual[5],'Source receipt mismatch');
  sourceTokens.add(s);return s as VerifiedLongSources;
}
