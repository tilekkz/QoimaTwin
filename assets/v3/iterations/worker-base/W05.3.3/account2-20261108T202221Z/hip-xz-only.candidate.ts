import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {applyWorkerRole,type WorkerInstance} from './workerRoles';
import {isWarehouseActionCatalogue,type WarehouseActionCatalogue} from './warehouseActionTimeline';
import {createWarehouseRouter,type RoutePolicy} from './warehouseRouting';
import {deriveNativeWorkerGaitRig,compileNativeWorkerGait,type WorkerGaitPose} from './warehouseWorkerGait';
import {createWarehouseDynamicCargoBinding} from './warehouseDynamicCargoBinding';
import type {CargoMeshPart} from './warehouseCargoGeometry';
import type {BoundCargo} from './warehouseCargo';
import type {WarehouseBundle,XYZ} from './warehouseTypes';

const POSE_PATH='frontend/public/data/v3/worker-base-carry-pose.json';
const POSE_SHA='f33bdb63db8fc78af68af173926a0a59267eda9f83b484a98e71ec4f375bac7b';
const REPORT_PATH='docs/adaptive-v3/evidence/W05.3.1-checks.json';
const REPORT_SHA='c589584d503575a855c25060c38e2aa881e0cde849a66114d6838fa8b14b75ea';
const DYNAMIC_REPORT_PATH='docs/adaptive-v3/evidence/W05.3.4-checks.json';
const DYNAMIC_REPORT_SHA='2c2b2e6024357cfd849b55d938882c5ac41947c041a5ed0d2987d01d41c5c443';
const HU='v3:HU:initial:DEMO_067:01',EPS=2e-6;
const ARC_IDS=['v3:ped-edge:0009:r','v3:ped-edge:0006:r'];
const NODE_IDS=['v3:gateway:SMALL_W','v3:ped-node:00600:04900','v3:ped-node:00600:03800'];
const POINTS:XYZ[]=[[10.75,0,49],[6,0,49],[6,0,38]];
const ARM_NAMES=['L','R'].flatMap(side=>['upper_arm','forearm','palm_roll','hand'].map(j=>'joint__'+j+'_'+side));
const LEG_NAMES=['L','R'].flatMap(side=>['thigh','shin','foot'].map(j=>'joint__'+j+'_'+side));
const flags={source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,physical_join:false as const,runtime_scene_joined:false as const,source_pickup_executed:false as const,calibration_only:true as const,generic_loaded_pedestrian_mode_admitted:false as const,completed_jobs:0 as const};
const actorOwners=new WeakSet<WorkerInstance>(),meshOwners=new WeakSet<THREE.InstancedMesh>();
const axisY=new THREE.Vector3(0,1,0),unit=new THREE.Vector3(1,1,1);
const sha=async(b:Uint8Array)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b as BufferSource))].map(x=>x.toString(16).padStart(2,'0')).join('');
const finite=(x:unknown):x is number=>typeof x==='number'&&Number.isFinite(x);
const tuple=(v:THREE.Vector3)=>v.toArray() as XYZ;
function freeze<T>(v:T):T{if(v&&typeof v==='object'&&!Object.isFrozen(v)){for(const c of Object.values(v))freeze(c);Object.freeze(v);}return v;}
export class WarehouseLoadedWalkError extends Error{constructor(readonly reason:string,readonly details:Record<string,unknown>={}){super(reason);this.name='WarehouseLoadedWalkError';}}
function requireValue(v:unknown,reason:string,details:Record<string,unknown>={}):asserts v{if(!v)throw new WarehouseLoadedWalkError(reason,details);}
type CarryPose={actor_id:string;worker_asset:string;worker_root:{position:XYZ;yaw_rad:number;scale:XYZ};cargo:{handling_unit_ref:string;position_m:XYZ;yaw_rad:number;scale:XYZ};jointEulerXYZ:Record<string,XYZ>;solved_reference_points:{side:'L'|'R';local_hand_m:XYZ;target_worker_m:XYZ}[];source_hashes:Record<string,string>};
type NodeState={node:THREE.Object3D;parent:THREE.Object3D|null;position:THREE.Vector3;quaternion:THREE.Quaternion;scale:THREE.Vector3;auto:boolean;worldAuto:boolean};
type MeshState={part:CargoMeshPart;original:Float32Array;last:Float32Array;world:THREE.Matrix4;local:NodeState};
type Options={calibration_fixture:true;bundle:WarehouseBundle;catalogue:WarehouseActionCatalogue;policy:RoutePolicy;actor:WorkerInstance;bound:BoundCargo;parts:CargoMeshPart[];cargoParts:Map<string,readonly CargoMeshPart[]>;readSource:(path:string)=>Promise<Uint8Array>};
const capture=(node:THREE.Object3D):NodeState=>({node,parent:node.parent,position:node.position.clone(),quaternion:node.quaternion.clone(),scale:node.scale.clone(),auto:node.matrixAutoUpdate,worldAuto:node.matrixWorldAutoUpdate});
const same=(s:NodeState)=>s.node.parent===s.parent&&s.node.position.equals(s.position)&&s.node.quaternion.equals(s.quaternion)&&s.node.scale.equals(s.scale)&&s.node.matrixAutoUpdate===s.auto&&s.node.matrixWorldAutoUpdate===s.worldAuto;
function restore(rows:NodeState[]){for(const s of rows){s.node.position.copy(s.position);s.node.quaternion.copy(s.quaternion);s.node.scale.copy(s.scale);}}
function disposeTemplate(root:THREE.Object3D){const g=new Set<THREE.BufferGeometry>(),m=new Set<THREE.Material>();root.traverse(n=>{if(n instanceof THREE.Mesh){g.add(n.geometry);for(const material of Array.isArray(n.material)?n.material:[n.material])m.add(material);}});for(const v of g)v.dispose();for(const v of m)v.dispose();root.clear();}
function nativeTriangles(part:CargoMeshPart){part.mesh.updateWorldMatrix(true,false);const instance=new THREE.Matrix4();part.mesh.getMatrixAt(part.index,instance);const matrix=part.mesh.matrixWorld.clone().multiply(instance),g=part.mesh.geometry,p=g.getAttribute('position'),ix=g.index,out:THREE.Triangle[]=[];for(let i=0;i<(ix?.count??p.count);i+=3)out.push(new THREE.Triangle(...[0,1,2].map(j=>new THREE.Vector3().fromBufferAttribute(p,ix?ix.getX(i+j):i+j).applyMatrix4(matrix)) as [THREE.Vector3,THREE.Vector3,THREE.Vector3]));return {triangles:out,matrix};}

/** Carry-only native hip X/Z, shin X with source turn twist Y; no source-target changes. */
function solveLoadedLegs(rig:ReturnType<typeof deriveNativeWorkerGaitRig>,p:WorkerGaitPose):WorkerGaitPose{
 if(p.at_s===0||p.stage==='route_end')return p;
 const rotations={...p.joint_rotations};let maximumError=0;
 for(const leg of rig.legs){
  const side=leg.side,target=p.feet[side],wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
  const desired=new THREE.Quaternion().setFromAxisAngle(axisY,wrap(target.yaw_rad-p.yaw_rad));
  const goal=new THREE.Vector3(...target.point).sub(new THREE.Vector3(...p.root_world)).applyAxisAngle(axisY,-p.yaw_rad).sub(new THREE.Vector3(...leg.sole).applyQuaternion(desired)).sub(new THREE.Vector3(...leg.hip));
  const names=['joint__thigh_'+side,'joint__shin_'+side,'joint__foot_'+side];
  const old1=new THREE.Euler().setFromQuaternion(new THREE.Quaternion(...p.joint_rotations[names[0]]),'XYZ'),old2=new THREE.Euler().setFromQuaternion(new THREE.Quaternion(...p.joint_rotations[names[1]]),'XYZ');
  const twist=wrap(target.yaw_rad-p.yaw_rad)*.30,values=[old1.x,0,old2.x],a=new THREE.Vector3(...leg.a),b=new THREE.Vector3(...leg.b),q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();
  function point(v:number[]){q1.setFromEuler(new THREE.Euler(v[0],0,v[1],'XYZ'));q2.setFromEuler(new THREE.Euler(v[2],twist,0,'XYZ'));q12.copy(q1).multiply(q2);return a.clone().applyQuaternion(q1).add(b.clone().applyQuaternion(q12));}
  for(let i=0;i<50;i++){
   const current=point(values),error=goal.clone().sub(current);if(error.length()<1e-11)break;
   const columns=values.map((_,j)=>{const v=[...values];v[j]+=1e-6;return point(v).sub(current).multiplyScalar(1e6);});
   const jac=new THREE.Matrix3().set(columns[0].x,columns[1].x,columns[2].x,columns[0].y,columns[1].y,columns[2].y,columns[0].z,columns[1].z,columns[2].z);
   requireValue(Math.abs(jac.determinant())>1e-15,'LOADED_LEG_SINGULAR',{at_s:p.at_s,side,values});
   error.applyMatrix3(jac.invert());for(let j=0;j<3;j++)values[j]+=THREE.MathUtils.clamp(error.getComponent(j),-.2,.2);
  }
  const error=point(values).distanceTo(goal);requireValue(error<=2e-7,'LOADED_LEG_UNREACHABLE',{at_s:p.at_s,side,error,values});maximumError=Math.max(maximumError,error);
  const angles=[new THREE.Euler(values[0],0,values[1],'XYZ'),new THREE.Euler(values[2],twist,0,'XYZ'),new THREE.Euler().setFromQuaternion(q12.clone().invert().multiply(desired),'XYZ')];
  for(let i=0;i<3;i++){const ranges=rig.nodes.find(n=>n.name===names[i])!.limits!,v=[angles[i].x,angles[i].y,angles[i].z];requireValue(v.every((x,k)=>x>=ranges[k][0]-1e-8&&x<=ranges[k][1]+1e-8),'LOADED_LEG_JOINT_LIMIT',{at_s:p.at_s,side,joint:names[i],v,ranges});rotations[names[i]]=new THREE.Quaternion().setFromEuler(angles[i]).toArray();}
 }
 return {...p,joint_rotations:rotations,maximum_IK_error_m:maximumError};
}

/** Prescribed pre-held calibration only; no Scene/global action lease or source-pickup admission. */
export async function createWarehouseLoadedWalkCalibration(o:Options){
 requireValue(o?.calibration_fixture===true,'ISOLATED_CALIBRATION_REQUIRED');
 const {bundle,catalogue,policy,actor,bound,parts,readSource}=o;
 requireValue(isWarehouseActionCatalogue(catalogue,bundle),'INVALID_CATALOGUE');
 requireValue(typeof readSource==='function'&&actor?.actorId==='P02'&&!actor.disposed&&actor.role==='picker'&&actor.root.userData.asset_id==='worker-base','ORIGINAL_P02_BASE_REQUIRED');
 try{applyWorkerRole(actor,actor.role);}catch{throw new WarehouseLoadedWalkError('UNISSUED_ACTOR');}
 requireValue(!actorOwners.has(actor),'ACTOR_BUSY');
 const canonical=bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===HU);
 requireValue(bound?.handling_unit_id===HU&&bound.cargo===canonical&&canonical?.archetype_id==='SMALL_CARTON'&&canonical.quantity_units===24&&canonical.gross_mass_kg===.94&&JSON.stringify(canonical.dimensions_xyz_m)==='[0.32,0.24,0.24]'&&bound.model_scale_factor===1&&bound.destination.kind==='storage_slot'&&bound.destination.slot_id===canonical.location.slot_id,'ORIGINAL_WHOLE_HU_REQUIRED');
 requireValue(o.cargoParts?.get(HU)===parts,'ORIGINAL_CARGO_MAP_REQUIRED');
 requireValue(parts?.length===4&&new Set(parts.map(p=>p.mesh)).size===4,'ORIGINAL_CARGO_PARTS_REQUIRED');
 for(const p of parts)requireValue(p.mesh instanceof THREE.InstancedMesh&&p.mesh.instanceMatrix.array instanceof Float32Array&&Number.isInteger(p.index)&&p.index>=0&&p.index<p.mesh.count&&p.mesh.userData.semanticIds?.[p.index]===HU&&!meshOwners.has(p.mesh),'ORIGINAL_CARGO_INSTANCE_REQUIRED');
 const source_hashes:Record<string,string>={};
 async function source(p:string,expected?:string){let b:Uint8Array;try{b=new Uint8Array(await readSource(p));}catch{throw new WarehouseLoadedWalkError('SOURCE_UNAVAILABLE',{path:p});}const digest=await sha(b!);requireValue(!expected||digest===expected,'SOURCE_HASH_MISMATCH',{path:p,expected,actual:digest});source_hashes[p]=digest;return b!;}
 const pose=JSON.parse(new TextDecoder().decode(await source(POSE_PATH,POSE_SHA))) as CarryPose;
 const report=JSON.parse(new TextDecoder().decode(await source(REPORT_PATH,REPORT_SHA)));
 requireValue(report.passed===true&&report.task_id==='W05.3.1'&&report.lifecycle.negative_cases===38&&report.native_clearance.material_changed_nonadjacent_witnesses.length===0,'STATIC_NATIVE_CALIBRATION_REQUIRED');
 for(const[p,h]of Object.entries(report.input_hashes as Record<string,string>))await source(p,h);
 const dynamicReport=JSON.parse(new TextDecoder().decode(await source(DYNAMIC_REPORT_PATH,DYNAMIC_REPORT_SHA)));
 requireValue(dynamicReport.schema_id==='qoima.W05.3.4.dynamic-cargo-binding-checks.v1'&&dynamicReport.passed===true,'PROVED_DYNAMIC_BINDING_REQUIRED');
 for(const[p,h]of Object.entries(dynamicReport.source_hashes as Record<string,string>))await source(p,h);
 requireValue(pose.actor_id==='P02'&&pose.worker_asset==='worker-base'&&pose.cargo.handling_unit_ref===HU&&JSON.stringify(pose.cargo.position_m)==='[0,0.96,0.52]'&&Object.keys(pose.jointEulerXYZ).sort().join('|')===[...ARM_NAMES].sort().join('|'),'STATIC_POSE_MISMATCH');
 const router=createWarehouseRouter(bundle,policy),route=router.route({source_kind:'visual_fixture',engine_operation:false,mode:'pedestrian',actor_id:'P02',vehicle_id:null,cargo_archetype_id:'SMALL_CARTON',from_node_id:NODE_IDS[0],to_node_id:NODE_IDS[2],service_port_id:null,closed_arc_ids:[]});
 requireValue(route.ok&&route.length_m===15.75&&JSON.stringify(route.arc_ids)===JSON.stringify(ARC_IDS),'CANONICAL_ROUTE_MISMATCH',{route});
 for(let i=0;i<3;i++)requireValue(JSON.stringify(bundle.layout.walk.nodes.find(n=>n.node_id===NODE_IDS[i])?.world_pos)===JSON.stringify(POINTS[i]),'CANONICAL_NODE_MISMATCH');
 const profile=bundle.profiles.profiles.find(p=>p.worker_id==='P02');requireValue(profile?.walk_speed_m_s===1.2&&profile.allowed_handlers.includes('manual'),'SOURCE_PROFILE_MISMATCH');
 const bodyBytes=await source('frontend/public/models/v3/worker-base.glb',pose.source_hashes['frontend/public/models/v3/worker-base.glb']);
 const template=(await new GLTFLoader().parseAsync(bodyBytes.buffer.slice(bodyBytes.byteOffset,bodyBytes.byteOffset+bodyBytes.byteLength) as ArrayBuffer,'')).scene;
 const sourceRoot=template.getObjectByName('worker_base_root');requireValue(sourceRoot,'BASE_RIG_MISSING');
 const nodes=new Map<string,THREE.Object3D>(),original:NodeState[]=[];actor.root.traverse(n=>{original.push(capture(n));if(n!==actor.root&&!n.userData.roleBadge){requireValue(!nodes.has(n.name),'DUPLICATE_NATIVE_NODE');nodes.set(n.name,n);}});
 let rig:ReturnType<typeof deriveNativeWorkerGaitRig>;
 try{
  rig=deriveNativeWorkerGaitRig(sourceRoot!);
  for(const n of rig.nodes){const actual=nodes.get(n.name);requireValue(actual&&actual.position.distanceTo(new THREE.Vector3(...n.position))<2e-8&&actual.quaternion.toArray().every((v,i)=>Math.abs(v-n.quaternion[i])<1e-8)&&actual.scale.distanceTo(new THREE.Vector3(...n.scale))<1e-10,'ACTOR_NOT_AT_SOURCE_REST',{node:n.name});
   if(n.mesh){requireValue(actual instanceof THREE.Mesh,'ACTOR_GEOMETRY_CHANGED');const p=actual.geometry.getAttribute('position'),ix=actual.geometry.index;requireValue(p.count*3===n.mesh.positions.length&&(ix?.count??0)===(n.mesh.indices?.length??0),'ACTOR_GEOMETRY_CHANGED');for(let i=0;i<p.count;i++)requireValue(p.getX(i)===n.mesh.positions[3*i]&&p.getY(i)===n.mesh.positions[3*i+1]&&p.getZ(i)===n.mesh.positions[3*i+2],'ACTOR_GEOMETRY_CHANGED');if(ix)for(let i=0;i<ix.count;i++)requireValue(ix.getX(i)===n.mesh.indices![i],'ACTOR_GEOMETRY_CHANGED');}
  }
 }finally{disposeTemplate(template);}
 const gait=compileNativeWorkerGait(rig!,POINTS,-Math.PI/2,profile!.walk_speed_m_s,bundle.layout.modules.map(m=>m.outer_bounds_world));
 const armQ=Object.fromEntries(ARM_NAMES.map(name=>{const a=pose.jointEulerXYZ[name];requireValue(a?.length===3&&[0,1,2].every(i=>Object.hasOwn(a,i)&&finite(a[i])),'INVALID_STATIC_JOINT');return [name,new THREE.Quaternion().setFromEuler(new THREE.Euler(...a,'XYZ'))];}));
 const meshes:MeshState[]=parts.map(part=>{part.mesh.updateWorldMatrix(true,false);return {part,original:new Float32Array(part.mesh.instanceMatrix.array),last:new Float32Array(part.mesh.instanceMatrix.array),world:part.mesh.matrixWorld.clone(),local:capture(part.mesh)};});
 const ancestors:NodeState[]=[];for(let n=actor.root.parent;n;n=n.parent)ancestors.push(capture(n));
 const parentWorld=actor.root.parent?.matrixWorld.clone()??new THREE.Matrix4();requireValue(actor.root.getWorldScale(new THREE.Vector3()).distanceTo(unit)<1e-8&&original.every(s=>s.auto&&s.worldAuto),'SOURCE_FRAME_NOT_SUPPORTED');
 const main=parts.find(p=>p.mesh.name.endsWith('small-carton__batch_02'));requireValue(main,'MAIN_BODY_PART_REQUIRED');
 const binding=createWarehouseDynamicCargoBinding({handling_unit_id:HU,parts});
 const sourceMainFrame=binding.getSourceFrame(main!),sourceMainInverse=sourceMainFrame.clone().invert();
 o.cargoParts.set(HU,binding.parts);for(const state of meshes)state.last=new Float32Array(state.part.mesh.instanceMatrix.array);
 let lastDelta=new THREE.Matrix4();
 let disposed=false,at=0,lastNodes=original,lastPose:WorkerGaitPose|null=null,lastSnapshot:Record<string,unknown>|null=null,applying=false;
 function live(){requireValue(!disposed&&!actor.disposed&&actor.role==='picker','CALIBRATION_DISPOSED');requireValue(!applying,'REENTRANT_APPLY');requireValue(ancestors.every(same),'ANCESTOR_FRAME_CHANGED');requireValue(lastNodes.every(same),'ACTOR_STATE_CHANGED');requireValue(o.cargoParts.get(HU)===binding.parts,'ACTIVE_CARGO_MAP_CHANGED');for(const s of meshes){requireValue(same(s.local)&&s.part.mesh.matrixWorld.equals(s.world),'CARGO_FRAME_CHANGED');const now=s.part.mesh.instanceMatrix.array;requireValue(now.length===s.last.length&&now.every((v,i)=>v===s.last[i]),'CARGO_BUFFER_CHANGED');}}
 function writeCargo(world:THREE.Matrix4){const delta=world.clone().multiply(sourceMainInverse);binding.applyDelta(delta);lastDelta=delta;}
 function observe(p:WorkerGaitPose){
  actor.root.updateWorldMatrix(true,true);const contactRows=pose.solved_reference_points.map(c=>{const hand=nodes.get('joint__hand_'+c.side)!,point=hand.localToWorld(new THREE.Vector3(...c.local_hand_m));let gap=Infinity,nearest:Record<string,unknown>={};for(const part of binding.parts){const n=nativeTriangles(part);for(let i=0;i<n.triangles.length;i++){const q=n.triangles[i].closestPointToPoint(point,new THREE.Vector3()),d=point.distanceTo(q);if(d<gap){gap=d;nearest={part:part.mesh.name,index:part.index,triangle:i,point_m:tuple(q),matrix_world:n.matrix.toArray()};}}}requireValue(gap<=EPS,'NATIVE_CONTACT_GAP',{at_s:p.at_s,phase:p.stage,side:c.side,gap_m:gap,reference_world_m:tuple(point),nearest});return {side:c.side,point_world_m:tuple(point),gap_m:gap,nearest};});
  const feet=rig!.legs.map(leg=>{const foot=nodes.get('joint__foot_'+leg.side)!,sole=nodes.get('anchor_foot_floor_'+leg.side)!.getWorldPosition(new THREE.Vector3()),bottom=Math.min(...leg.vertices.map(v=>new THREE.Vector3(...v).applyMatrix4(foot.matrixWorld).y)),target=p.feet[leg.side],error=sole.distanceTo(new THREE.Vector3(...target.point)),forward=new THREE.Vector3(0,0,1).transformDirection(foot.matrixWorld),yaw=Math.atan2(forward.x,forward.z),yawError=Math.abs(Math.atan2(Math.sin(yaw-target.yaw_rad),Math.cos(yaw-target.yaw_rad)));requireValue(error<=EPS&&yawError<=EPS&&bottom>=-EPS&&(!target.stance||Math.abs(bottom)<=EPS),'NATIVE_STANCE_VIOLATION',{at_s:p.at_s,side:leg.side,error_m:error,yaw_error_rad:yawError,bottom_y_m:bottom});return {side:leg.side,stance:target.stance,sole_world_m:tuple(sole),target_world_m:target.point,error_m:error,native_bottom_y_m:bottom,yaw_rad:yaw,target_yaw_rad:target.yaw_rad,yaw_error_rad:yawError};});
  return freeze({...flags,at_s:p.at_s,duration_s:gait.duration_s,stage:p.at_s===gait.duration_s?'terminal_hold':p.at_s===0?'static_hold':'loaded_walk',gait_stage:p.stage,actor_id:'P02',handling_unit_id:HU,root_world_m:tuple(actor.root.getWorldPosition(new THREE.Vector3())),yaw_rad:p.yaw_rad,body_drop_m:p.body_drop_m,contacts:contactRows,feet,route_arc_ids:ARC_IDS,ownership_scope:'One isolated calibration owner across static_hold/loaded_walk/terminal_hold; no global Scene lease',foreign_clearance_scope:'Independent current native CPU gate required',source_pickup_executed:false,binding:binding.snapshot(),actual_events:[]});
 }
 function apply(seconds:number){requireValue(finite(seconds),'INVALID_TIME');live();const next=solveLoadedLegs(rig!,gait.sample(seconds)),beforeNodes=lastNodes,beforeDelta=lastDelta.clone(),beforeAt=at,beforePose=lastPose,beforeSnapshot=lastSnapshot;applying=true;
  try{
   const rotations=new Map(ARM_NAMES.map(n=>[n,armQ[n]]));for(const name of LEG_NAMES)rotations.set(name,new THREE.Quaternion(...next.joint_rotations[name]));
   // One composite expected frame; never call the unloaded controller or overwrite its arms later.
   restore(original);actor.root.position.copy(new THREE.Vector3(...next.root_world).applyMatrix4(parentWorld.clone().invert()));const parentQ=actor.root.parent?.getWorldQuaternion(new THREE.Quaternion())??new THREE.Quaternion();actor.root.quaternion.copy(parentQ.invert().multiply(new THREE.Quaternion().setFromAxisAngle(axisY,next.yaw_rad)));for(const[n,q]of rotations)nodes.get(n)!.quaternion.copy(q);actor.root.updateWorldMatrix(true,true);
   const cargoWorld=actor.root.matrixWorld.clone().multiply(new THREE.Matrix4().compose(new THREE.Vector3(...pose.cargo.position_m),new THREE.Quaternion().setFromAxisAngle(axisY,pose.cargo.yaw_rad),unit));writeCargo(cargoWorld);lastSnapshot=observe(next);at=next.at_s;lastPose=next;lastNodes=original.map(s=>capture(s.node));for(const s of meshes)s.last=new Float32Array(s.part.mesh.instanceMatrix.array);return lastSnapshot;
  }catch(e){restore(beforeNodes);binding.applyDelta(beforeDelta);lastDelta=beforeDelta;actor.root.updateWorldMatrix(true,true);at=beforeAt;lastPose=beforePose;lastSnapshot=beforeSnapshot;throw e;}finally{applying=false;}
 }
 function reset(){return apply(0);}
 function snapshot(){if(!disposed)live();return lastSnapshot;}
 function dispose(){if(disposed)return;disposed=true;restore(original);binding.dispose();o.cargoParts.set(HU,parts);actor.root.updateWorldMatrix(true,true);actorOwners.delete(actor);for(const s of meshes)meshOwners.delete(s.part.mesh);}
 actorOwners.add(actor);for(const s of meshes)meshOwners.add(s.part.mesh);
 try{apply(0);}catch(e){dispose();throw e;}
 return Object.freeze({apply,reset,snapshot,dispose,parts:binding.parts,sourceParts:parts,bindingSnapshot:()=>binding.snapshot(),duration_s:gait.duration_s,phases:gait.phases,source_hashes:freeze(source_hashes),route:freeze({...route}),scope:freeze({...flags,calibration_start_is_original_actor_home:false,calibration_setup_is_elapsed_action:false,other_actor_and_HU_count_delta:0})});
}
