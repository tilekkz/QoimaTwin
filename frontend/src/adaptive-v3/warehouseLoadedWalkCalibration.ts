import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {applyWorkerRole,type WorkerInstance} from './workerRoles';
import {isWarehouseActionCatalogue,type WarehouseActionCatalogue} from './warehouseActionTimeline';
import {createWarehouseRouter,type RoutePolicy} from './warehouseRouting';
import {deriveNativeWorkerGaitRig,compileNativeWorkerGait,type WorkerGaitPose} from './warehouseWorkerGait';
import {createWarehouseDynamicCargoBinding} from './warehouseDynamicCargoBinding';
import {createWarehouseCarryBreathing} from './warehouseCarryBreathing';
import {createWarehouseForearmPronationPose} from './warehouseForearmPronationPose';
import {createWarehousePalmSupport} from './warehousePalmSupport';
import type {CargoMeshPart} from './warehouseCargoGeometry';
import type {BoundCargo} from './warehouseCargo';
import type {WarehouseBundle,XYZ} from './warehouseTypes';

// Work proposal only: SHA is zero until a real candidate is supplied and validated.
const ORIGINAL_HOLD_POSE_PATH='frontend/public/data/v3/worker-base-original-hold-pose.json';
const ORIGINAL_HOLD_POSE_SHA='0aa1247d02914349e841d14c1093ce556b5804640b8c4dc6860be2f7c9959caa';
const ORIGINAL_BODY_SHA='542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163';
const POSE_PATH='frontend/public/data/v3/worker-base-carry-pose.json';
const POSE_SHA='f33bdb63db8fc78af68af173926a0a59267eda9f83b484a98e71ec4f375bac7b';
const LOW_BODY_PATH='frontend/public/models/v3/worker-base-carry-natural.glb';
const LOW_POSE_PATH='frontend/public/data/v3/worker-base-low-close-carry-pose.json';
const CLOSE_POSE_PATH='frontend/public/data/v3/worker-base-close-hold-jointfit-pose.json';
const CLOSE_POSE_SHA='47e7d9c315afb7f23f29304511b65e23764ef856f6017b1fe2603ab88a26cb77';
const CLOSE_BODY_PATH='frontend/public/models/v3/worker-base-close-hold-jointfit.glb';
const VERTICAL_POSE_PATH='frontend/public/data/v3/worker-base-vertical-carry-pose.json';
const VERTICAL_POSE_SHA='0f757a71e6c8686d3a941c876ae4768884142c6c2bc1dc0bea33427e60be5603';
const VERTICAL_BODY_PATH='frontend/public/models/v3/worker-base-vertical-carry.glb';
const LOW_POSE_SHA='8e67cf128bf1b79c9c308ad36a953b2336aff4e7f778fc2425b5f76fbeb4cb7a';
const REPORT_PATH='docs/adaptive-v3/evidence/W05.3.1-checks.json';
const REPORT_SHA='c589584d503575a855c25060c38e2aa881e0cde849a66114d6838fa8b14b75ea';
const DYNAMIC_REPORT_PATH='docs/adaptive-v3/evidence/W05.3.4-checks.json';
const DYNAMIC_REPORT_SHA='2c2b2e6024357cfd849b55d938882c5ac41947c041a5ed0d2987d01d41c5c443';
const HU='v3:HU:initial:DEMO_067:01',EPS=2e-6;
const ARC_IDS=['v3:ped-edge:0009:r','v3:ped-edge:0006:r'];
const NODE_IDS=['v3:gateway:SMALL_W','v3:ped-node:00600:04900','v3:ped-node:00600:03800'];
const POINTS:XYZ[]=[[10.75,0,49],[6,0,49],[6,0,38]];
// Fixed close_hold source-route fit; baseline TS 3c1680f7a14d5e915bbf65a286e07d4a29ac4d3be77118f0e27afa1601885eb8; fit 65fc6c0f7f880a0cc7bc53d7f2098166ae4be71c52f8eba5926f75ed53ac075c.
// Reviewed compiled prototype 8fbb8c5671210ffbe9c0ab2bcf10da665c47f638949d88eb99e60f26e8cffc01; unchanged native limits.
const CLOSE_HOLD_START_STOP_RESERVE:ReadonlyMap<number,number>=new Map<number,number>([[0.35,0.006],[0.8695058841210209,0.006],[7.110551948051947,0.002673442840576172],[7.4912084015932665,0.000952646255493164],[11.53071428571429,0.006],[12.055118709799364,0.0005773515701293945],[27.211071428571433,0.002592807769775391],[27.59559557591493,0.0009188060760498048]]);
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
type CarryPose={actor_id:string;worker_asset:string;worker_model_path?:string;pose_only_forearm_pronation?:{gain:number;law:string;source_meshes:string[]};worker_root:{position:XYZ;yaw_rad:number;scale:XYZ};cargo:{handling_unit_ref:string;position_m:XYZ;yaw_rad:number;scale:XYZ};jointEulerXYZ:Record<string,XYZ>;solved_reference_points:{side:'L'|'R';local_hand_m:XYZ;target_worker_m:XYZ}[];source_hashes:Record<string,string>};
type NodeState={node:THREE.Object3D;parent:THREE.Object3D|null;position:THREE.Vector3;quaternion:THREE.Quaternion;scale:THREE.Vector3;auto:boolean;worldAuto:boolean};
type MeshState={part:CargoMeshPart;original:Float32Array;last:Float32Array;world:THREE.Matrix4;local:NodeState};
type Options={calibration_fixture:true;motion_style?:'source'|'grounded_carry';carry_pose?:'source'|'low_close'|'vertical_90'|'close_hold'|'original_hold';breathing?:boolean;bundle:WarehouseBundle;catalogue:WarehouseActionCatalogue;policy:RoutePolicy;actor:WorkerInstance;bound:BoundCargo;parts:CargoMeshPart[];cargoParts:Map<string,readonly CargoMeshPart[]>;readSource:(path:string)=>Promise<Uint8Array>};
const capture=(node:THREE.Object3D):NodeState=>({node,parent:node.parent,position:node.position.clone(),quaternion:node.quaternion.clone(),scale:node.scale.clone(),auto:node.matrixAutoUpdate,worldAuto:node.matrixWorldAutoUpdate});
const same=(s:NodeState)=>s.node.parent===s.parent&&s.node.position.equals(s.position)&&s.node.quaternion.equals(s.quaternion)&&s.node.scale.equals(s.scale)&&s.node.matrixAutoUpdate===s.auto&&s.node.matrixWorldAutoUpdate===s.worldAuto;
function restore(rows:NodeState[]){for(const s of rows){s.node.position.copy(s.position);s.node.quaternion.copy(s.quaternion);s.node.scale.copy(s.scale);}}
function disposeTemplate(root:THREE.Object3D){const g=new Set<THREE.BufferGeometry>(),m=new Set<THREE.Material>();root.traverse(n=>{if(n instanceof THREE.Mesh){g.add(n.geometry);for(const material of Array.isArray(n.material)?n.material:[n.material])m.add(material);}});for(const v of g)v.dispose();for(const v of m)v.dispose();root.clear();}
function nativeTriangles(part:CargoMeshPart){part.mesh.updateWorldMatrix(true,false);const instance=new THREE.Matrix4();part.mesh.getMatrixAt(part.index,instance);const matrix=part.mesh.matrixWorld.clone().multiply(instance),g=part.mesh.geometry,p=g.getAttribute('position'),ix=g.index,out:THREE.Triangle[]=[];for(let i=0;i<(ix?.count??p.count);i+=3)out.push(new THREE.Triangle(...[0,1,2].map(j=>new THREE.Vector3().fromBufferAttribute(p,ix?ix.getX(i+j):i+j).applyMatrix4(matrix)) as [THREE.Vector3,THREE.Vector3,THREE.Vector3]));return {triangles:out,matrix};}

/** Carry-only native hip X/Y/Z, shin X with source turn twist Y; no source-target changes. */
function solveLoadedLegs(rig:ReturnType<typeof deriveNativeWorkerGaitRig>,p:WorkerGaitPose,smoothHipYaw=false):WorkerGaitPose{
 if(p.at_s===0||p.stage==='route_end')return p;
 const rotations={...p.joint_rotations};let maximumError=0;
 for(const leg of rig.legs){
  const side=leg.side,target=p.feet[side],wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
  const desired=new THREE.Quaternion().setFromAxisAngle(axisY,wrap(target.yaw_rad-p.yaw_rad));
  const goal=new THREE.Vector3(...target.point).sub(new THREE.Vector3(...p.root_world)).applyAxisAngle(axisY,-p.yaw_rad).sub(new THREE.Vector3(...leg.sole).applyQuaternion(desired)).sub(new THREE.Vector3(...leg.hip));
  const names=['joint__thigh_'+side,'joint__shin_'+side,'joint__foot_'+side];
  const old1=new THREE.Euler().setFromQuaternion(new THREE.Quaternion(...p.joint_rotations[names[0]]),'XYZ'),old2=new THREE.Euler().setFromQuaternion(new THREE.Quaternion(...p.joint_rotations[names[1]]),'XYZ');
  const relativeYaw=wrap(target.yaw_rad-p.yaw_rad),twist=relativeYaw*.30;
  // The legacy seed contains the source hard-max height cusp. Close-hold uses
  // the corrected goal, with a smooth bounded preference inside the same range.
  const bend=Math.atan2(goal.z,-goal.y),bendSquared=bend*bend,preferred=(side==='L'?1:-1)*.09*bendSquared/(bendSquared+.15*.15),centre=relativeYaw-twist;
  const hipYaw=smoothHipYaw?centre+.19*Math.tanh((preferred-centre)/.19):THREE.MathUtils.clamp((side==='L'?1:-1)*.30*Math.min(.30,Math.abs(old1.x)),relativeYaw-twist-.19,relativeYaw-twist+.19),values=[old1.x,0,old2.x],a=new THREE.Vector3(...leg.a),b=new THREE.Vector3(...leg.b),q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();
  function point(v:number[]){q1.setFromEuler(new THREE.Euler(v[0],hipYaw,v[1],'XYZ'));q2.setFromEuler(new THREE.Euler(v[2],twist,0,'XYZ'));q12.copy(q1).multiply(q2);return a.clone().applyQuaternion(q1).add(b.clone().applyQuaternion(q12));}
  for(let i=0;i<50;i++){
   const current=point(values),error=goal.clone().sub(current);if(error.length()<1e-11)break;
   const columns=values.map((_,j)=>{const v=[...values];v[j]+=1e-6;return point(v).sub(current).multiplyScalar(1e6);});
   const jac=new THREE.Matrix3().set(columns[0].x,columns[1].x,columns[2].x,columns[0].y,columns[1].y,columns[2].y,columns[0].z,columns[1].z,columns[2].z);
   requireValue(Math.abs(jac.determinant())>1e-15,'LOADED_LEG_SINGULAR',{at_s:p.at_s,side,values});
   error.applyMatrix3(jac.invert());for(let j=0;j<3;j++)values[j]+=THREE.MathUtils.clamp(error.getComponent(j),-.2,.2);
  }
  const error=point(values).distanceTo(goal);requireValue(error<=2e-7,'LOADED_LEG_UNREACHABLE',{at_s:p.at_s,side,error,values});maximumError=Math.max(maximumError,error);
  const angles=[new THREE.Euler(values[0],hipYaw,values[1],'XYZ'),new THREE.Euler(values[2],twist,0,'XYZ'),new THREE.Euler().setFromQuaternion(q12.clone().invert().multiply(desired),'XYZ')];
  for(let i=0;i<3;i++){const ranges=rig.nodes.find(n=>n.name===names[i])!.limits!,v=[angles[i].x,angles[i].y,angles[i].z];requireValue(v.every((x,k)=>x>=ranges[k][0]-1e-8&&x<=ranges[k][1]+1e-8),'LOADED_LEG_JOINT_LIMIT',{at_s:p.at_s,side,joint:names[i],v,ranges});rotations[names[i]]=new THREE.Quaternion().setFromEuler(angles[i]).toArray();}
 }
 return {...p,joint_rotations:rotations,maximum_IK_error_m:maximumError};
}

/** Carry-only support timing; horizontal route remains source-bound. */
function sampleGroundedCarry(rig:ReturnType<typeof deriveNativeWorkerGaitRig>,gait:ReturnType<typeof compileNativeWorkerGait>,seconds:number):WorkerGaitPose{
 const pure=gait.sample(seconds),phase=gait.phases.find(p=>pure.at_s>=p.start_s&&pure.at_s<p.end_s);
 if(!phase||!phase.swing||pure.at_s===0)return solveLoadedLegs(rig,pure);
 const ease=(u:number)=>u*u*u*(10+u*(-15+6*u)),wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
 const u=(pure.at_s-phase.start_s)/(phase.end_s-phase.start_s),v=Math.max(0,Math.min(1,(u-.06)/.88)),blend=ease(v),side=phase.swing,from=phase.feet_from[side],to=phase.feet_to[side],lift=.018*Math.sin(Math.PI*v)**2;
 const feet:WorkerGaitPose['feet']={...pure.feet,[side]:{point:tuple(new THREE.Vector3(...from.point).lerp(new THREE.Vector3(...to.point),blend).add(new THREE.Vector3(0,lift,0))),yaw_rad:from.yaw_rad+wrap(to.yaw_rad-from.yaw_rad)*blend,stance:u<=.06||u>=.94,lift_m:lift}};
 const position=new THREE.Vector3(...pure.root_world);position.y+=pure.body_drop_m;let drop=0;
 for(const leg of rig.legs){const foot=feet[leg.side],local=new THREE.Vector3(...foot.point).sub(position).applyAxisAngle(axisY,-pure.yaw_rad),ankle=local.sub(new THREE.Vector3(...leg.sole).applyAxisAngle(axisY,foot.yaw_rad-pure.yaw_rad)),dx=ankle.x-leg.hip[0],dz=ankle.z-leg.hip[2],length=new THREE.Vector3(...leg.a).length()+new THREE.Vector3(...leg.b).length();drop=Math.max(drop,leg.hip[1]-ankle.y-Math.sqrt(Math.max(0,length*length-dx*dx-dz*dz)));}
 drop=Math.max(0,drop)+phase.margin_from+(phase.margin_to-phase.margin_from)*ease(u);position.y-=drop;
 return solveLoadedLegs(rig,{...pure,root_world:tuple(position),body_drop_m:drop,feet});
}

/** Close-hold-only conservative reach conditioning; source footfalls/clock stay exact. */
function sampleGroundedCloseCarry(rig:ReturnType<typeof deriveNativeWorkerGaitRig>,gait:ReturnType<typeof compileNativeWorkerGait>,seconds:number):WorkerGaitPose{
 const pure=gait.sample(seconds),phase=gait.phases.find(p=>pure.at_s>=p.start_s&&pure.at_s<p.end_s);
 if(!phase||pure.at_s===0)return solveLoadedLegs(rig,pure,true);
 const ease=(u:number)=>u*u*u*(10+u*(-15+6*u)),wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
 const u=(pure.at_s-phase.start_s)/(phase.end_s-phase.start_s);
 let feet=pure.feet;
 if(phase.swing){
  const v=Math.max(0,Math.min(1,(u-.06)/.88)),blend=ease(v),side=phase.swing,from=phase.feet_from[side],to=phase.feet_to[side],lift=.018*Math.sin(Math.PI*v)**2;
  feet={...pure.feet,[side]:{point:tuple(new THREE.Vector3(...from.point).lerp(new THREE.Vector3(...to.point),blend).add(new THREE.Vector3(0,lift,0))),yaw_rad:from.yaw_rad+wrap(to.yaw_rad-from.yaw_rad)*blend,stance:u<=.06||u>=.94,lift_m:lift}};
 }
 const position=new THREE.Vector3(...pure.root_world);position.y+=pure.body_drop_m;
 const required=[0];
 for(const leg of rig.legs){const foot=feet[leg.side],local=new THREE.Vector3(...foot.point).sub(position).applyAxisAngle(axisY,-pure.yaw_rad),ankle=local.sub(new THREE.Vector3(...leg.sole).applyAxisAngle(axisY,foot.yaw_rad-pure.yaw_rad)),dx=ankle.x-leg.hip[0],dz=ankle.z-leg.hip[2],length=new THREE.Vector3(...leg.a).length()+new THREE.Vector3(...leg.b).length();required.push(leg.hip[1]-ankle.y-Math.sqrt(Math.max(0,length*length-dx*dx-dz*dz)));}
 const hard=Math.max(...required),scale=.001,soft=hard+scale*Math.log(required.reduce((sum,d)=>sum+Math.exp((d-hard)/scale),0));
 const envelope=phase.kind==='prepare'?ease(u):phase.kind==='settle'?1-ease(u):1;
 // Fixed start/stop amplitudes retain the fitted native ankle-range bounds.
 // Cruise eligibility is constant per phase; pulse value/slope vanish at joins.
 const profile=phase.profile,eligible=phase.kind==='walk_step'&&profile!==null&&phase.start_s>=profile.start_s+profile.ramp_s&&phase.end_s<=profile.start_s+profile.ramp_s+profile.cruise_s;
 const phaseAmplitude=phase.kind==='walk_step'&&profile!==null&&!eligible ? (CLOSE_HOLD_START_STOP_RESERVE.get(phase.start_s)??0):0;
 const reserve=(eligible ? .006:phaseAmplitude)*Math.sin(Math.PI*u)**2;
 const drop=hard+envelope*(soft-hard)+reserve+phase.margin_from+(phase.margin_to-phase.margin_from)*ease(u);
 position.y-=drop;
 return solveLoadedLegs(rig,{...pure,root_world:tuple(position),body_drop_m:drop,feet},true);
}

/** Prescribed pre-held calibration only; no Scene/global action lease or source-pickup admission. */
export async function createWarehouseLoadedWalkCalibration(o:Options){
 requireValue(o?.calibration_fixture===true,'ISOLATED_CALIBRATION_REQUIRED');
 const motionStyle=o.motion_style??'source';requireValue(motionStyle==='source'||motionStyle==='grounded_carry','INVALID_MOTION_STYLE');
 const carryPreset=o.carry_pose??'source';requireValue(carryPreset==='source'||carryPreset==='low_close'||carryPreset==='vertical_90'||carryPreset==='close_hold'||carryPreset==='original_hold','INVALID_CARRY_POSE');
 requireValue(carryPreset!=='close_hold'||motionStyle==='grounded_carry','CLOSE_HOLD_REQUIRES_GROUNDED_CARRY');
 requireValue(carryPreset!=='original_hold'||motionStyle==='grounded_carry','ORIGINAL_HOLD_REQUIRES_GROUNDED_CARRY');
 requireValue(o.breathing===undefined||typeof o.breathing==='boolean','INVALID_BREATHING_OPTION');
 let breathingEnabled=o.breathing===true,breathingConfigured=o.breathing!==undefined;
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
 const sourcePose=JSON.parse(new TextDecoder().decode(await source(POSE_PATH,POSE_SHA))) as CarryPose;
 const pose=carryPreset==='source'?sourcePose:JSON.parse(new TextDecoder().decode(await source(carryPreset==='original_hold'?ORIGINAL_HOLD_POSE_PATH:carryPreset==='low_close'?LOW_POSE_PATH:carryPreset==='vertical_90'?VERTICAL_POSE_PATH:CLOSE_POSE_PATH,carryPreset==='original_hold'?ORIGINAL_HOLD_POSE_SHA:carryPreset==='low_close'?LOW_POSE_SHA:carryPreset==='vertical_90'?VERTICAL_POSE_SHA:CLOSE_POSE_SHA))) as CarryPose;
 // Study-time provenance includes a mutable task card; native runtime admission
 // is pinned by the reviewed pose SHA and the current independent loaded gate.
 const report=JSON.parse(new TextDecoder().decode(await source(REPORT_PATH,REPORT_SHA)));
 requireValue(report.passed===true&&report.task_id==='W05.3.1'&&report.lifecycle.negative_cases===38&&report.native_clearance.material_changed_nonadjacent_witnesses.length===0,'STATIC_NATIVE_CALIBRATION_REQUIRED');
 for(const[p,h]of Object.entries(report.input_hashes as Record<string,string>))await source(p,h);
 const dynamicReport=JSON.parse(new TextDecoder().decode(await source(DYNAMIC_REPORT_PATH,DYNAMIC_REPORT_SHA)));
 requireValue(dynamicReport.schema_id==='qoima.W05.3.4.dynamic-cargo-binding-checks.v1'&&dynamicReport.passed===true,'PROVED_DYNAMIC_BINDING_REQUIRED');
 for(const[p,h]of Object.entries(dynamicReport.source_hashes as Record<string,string>))await source(p,h);
 requireValue(pose.actor_id==='P02'&&pose.worker_asset==='worker-base'&&pose.cargo.handling_unit_ref===HU&&(carryPreset==='source'?JSON.stringify(pose.cargo.position_m)==='[0,0.96,0.52]':pose.cargo.position_m.length===3&&pose.cargo.position_m.every(finite)&&pose.cargo.position_m[1]<.96&&pose.cargo.position_m[2]<.52)&&Object.keys(pose.jointEulerXYZ).sort().join('|')===[...ARM_NAMES].sort().join('|'),'STATIC_POSE_MISMATCH');
 const router=createWarehouseRouter(bundle,policy),route=router.route({source_kind:'visual_fixture',engine_operation:false,mode:'pedestrian',actor_id:'P02',vehicle_id:null,cargo_archetype_id:'SMALL_CARTON',from_node_id:NODE_IDS[0],to_node_id:NODE_IDS[2],service_port_id:null,closed_arc_ids:[]});
 requireValue(route.ok&&route.length_m===15.75&&JSON.stringify(route.arc_ids)===JSON.stringify(ARC_IDS),'CANONICAL_ROUTE_MISMATCH',{route});
 for(let i=0;i<3;i++)requireValue(JSON.stringify(bundle.layout.walk.nodes.find(n=>n.node_id===NODE_IDS[i])?.world_pos)===JSON.stringify(POINTS[i]),'CANONICAL_NODE_MISMATCH');
 const profile=bundle.profiles.profiles.find(p=>p.worker_id==='P02');requireValue(profile?.walk_speed_m_s===1.2&&profile.allowed_handlers.includes('manual'),'SOURCE_PROFILE_MISMATCH');
 const bodyPath=(carryPreset==='source'||carryPreset==='original_hold')?'frontend/public/models/v3/worker-base.glb':carryPreset==='low_close'?LOW_BODY_PATH:carryPreset==='vertical_90'?VERTICAL_BODY_PATH:CLOSE_BODY_PATH;
 requireValue(carryPreset==='source'||pose.worker_model_path===bodyPath,'CARRY_MODEL_VARIANT_MISMATCH');
 requireValue(carryPreset!=='original_hold'||pose.worker_model_path===bodyPath&&pose.source_hashes[bodyPath]===ORIGINAL_BODY_SHA,'ORIGINAL_HOLD_ORIGINAL_MODEL_REQUIRED');
 requireValue(carryPreset!=='original_hold'||pose.pose_only_forearm_pronation?.gain===.5&&pose.pose_only_forearm_pronation.law==='canonical_Y_roll_bind_delta_about_native_forearm_axis'&&Array.isArray(pose.pose_only_forearm_pronation.source_meshes)&&[...pose.pose_only_forearm_pronation.source_meshes].sort().join('|')==='worker-base__batch_11|worker-base__batch_14','ORIGINAL_HOLD_PRONATION_CONTRACT_REQUIRED');
 const bodyBytes=await source(bodyPath,pose.source_hashes[bodyPath]);
 const template=(await new GLTFLoader().parseAsync(bodyBytes.buffer.slice(bodyBytes.byteOffset,bodyBytes.byteOffset+bodyBytes.byteLength) as ArrayBuffer,'')).scene;
 const sourceRoot=template.getObjectByName('worker_base_root');requireValue(sourceRoot,'BASE_RIG_MISSING');
 const nodes=new Map<string,THREE.Object3D>(),original:NodeState[]=[];actor.root.traverse(n=>{original.push(capture(n));if(n!==actor.root&&!n.userData.roleBadge){requireValue(!nodes.has(n.name),'DUPLICATE_NATIVE_NODE');nodes.set(n.name,n);}});
 let rig:ReturnType<typeof deriveNativeWorkerGaitRig>;
 let forearmPronation:ReturnType<typeof createWarehouseForearmPronationPose>|undefined;
 try{
  rig=deriveNativeWorkerGaitRig(sourceRoot!);
  for(const n of rig.nodes){const actual=nodes.get(n.name);requireValue(actual&&actual.position.distanceTo(new THREE.Vector3(...n.position))<2e-8&&actual.quaternion.toArray().every((v,i)=>Math.abs(v-n.quaternion[i])<1e-8)&&actual.scale.distanceTo(new THREE.Vector3(...n.scale))<1e-10,'ACTOR_NOT_AT_SOURCE_REST',{node:n.name});
   if(n.mesh){requireValue(actual instanceof THREE.Mesh,'ACTOR_GEOMETRY_CHANGED');const p=actual.geometry.getAttribute('position'),ix=actual.geometry.index;requireValue(p.count*3===n.mesh.positions.length&&(ix?.count??0)===(n.mesh.indices?.length??0),'ACTOR_GEOMETRY_CHANGED');for(let i=0;i<p.count;i++)requireValue(p.getX(i)===n.mesh.positions[3*i]&&p.getY(i)===n.mesh.positions[3*i+1]&&p.getZ(i)===n.mesh.positions[3*i+2],'ACTOR_GEOMETRY_CHANGED');if(ix)for(let i=0;i<ix.count;i++)requireValue(ix.getX(i)===n.mesh.indices![i],'ACTOR_GEOMETRY_CHANGED');}
  }
  if(carryPreset==='original_hold')forearmPronation=createWarehouseForearmPronationPose(actor.root,sourceRoot!,ORIGINAL_BODY_SHA);
 }finally{disposeTemplate(template);}
 const motionSpeed=motionStyle==='grounded_carry'?Math.min(profile!.walk_speed_m_s,.7):profile!.walk_speed_m_s;
 const gait=compileNativeWorkerGait(rig!,POINTS,-Math.PI/2,motionSpeed,bundle.layout.modules.map(m=>m.outer_bounds_world));
 if(carryPreset==='close_hold'){const fittedPhases=gait.phases.filter(p=>p.kind==='walk_step'&&p.profile!==null&&!(p.start_s>=p.profile.start_s+p.profile.ramp_s&&p.end_s<=p.profile.start_s+p.profile.ramp_s+p.profile.cruise_s));requireValue(fittedPhases.length===CLOSE_HOLD_START_STOP_RESERVE.size&&fittedPhases.every(p=>CLOSE_HOLD_START_STOP_RESERVE.has(p.start_s)),'CLOSE_HOLD_START_STOP_FIT_PHASE_MISMATCH');}
 const motionProfile=freeze({style:motionStyle,source_profile_speed_m_s:profile!.walk_speed_m_s,actual_calibration_speed_cap_m_s:motionSpeed,foot_hold_fraction_each_end:motionStyle==='grounded_carry'?.06:0,whole_sole_flat_support:true,lateral_root_transfer:false,force_balance_certified:false,...(carryPreset==='close_hold'?{reach_smoothmax_scale_m:.001,steady_cruise_flexion_reserve_peak_m:.006,hip_yaw_preference:'smooth_corrected_hip_to_ankle_goal',bounded_start_stop_reserve:{phase_count:CLOSE_HOLD_START_STOP_RESERVE.size,maximum_amplitude_m:.006,fit_sha256:'65fc6c0f7f880a0cc7bc53d7f2098166ae4be71c52f8eba5926f75ed53ac075c',fit_source_controller_sha256:'3c1680f7a14d5e915bbf65a286e07d4a29ac4d3be77118f0e27afa1601885eb8',source_route_arc_ids:[...ARC_IDS]}}:{})});
 const breathing=createWarehouseCarryBreathing(actor.root);
 actor.root.updateWorldMatrix(true,true);const palmSupport=carryPreset==='close_hold'?createWarehousePalmSupport(actor.root):null;
 const armQ=Object.fromEntries(ARM_NAMES.map(name=>{const a=pose.jointEulerXYZ[name];requireValue(a?.length===3&&[0,1,2].every(i=>Object.hasOwn(a,i)&&finite(a[i])),'INVALID_STATIC_JOINT');if(carryPreset==='original_hold'){const node=nodes.get(name)!;const ranges=name.includes('palm_roll')?[[0,0],node.userData.rotation_range_radians,[0,0]]:JSON.parse(node.userData.limits_xyz_json??'null');requireValue(Array.isArray(ranges)&&ranges.length===3&&ranges.every((r:unknown)=>Array.isArray(r)&&r.length===2&&r.every(finite)),'ORIGINAL_HOLD_NATIVE_ARM_LIMITS_REQUIRED',{name});requireValue(a.every((v,i)=>v>=ranges[i][0]-1e-10&&v<=ranges[i][1]+1e-10),'ORIGINAL_HOLD_NATIVE_ARM_LIMIT',{name,a,ranges});}return [name,new THREE.Quaternion().setFromEuler(new THREE.Euler(...a,'XYZ'))];}));
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
 function observe(p:WorkerGaitPose,cargoWorld:THREE.Matrix4){
  actor.root.updateWorldMatrix(true,true);const contactRows=pose.solved_reference_points.map(c=>{const hand=nodes.get('joint__hand_'+c.side)!,point=hand.localToWorld(new THREE.Vector3(...c.local_hand_m));let gap=Infinity,nearest:Record<string,unknown>={};for(const part of binding.parts){const n=nativeTriangles(part);for(let i=0;i<n.triangles.length;i++){const q=n.triangles[i].closestPointToPoint(point,new THREE.Vector3()),d=point.distanceTo(q);if(d<gap){gap=d;nearest={part:part.mesh.name,index:part.index,triangle:i,point_m:tuple(q),matrix_world:n.matrix.toArray()};}}}requireValue(gap<=EPS,'NATIVE_CONTACT_GAP',{at_s:p.at_s,phase:p.stage,side:c.side,gap_m:gap,reference_world_m:tuple(point),nearest});return {side:c.side,point_world_m:tuple(point),gap_m:gap,nearest};});
  const feet=rig!.legs.map(leg=>{const foot=nodes.get('joint__foot_'+leg.side)!,sole=nodes.get('anchor_foot_floor_'+leg.side)!.getWorldPosition(new THREE.Vector3()),bottom=Math.min(...leg.vertices.map(v=>new THREE.Vector3(...v).applyMatrix4(foot.matrixWorld).y)),target=p.feet[leg.side],error=sole.distanceTo(new THREE.Vector3(...target.point)),forward=new THREE.Vector3(0,0,1).transformDirection(foot.matrixWorld),yaw=Math.atan2(forward.x,forward.z),yawError=Math.abs(Math.atan2(Math.sin(yaw-target.yaw_rad),Math.cos(yaw-target.yaw_rad)));requireValue(error<=EPS&&yawError<=EPS&&bottom>=-EPS&&(!target.stance||Math.abs(bottom)<=EPS),'NATIVE_STANCE_VIOLATION',{at_s:p.at_s,side:leg.side,error_m:error,yaw_error_rad:yawError,bottom_y_m:bottom});return {side:leg.side,stance:target.stance,sole_world_m:tuple(sole),target_world_m:target.point,error_m:error,native_bottom_y_m:bottom,yaw_rad:yaw,target_yaw_rad:target.yaw_rad,yaw_error_rad:yawError};});
  const armAnatomy=carryPreset==='vertical_90'||carryPreset==='close_hold'?(['L','R'] as const).map(side=>{const shoulder=nodes.get('joint__upper_arm_'+side)!.getWorldPosition(new THREE.Vector3()),elbow=nodes.get('joint__forearm_'+side)!.getWorldPosition(new THREE.Vector3()),wrist=nodes.get('joint__palm_roll_'+side)!.getWorldPosition(new THREE.Vector3()),upper=elbow.clone().sub(shoulder),fore=wrist.clone().sub(elbow),tilt=THREE.MathUtils.radToDeg(upper.angleTo(new THREE.Vector3(0,-1,0))),inner=THREE.MathUtils.radToDeg(upper.clone().negate().angleTo(fore));requireValue(tilt<=5+1e-7&&inner>=85-1e-7&&inner<=95+1e-7,'NATIVE_ARM_ANATOMY_VIOLATION',{at_s:p.at_s,side,upper_tilt_deg:tilt,elbow_inner_deg:inner});return {side,shoulder_world_m:tuple(shoulder),elbow_world_m:tuple(elbow),wrist_world_m:tuple(wrist),upper_tilt_deg:tilt,elbow_inner_deg:inner};}):null;
  const gripSupport=palmSupport?.sample(cargoWorld);if(gripSupport)for(const row of gripSupport)requireValue(row.lower.coverage_ratio>=.95&&row.upper.coverage_ratio>=.95&&row.lower_centroid_z_offset_m!==null&&Math.abs(row.lower_centroid_z_offset_m)<=.025&&row.lower.maximum_plane_gap_m<=EPS&&row.upper.maximum_plane_gap_m<=EPS,'NATIVE_FULL_PALM_SUPPORT_VIOLATION',{at_s:p.at_s,...row});
  return freeze({...flags,...(forearmPronation?{forearm_pronation:forearmPronation.snapshot()}:{}),motion_profile:motionProfile,...(gripSupport?{grip_support:gripSupport}:{}),...(armAnatomy?{arm_anatomy:armAnatomy}:{}),...(carryPreset!=='source'||breathingConfigured?{carry_pose:carryPreset,breathing:{enabled:breathingEnabled,angle_rad:breathing.sample(p.at_s,breathingEnabled).angle_rad,period_s:breathing.period_s,amplitude_rad:breathing.amplitude_rad}}:{}),at_s:p.at_s,duration_s:gait.duration_s,stage:p.at_s===gait.duration_s?'terminal_hold':p.at_s===0?'static_hold':'loaded_walk',gait_stage:p.stage,actor_id:'P02',handling_unit_id:HU,root_world_m:tuple(actor.root.getWorldPosition(new THREE.Vector3())),yaw_rad:p.yaw_rad,body_drop_m:p.body_drop_m,contacts:contactRows,feet,route_arc_ids:ARC_IDS,ownership_scope:'One isolated calibration owner across static_hold/loaded_walk/terminal_hold; no global Scene lease',foreign_clearance_scope:'Independent current native CPU gate required',source_pickup_executed:false,binding:binding.snapshot(),actual_events:[]});
 }
 function apply(seconds:number){requireValue(finite(seconds),'INVALID_TIME');live();const next=motionStyle==='grounded_carry'?(carryPreset==='close_hold'?sampleGroundedCloseCarry(rig!,gait,seconds):sampleGroundedCarry(rig!,gait,seconds)):solveLoadedLegs(rig!,gait.sample(seconds)),beforeNodes=lastNodes,beforeDelta=lastDelta.clone(),beforeAt=at,beforePose=lastPose,beforeSnapshot=lastSnapshot;applying=true;
  try{
   const rotations=new Map(ARM_NAMES.map(n=>[n,armQ[n]]));for(const name of LEG_NAMES)rotations.set(name,new THREE.Quaternion(...next.joint_rotations[name]));
   // One composite expected frame; never call the unloaded controller or overwrite its arms later.
   restore(original);actor.root.position.copy(new THREE.Vector3(...next.root_world).applyMatrix4(parentWorld.clone().invert()));const parentQ=actor.root.parent?.getWorldQuaternion(new THREE.Quaternion())??new THREE.Quaternion();actor.root.quaternion.copy(parentQ.invert().multiply(new THREE.Quaternion().setFromAxisAngle(axisY,next.yaw_rad)));for(const[n,q]of rotations)nodes.get(n)!.quaternion.copy(q);forearmPronation?.apply();actor.root.updateWorldMatrix(true,true);
   const breath=breathing.sample(next.at_s,breathingEnabled);if(breathingEnabled){nodes.get(breathing.torso_name)!.quaternion.copy(breath.torso_quaternion);actor.root.updateWorldMatrix(true,true);}
   const cargoWorld=actor.root.matrixWorld.clone();if(breathingEnabled)cargoWorld.multiply(breath.cargo_delta_root);cargoWorld.multiply(new THREE.Matrix4().compose(new THREE.Vector3(...pose.cargo.position_m),new THREE.Quaternion().setFromAxisAngle(axisY,pose.cargo.yaw_rad),unit));writeCargo(cargoWorld);lastSnapshot=observe(next,cargoWorld);at=next.at_s;lastPose=next;lastNodes=original.map(s=>capture(s.node));for(const s of meshes)s.last=new Float32Array(s.part.mesh.instanceMatrix.array);return lastSnapshot;
  }catch(e){restore(beforeNodes);binding.applyDelta(beforeDelta);lastDelta=beforeDelta;actor.root.updateWorldMatrix(true,true);at=beforeAt;lastPose=beforePose;lastSnapshot=beforeSnapshot;throw e;}finally{applying=false;}
 }
 function setBreathingEnabled(enabled:boolean){requireValue(typeof enabled==='boolean','INVALID_BREATHING_OPTION');live();const previous=breathingEnabled,configured=breathingConfigured;breathingEnabled=enabled;breathingConfigured=true;try{return apply(at);}catch(error){breathingEnabled=previous;breathingConfigured=configured;throw error;}}
 function reset(){return apply(0);}
 function snapshot(){if(!disposed)live();return lastSnapshot;}
 function dispose(){if(disposed)return;disposed=true;forearmPronation?.dispose();restore(original);binding.dispose();o.cargoParts.set(HU,parts);actor.root.updateWorldMatrix(true,true);actorOwners.delete(actor);for(const s of meshes)meshOwners.delete(s.part.mesh);}
 actorOwners.add(actor);for(const s of meshes)meshOwners.add(s.part.mesh);
 try{apply(0);}catch(e){dispose();throw e;}
 return Object.freeze({apply,reset,snapshot,dispose,setBreathingEnabled,parts:binding.parts,sourceParts:parts,bindingSnapshot:()=>binding.snapshot(),duration_s:gait.duration_s,phases:gait.phases,motion_profile:motionProfile,source_hashes:freeze(source_hashes),route:freeze({...route}),scope:freeze({...flags,calibration_start_is_original_actor_home:false,calibration_setup_is_elapsed_action:false,other_actor_and_HU_count_delta:0})});
}
