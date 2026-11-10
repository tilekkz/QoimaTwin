import * as THREE from 'three';
import {isWarehouseSmallClampManualTransfer,type WarehouseSmallClampManualTransfer} from './warehouseSmallClampManualTransfer';
import {isWarehouseSmallClampReceivingTransfer,type WarehouseSmallClampReceivingTransfer} from './warehouseSmallClampReceivingTransfer';
import type {WarehouseWestPalletReceipt} from './warehouseWestPalletReceipt';
import {deriveNativeWorkerGaitRig,compileNativeWorkerGait,type CompiledWorkerGait} from './warehouseWorkerGait';
import {createWarehouseCargo} from './warehouseCargo';
import {createWarehouseHeavyInboundScene} from './warehouseHeavyInboundScene';
import {isWarehouseHeavyInboundPlan,type WarehouseHeavyInboundPlan} from './warehouseHeavyInboundPlan';
import {isWarehouseAdditionalHeavyPlan} from './warehouseAdditionalHeavyCases';
import {isWarehouseScenarioPlan,type WarehouseScenarioAdditionalHeavyPlan,type ScenarioReceivingSample,type ScenarioSmallReceivingSample} from './warehouseScenarioExecution';
import {isWarehouseReceivingManualTransfer,type WarehouseReceivingManualTransfer} from './warehouseReceivingManualTransfer';
import {createWarehouseAdditionalHeavyScene,type AdditionalHeavyDisplayRow} from './warehouseAdditionalHeavyScene';
import {isWarehouseManualTransfer,type WarehouseManualTransfer} from './warehouseScenarioManualTransfer';
import type {WarehouseBundle,XYZ} from './warehouseTypes';
import {createWarehouseLongScenarioScene} from './warehouseLongScenarioScene';
import {createWarehouseLongSourceOperationScene} from './warehouseLongSourceOperationScene';
import {isWarehouseLongSourceOperationPlan,type WarehouseLongSourceOperationPlan,type LongSourceSample} from './warehouseLongSourceOperationPlan';
import {isWarehouseLongScenarioPlan,type compileWarehouseLongScenarioPlan} from './warehouseLongScenarioPlan';
type LongPlan=Awaited<ReturnType<typeof compileWarehouseLongScenarioPlan>>;

export type ScenarioNativeRoute={route_id:string;actor_id:string;mode:string;points_world:XYZ[];start_yaw_rad:number;speed_m_s:number;duration_s:number;from_node_id?:string};
type ActorFrame={actor_id:string;vehicle_id:string|null;role:string;position:XYZ;yaw_rad:number;activity:string;job_id:string|null;route_id:string|null;route_at_s:number};
type VehicleFrame={vehicle_id:string;actor_id:string;position:XYZ;yaw_rad:number;fork_top_m:number;extension_m:number;rear_steer_rad:{L:number;R:number};fork_halfspacing_m?:number;wheel_angles_rad:Record<string,number>};
type CargoFrame={handling_unit_id:string;position:XYZ|null;yaw_rad:number;visible:boolean;attached:boolean;location:unknown};
export type ScenarioNativeSample={native_small_manual_local_s?:number|null;native_small_manual?:ReturnType<WarehouseSmallClampManualTransfer['sample']>|null;native_small_receiving?:ScenarioSmallReceivingSample|null;at_s:number;actors:readonly ActorFrame[];vehicles:readonly VehicleFrame[];cargo:readonly CargoFrame[];native_heavy_local_s:number|null;native_heavy:unknown;native_manual_local_s?:number|null;native_additional_heavy?:readonly AdditionalHeavyDisplayRow[];native_long_local_s?:number|null;native_long?:unknown;native_receiving?:readonly ScenarioReceivingSample[];native_source_long_local_s?:number|null;native_source_long?:Readonly<LongSourceSample>|null};
export type ScenarioNativePlan={duration_s:number;routes:readonly ScenarioNativeRoute[];sample:(at_s:number)=>ScenarioNativeSample;native_heavy_plan?:WarehouseHeavyInboundPlan|null};
type Local={node:THREE.Object3D;parent:THREE.Object3D|null;p:THREE.Vector3;q:THREE.Quaternion;s:THREE.Vector3};
const Y=new THREE.Vector3(0,1,0),X=new THREE.Vector3(1,0,0),UNIT=new THREE.Vector3(1,1,1),owners=new WeakSet<THREE.Scene>();
const save=(node:THREE.Object3D):Local=>({node,parent:node.parent,p:node.position.clone(),q:node.quaternion.clone(),s:node.scale.clone()});
const restore=(rows:readonly Local[])=>{for(const r of rows){r.node.position.copy(r.p);r.node.quaternion.copy(r.q);r.node.scale.copy(r.s);}};
const pose=(position:XYZ,yaw:number)=>new THREE.Matrix4().compose(new THREE.Vector3(...position),new THREE.Quaternion().setFromAxisAngle(Y,yaw),UNIT);
function requireValue(value:unknown,message:string):asserts value{if(!value)throw Error(message);}

/** Native display context. Preparation supplies exact native timing to the pure
 * common clock. A calendar entry alone never moves a HU or completes a handoff. */
export function createWarehouseScenarioScene(scene:THREE.Scene,bundle:WarehouseBundle){
 requireValue(scene?.isScene&&!owners.has(scene),'SCENARIO_SCENE_ALREADY_OWNED');
 const actors=new Map<string,THREE.Object3D>(),vehicles=new Map<string,THREE.Object3D>(),original:Local[]=[],seen=new Set<THREE.Object3D>();
 const remember=(root:THREE.Object3D)=>root.traverse(n=>{if(!seen.has(n)){seen.add(n);original.push(save(n));}});
 scene.traverse(n=>{if(n.userData.semanticKind==='actor'&&typeof n.userData.semanticId==='string')actors.set(n.userData.semanticId,n);if(n.name.startsWith('vehicle__'))vehicles.set(n.name.slice('vehicle__'.length),n);});
 requireValue(actors.size===24&&vehicles.size===2,'ORIGINAL_SCENARIO_POPULATION_REQUIRED');for(const n of [...actors.values(),...vehicles.values()])remember(n);
 const rests=new Map(original.map(r=>[r.node,r])),sourceCargo=new Map(createWarehouseCargo(bundle).snapshot().map(h=>[h.handling_unit_id,h]));
 const rigCache=new Map<string,ReturnType<typeof deriveNativeWorkerGaitRig>>(),gaits=new Map<string,{route:ScenarioNativeRoute;gait:CompiledWorkerGait}>();
 const fixed=bundle.layout.modules.map(m=>m.outer_bounds_world);
 let small:WarehouseSmallClampManualTransfer|undefined,smallReceiving:WarehouseSmallClampReceivingTransfer|undefined;
 let plan:ScenarioNativePlan|undefined,heavySource:WarehouseHeavyInboundPlan|undefined,heavy:ReturnType<typeof createWarehouseHeavyInboundScene>|undefined,manual:WarehouseManualTransfer|undefined,additional:ReturnType<typeof createWarehouseAdditionalHeavyScene>|undefined,additionalPlans:readonly WarehouseScenarioAdditionalHeavyPlan[]=[],longSource:LongPlan|undefined,long:Awaited<ReturnType<typeof createWarehouseLongScenarioScene>>|undefined,longEpoch=0,sourceLongSource:WarehouseLongSourceOperationPlan|undefined,sourceLong:Awaited<ReturnType<typeof createWarehouseLongSourceOperationScene>>|undefined,receivingCases:readonly WarehouseReceivingManualTransfer[]=[],current:ScenarioNativeSample|undefined,disposed=false,refusal:string|null=null;
 owners.add(scene);
 function alive(){requireValue(!disposed,'SCENARIO_SCENE_DISPOSED');}
 async function prepareLongCrossdock(value:LongPlan,options:{signal?:AbortSignal;readSource?:(path:string)=>Promise<ArrayBuffer|Uint8Array>}={}){
  alive();requireValue(isWarehouseLongScenarioPlan(value),'ISSUED_LONG_PLAN_REQUIRED');if(long&&longSource===value)return snapshot();const token=++longEpoch;sourceLong?.dispose();sourceLong=undefined;sourceLongSource=undefined;long?.dispose();long=undefined;longSource=undefined;
  const readSource=options.readSource?async(path:string)=>{const bytes=await options.readSource!(path);return bytes instanceof Uint8Array?bytes:new Uint8Array(bytes);}:undefined;
  const prepared=await createWarehouseLongScenarioScene(scene,bundle,value,{signal:options.signal,readSource});
  if(disposed||token!==longEpoch||options.signal?.aborted){prepared.dispose();throw Error(disposed?'SCENARIO_SCENE_DISPOSED':'SCENARIO_LONG_PREPARATION_CANCELLED');}long=prepared;longSource=value;return snapshot();
 }
 async function prepareSourceLong(value:WarehouseLongSourceOperationPlan,options:{signal?:AbortSignal;readSource?:(path:string)=>Promise<ArrayBuffer|Uint8Array>}={}){
  alive();requireValue(isWarehouseLongSourceOperationPlan(value),'ISSUED_SOURCE_LONG_PLAN_REQUIRED');options.signal?.throwIfAborted();if(sourceLong&&sourceLongSource===value)return snapshot();const token=++longEpoch;long?.dispose();long=undefined;longSource=undefined;sourceLong?.dispose();sourceLong=undefined;sourceLongSource=undefined;
  const readSource=options.readSource?async(path:string)=>{const b=await options.readSource!(path);return b instanceof Uint8Array?b:new Uint8Array(b);}:undefined;
  const prepared=await createWarehouseLongSourceOperationScene(scene,bundle,value,{signal:options.signal,readSource});
  if(disposed||token!==longEpoch||options.signal?.aborted){prepared.dispose();throw Error(disposed?'SCENARIO_SCENE_DISPOSED':'SCENARIO_SOURCE_LONG_PREPARATION_CANCELLED');}sourceLong=prepared;sourceLongSource=value;return snapshot();
 }
 function preparePedestrianRoute(route:ScenarioNativeRoute){
  alive();requireValue(route.mode==='pedestrian','NATIVE_PEDESTRIAN_ROUTE_REQUIRED');const actor=actors.get(route.actor_id),worker=bundle.registry.workers.find(w=>w.actor_id===route.actor_id);requireValue(actor&&worker&&!worker.assigned_vehicle_id,'ORIGINAL_UNSEATED_ACTOR_REQUIRED');
  const cached=gaits.get(route.route_id);if(cached){requireValue(JSON.stringify(cached.route.points_world)===JSON.stringify(route.points_world)&&cached.route.actor_id===route.actor_id&&cached.route.start_yaw_rad===route.start_yaw_rad&&cached.route.speed_m_s===route.speed_m_s&&cached.route.from_node_id===route.from_node_id,'SCENARIO_ROUTE_ID_REUSED');return motion(cached.gait);}
  let rig=rigCache.get(route.actor_id);if(!rig){const previous=original.map(r=>save(r.node));try{restore(original);scene.updateMatrixWorld(true);rig=deriveNativeWorkerGaitRig(actor);rigCache.set(route.actor_id,rig);}finally{restore(previous);scene.updateMatrixWorld(true);}}
  const points=route.points_world.length?route.points_world:[bundle.layout.walk.nodes.find(n=>n.node_id===route.from_node_id)?.world_pos??(rests.get(actor)!.p.toArray() as XYZ)];requireValue(route.points_world.length>0||route.duration_s===0,'NONEMPTY_NATIVE_ROUTE_REQUIRED');
  const gait=compileNativeWorkerGait(rig,points,route.start_yaw_rad,route.speed_m_s,fixed);gaits.set(route.route_id,{route:structuredClone(route),gait});return motion(gait);
 }
 function motion(gait:CompiledWorkerGait){return {duration_s:gait.duration_s,sample:(at_s:number)=>{const p=gait.sample(at_s);return {position:[...p.root_world] as XYZ,yaw_rad:p.yaw_rad};},native_timing:true as const};}
 const pedestrianDuration=(route:ScenarioNativeRoute)=>preparePedestrianRoute(route).duration_s;
 function reset(){alive();smallReceiving?.reset();small?.reset();for(const c of receivingCases)c.reset();manual?.reset();long?.reset();sourceLong?.reset();additional?.reset();heavy?.apply(0);restore(original);scene.updateMatrixWorld(true);current=undefined;refusal=null;}
 function bind(value:ScenarioNativePlan,options:{native_heavy_materialization?:WarehouseWestPalletReceipt;native_small_manual_case?:WarehouseSmallClampManualTransfer;native_small_receiving_case?:WarehouseSmallClampReceivingTransfer;native_source_long_plan?:WarehouseLongSourceOperationPlan;native_heavy_plan?:WarehouseHeavyInboundPlan;native_manual_case?:WarehouseManualTransfer;native_additional_heavy_plans?:readonly WarehouseScenarioAdditionalHeavyPlan[];native_long_crossdock_plan?:LongPlan;native_receiving_cases?:readonly WarehouseReceivingManualTransfer[]}={}){
  alive();requireValue(isWarehouseScenarioPlan(value),'ISSUED_SCENARIO_PLAN_REQUIRED');
  // Preflight is non-owning: a rejected B must leave the bound A usable.
  requireValue(value.native_heavy_materialization===options.native_heavy_materialization,'SCENARIO_WEST_MATERIALIZATION_IDENTITY_REQUIRED');
  requireValue(value.native_small_manual_case===options.native_small_manual_case&&value.native_small_receiving_case===options.native_small_receiving_case,'SCENARIO_SMALL_FACTORY_IDENTITY_REQUIRED');
  if(options.native_small_manual_case)requireValue(isWarehouseSmallClampManualTransfer(options.native_small_manual_case),'ISSUED_SMALL_MANUAL_CASE_REQUIRED');
  if(options.native_small_receiving_case)requireValue(isWarehouseSmallClampReceivingTransfer(options.native_small_receiving_case)&&options.native_small_receiving_case.dependency.native_manual_case===options.native_small_manual_case&&options.native_small_receiving_case.tool_token===options.native_small_manual_case?.tool_token,'SCENARIO_SAME_SMALL_TOOL_REQUIRED');
  requireValue(!(options.native_source_long_plan&&options.native_long_crossdock_plan),'SOURCE_LONG_AND_EXTRA_CROSSDOCK_ARE_MUTUALLY_EXCLUSIVE');
  requireValue(value.native_source_long_plan===options.native_source_long_plan,'SCENARIO_SOURCE_LONG_PLAN_IDENTITY_REQUIRED');
  if(options.native_source_long_plan)requireValue(isWarehouseLongSourceOperationPlan(options.native_source_long_plan)&&sourceLongSource===options.native_source_long_plan&&sourceLong,'SCENARIO_SOURCE_LONG_PLAN_NOT_PREPARED');
  requireValue(value.native_long_crossdock_plan===options.native_long_crossdock_plan,'SCENARIO_LONG_PLAN_IDENTITY_REQUIRED');
  if(options.native_long_crossdock_plan)requireValue(isWarehouseLongScenarioPlan(options.native_long_crossdock_plan)&&longSource===options.native_long_crossdock_plan&&long,'SCENARIO_LONG_PLAN_NOT_PREPARED');
  const incomingReceiving=options.native_receiving_cases??[];
  requireValue(incomingReceiving.every(isWarehouseReceivingManualTransfer)&&new Set(incomingReceiving.map(c=>c.handling_unit_id)).size===incomingReceiving.length&&new Set(incomingReceiving.flatMap(c=>c.participant_actor_ids)).size===incomingReceiving.length,'UNIQUE_ISSUED_RECEIVING_CASES_REQUIRED');
  requireValue((value.native_receiving_cases??[]).every(c=>incomingReceiving.includes(c)),'SCENARIO_RECEIVING_FACTORY_IDENTITY_REQUIRED');
  if(options.native_manual_case)requireValue(isWarehouseManualTransfer(options.native_manual_case),'ISSUED_MANUAL_TRANSFER_REQUIRED');
  if(value.native_manual_case)requireValue(value.native_manual_case===options.native_manual_case,'SCENARIO_MANUAL_FACTORY_IDENTITY_REQUIRED');
  const needsHeavy=value.jobs.some(j=>j.native_case==='connected_pallet455'),needsAdditional=value.jobs.some(j=>j.native_case==='additional_heavy'),incomingAdditional=options.native_additional_heavy_plans??[];
  if(needsHeavy)requireValue(isWarehouseHeavyInboundPlan(options.native_heavy_plan)&&value.native_heavy_plan===options.native_heavy_plan,'SCENARIO_NATIVE_HEAVY_PLAN_REQUIRED');
  requireValue(incomingAdditional.every(isWarehouseAdditionalHeavyPlan)&&(value.native_additional_heavy_plans??[]).every(p=>incomingAdditional.includes(p)),'SCENARIO_ADDITIONAL_FACTORY_IDENTITY_REQUIRED');
  if(needsAdditional)requireValue(needsHeavy&&incomingAdditional.length,'SCENARIO_PRIMARY_AND_ADDITIONAL_PLANS_REQUIRED');
  // Cached IDs must also validate yaw/speed/points on every bind, not just on
  // their first compilation. New pure gait preparation restores prior poses.
  for(const r of value.routes)if(r.mode==='pedestrian')preparePedestrianRoute(r);
  plan=undefined;current=undefined;
  try{
   if(smallReceiving!==options.native_small_receiving_case)smallReceiving?.dispose();
   if(small!==options.native_small_manual_case)small?.dispose();
   small=options.native_small_manual_case;smallReceiving=options.native_small_receiving_case;smallReceiving?.reset();small?.reset();
   if(!options.native_source_long_plan&&sourceLong){sourceLong.dispose();sourceLong=undefined;sourceLongSource=undefined;++longEpoch;}
   if(!options.native_long_crossdock_plan&&long){long.dispose();long=undefined;longSource=undefined;++longEpoch;}
   for(const c of receivingCases)if(!incomingReceiving.includes(c))c.dispose();receivingCases=[...incomingReceiving];for(const c of receivingCases)c.reset();
   if(manual!==options.native_manual_case)manual?.dispose();manual=options.native_manual_case;manual?.reset();
   additional?.dispose();additional=undefined;additionalPlans=[];heavy?.dispose();heavy=undefined;heavySource=undefined;restore(original);scene.updateMatrixWorld(true);
   if(needsHeavy){heavySource=options.native_heavy_plan!;heavy=createWarehouseHeavyInboundScene(scene,bundle,heavySource);}
   if(needsAdditional){additionalPlans=incomingAdditional;additional=createWarehouseAdditionalHeavyScene(scene,bundle,additionalPlans);}
   plan=value;refusal=null;return snapshot();
  }catch(error){
   // Ownership teardown cannot generally be undone. Never leave the old plan
   // advertised as ready if a later native construction/reset has failed.
   plan=undefined;current=undefined;refusal=error instanceof Error?error.message:String(error);
   try{additional?.dispose();}finally{additional=undefined;additionalPlans=[];try{heavy?.dispose();}finally{heavy=undefined;heavySource=undefined;restore(original);scene.updateMatrixWorld(true);}}
   throw error;
  }
 }
 // Inactive controllers restore their own source roots before the active
 // owner applies its clone. Two factories may retain the same original actor;
 // an unstarted controller must never re-add it after the active one runs.
 function applyNativeCases(frame?:ScenarioNativeSample){
  const mt=frame?.native_manual_local_s??0,st=frame?.native_small_manual_local_s??0,mActive=frame?.native_manual_local_s!=null&&!!manual&&mt<manual.duration_s,sActive=frame?.native_small_manual_local_s!=null&&!!small&&st<small.duration_s,smallRow=frame?.native_small_receiving??null,rows=frame?.native_receiving??[];
  heavy?.apply(frame?.native_heavy_local_s??0);additional?.apply(frame?.native_additional_heavy??[]);long?.apply(frame?.native_long_local_s??0);sourceLong?.apply(frame?.native_source_long_local_s??0);
  if(!mActive)manual?.apply(mt);if(!sActive)small?.apply(st);
  for(const c of receivingCases){const r=rows.find(r=>r.request_id===c.request_id);if(!r?.active)c.apply(r?c.duration_s:0);}
  if(!smallRow?.active){if(smallRow)smallReceiving!.apply(smallReceiving!.duration_s);else smallReceiving?.reset();}
  if(mActive)manual!.apply(mt);if(sActive)small!.apply(st);
  for(const c of receivingCases){const r=rows.find(r=>r.request_id===c.request_id);if(r?.active)c.apply(r.local_s);}
  if(smallRow?.active)smallReceiving!.apply(smallRow.local_s);
 }
 function vehiclePose(row:VehicleFrame){const root=vehicles.get(row.vehicle_id);requireValue(root,'UNKNOWN_SCENARIO_VEHICLE');const m=pose(row.position,row.yaw_rad);if(root.parent)m.premultiply(root.parent.matrixWorld.clone().invert());m.decompose(root.position,root.quaternion,root.scale);for(const name of ['joint__carriage','joint__reach','joint__fork_L','joint__fork_R'])requireValue(root.getObjectByName(name),'SCENARIO_FORK_JOINT_MISSING');root.getObjectByName('joint__carriage')!.position.y=row.fork_top_m;const reach=root.getObjectByName('joint__reach')!;reach.position.z=rests.get(reach)!.p.z+row.extension_m;if(row.fork_halfspacing_m!==undefined){requireValue(Number.isFinite(row.fork_halfspacing_m)&&row.fork_halfspacing_m>0,'SCENARIO_VALID_FORK_SPACING_REQUIRED');root.getObjectByName('joint__fork_L')!.position.x=-row.fork_halfspacing_m;root.getObjectByName('joint__fork_R')!.position.x=row.fork_halfspacing_m;}for(const side of ['L','R'] as const){const steer=root.getObjectByName('joint__rear_steer_'+side)!;steer.quaternion.copy(rests.get(steer)!.q).multiply(new THREE.Quaternion().setFromAxisAngle(Y,row.rear_steer_rad[side]));for(const axle of ['front','rear']){const n=root.getObjectByName('joint__wheel_'+axle+'_'+side)!;n.quaternion.copy(rests.get(n)!.q).multiply(new THREE.Quaternion().setFromAxisAngle(X,row.wheel_angles_rad[axle+'_'+side]));}}root.updateWorldMatrix(true,true);}
 function apply(at_s:number){alive();requireValue(plan,'SCENARIO_PLAN_NOT_BOUND');const next=plan.sample(at_s),previous=original.map(r=>save(r.node)),old=current;try{
   const sourceLongTime=next.native_source_long_local_s??null;requireValue(sourceLongTime===null||sourceLongSource&&Number.isFinite(sourceLongTime)&&sourceLongTime>=0&&sourceLongTime<=sourceLongSource.duration_s,'SCENARIO_SOURCE_LONG_TIME_INVALID');const sourceLongFrame=sourceLongTime===null?null:sourceLongSource!.sample(sourceLongTime);
   const smallTime=next.native_small_manual_local_s??null,smallFrame=smallTime===null?null:(requireValue(small,'SCENARIO_SMALL_CASE_REQUIRED'),small.sample(smallTime)),smallReceivingRow=next.native_small_receiving??null,smallReceivingFrame=smallReceivingRow?(requireValue(smallReceiving&&smallReceiving.request_id===smallReceivingRow.request_id,'SCENARIO_SMALL_RECEIVING_CASE_REQUIRED'),smallReceiving.sample(smallReceivingRow.active?smallReceivingRow.local_s:smallReceiving.duration_s)):null;
   const manualTime=next.native_manual_local_s??null,manualFrame=manualTime!==null?(requireValue(manual,'SCENARIO_MANUAL_CASE_REQUIRED'),manual.sample(manualTime)):null,receivingRows=next.native_receiving??[],receivingByHU=new Map<string,ReturnType<WarehouseReceivingManualTransfer['sample']>>(),activeReceivers=new Set<string>();requireValue(new Set(receivingRows.map(r=>r.request_id)).size===receivingRows.length,'DUPLICATE_RECEIVING_DISPLAY_ROW');for(const row of receivingRows){const c=receivingCases.find(c=>c.request_id===row.request_id);requireValue(c,'SCENARIO_RECEIVING_CASE_REQUIRED');requireValue(Number.isFinite(row.local_s)&&row.local_s>=0&&row.local_s<=c.duration_s,'SCENARIO_RECEIVING_TIME_INVALID');receivingByHU.set(c.handling_unit_id,c.sample(row.active?row.local_s:c.duration_s));if(row.active)for(const id of c.participant_actor_ids)activeReceivers.add(id);}
   requireValue(next.cargo.filter(h=>sourceCargo.has(h.handling_unit_id)).length===sourceCargo.size,'SCENARIO_SOURCE_STOCK_IDENTITY_CHANGED');
   for(const h of next.cargo){const source=sourceCargo.get(h.handling_unit_id);if(!source){if(smallReceiving&&h.handling_unit_id===smallReceiving.handling_unit_id){if(!smallReceivingFrame){requireValue(!h.visible&&!h.attached&&h.position===null,'SCENARIO_SMALL_RECEIVING_NOT_STARTED');continue;}const e=smallReceivingFrame.cargo;requireValue(h.visible===e.visible&&h.attached===e.attached&&h.position!==null&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...e.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-e.yaw_rad),Math.cos(h.yaw_rad-e.yaw_rad)))<=1e-8,'SCENARIO_SMALL_RECEIVING_FRAME_MISMATCH');continue;}const received=receivingByHU.get(h.handling_unit_id);if(received){const expected=received.cargo;requireValue(h.visible===expected.visible&&h.attached===expected.attached&&h.position!==null&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...expected.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-expected.yaw_rad),Math.cos(h.yaw_rad-expected.yaw_rad)))<=1e-8,'SCENARIO_RECEIVING_CARGO_FRAME_MISMATCH');continue;}if(receivingCases.some(c=>c.handling_unit_id===h.handling_unit_id)){requireValue(!h.visible&&!h.attached,'SCENARIO_RECEIVING_CASE_NOT_STARTED');continue;}if(!h.visible&&h.position===null&&!h.attached)continue;requireValue((!!heavySource&&h.handling_unit_id===heavySource.fixture.receipt.handling_unit_id)||additionalPlans.some(p=>p.case.receipt.handling_unit_id===h.handling_unit_id)||(!!longSource&&h.handling_unit_id===longSource.fixture.handling_unit_id),'UNKNOWN_SCENARIO_CARGO');continue;}if(sourceLongFrame&&h.handling_unit_id===sourceLongFrame.cargo.handling_unit_id){const expected=sourceLongFrame.cargo;requireValue(h.visible&&h.attached===(expected.holder==='F02')&&h.position!==null&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...expected.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-expected.yaw_rad),Math.cos(h.yaw_rad-expected.yaw_rad)))<=1e-8,'SCENARIO_SOURCE_LONG_CARGO_FRAME_MISMATCH');continue;}if(smallFrame&&h.handling_unit_id===small!.handling_unit_id){const e=smallFrame.cargo;requireValue(h.visible===e.visible&&h.attached===e.attached&&h.position!==null&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...e.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-e.yaw_rad),Math.cos(h.yaw_rad-e.yaw_rad)))<=1e-8,'SCENARIO_SMALL_NATIVE_FRAME_MISMATCH');continue;}if(manualFrame&&h.handling_unit_id===manualFrame.handling_unit_id){const expected=manualFrame.cargo;requireValue(h.visible===expected.visible&&h.position!==null&&h.attached===expected.attached&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...expected.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-expected.yaw_rad),Math.cos(h.yaw_rad-expected.yaw_rad)))<=1e-8,'SCENARIO_MANUAL_CARGO_FRAME_MISMATCH');continue;}requireValue(!h.attached&&h.visible&&h.position!==null&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...source.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-source.yaw_rad),Math.cos(h.yaw_rad-source.yaw_rad)))<=1e-8,'SCENARIO_NATIVE_HU_HANDOFF_REQUIRED:'+h.handling_unit_id);}
   restore(original);scene.updateMatrixWorld(true);
   applyNativeCases(next);
   for(const row of next.actors){if(smallFrame&&smallTime!<small!.duration_s&&small!.participant_actor_ids.includes(row.actor_id)||smallReceivingRow?.active&&row.actor_id===smallReceiving!.actor_id)continue;if(activeReceivers.has(row.actor_id))continue;if(manualFrame&&manualTime!<manual!.duration_s&&manual!.participant_actor_ids.includes(row.actor_id))continue;const root=actors.get(row.actor_id),worker=bundle.registry.workers.find(w=>w.actor_id===row.actor_id);requireValue(root&&worker,'UNKNOWN_SCENARIO_ACTOR');if(worker.assigned_vehicle_id)continue;requireValue(row.role===worker.baseline_role,'SCENARIO_ROLE_TRANSITION_ADAPTER_REQUIRED');if(row.route_id){const prepared=gaits.get(row.route_id);requireValue(prepared&&prepared.route.actor_id===row.actor_id,'SCENARIO_NATIVE_ROUTE_NOT_PREPARED:'+row.route_id);const p=prepared.gait.sample(row.route_at_s),m=pose(p.root_world,p.yaw_rad);if(root.parent)m.premultiply(root.parent.matrixWorld.clone().invert());m.decompose(root.position,root.quaternion,root.scale);for(const[name,q]of Object.entries(p.joint_rotations)){const n=root.getObjectByName(name);requireValue(n,'SCENARIO_NATIVE_GAIT_JOINT_MISSING');n.quaternion.fromArray(q);}root.updateWorldMatrix(true,true);}else{const m=pose(row.position,row.yaw_rad);if(root.parent)m.premultiply(root.parent.matrixWorld.clone().invert());m.decompose(root.position,root.quaternion,root.scale);root.updateWorldMatrix(true,true);}}
   for(const row of next.vehicles)if(!sourceLongFrame?.vehicles.some(v=>v.vehicle_id===row.vehicle_id&&v.controlled))vehiclePose(row);
   current=next;refusal=null;return snapshot();
  }catch(e){try{applyNativeCases(old);}finally{restore(previous);scene.updateMatrixWorld(true);}current=old;refusal=e instanceof Error?e.message:String(e);throw e;}}
 function snapshot(){const visibleActors=new Map(actors);if(manual||receivingCases.length||small||smallReceiving)scene.traverse(n=>{if(n.userData.semanticKind==='actor'&&actors.has(n.userData.semanticId))visibleActors.set(n.userData.semanticId,n);});return {ready:!!plan&&!disposed,disposed,at_s:current?.at_s??null,refusal,actors:actors.size,vehicles:vehicles.size,stock_HUs:sourceCargo.size,prepared_native_routes:gaits.size,native_routes:[...gaits].map(([route_id,{gait}])=>({route_id,duration_s:gait.duration_s,phases:gait.phases.length})),actor_frames:[...visibleActors].map(([actor_id,n])=>({actor_id,uuid:n.uuid,parent_uuid:n.parent?.uuid,position:n.getWorldPosition(new THREE.Vector3()).toArray(),quaternion:n.getWorldQuaternion(new THREE.Quaternion()).toArray()})),vehicle_frames:[...vehicles].map(([vehicle_id,n])=>({vehicle_id,uuid:n.uuid,position:n.getWorldPosition(new THREE.Vector3()).toArray(),quaternion:n.getWorldQuaternion(new THREE.Quaternion()).toArray()})),native_heavy:heavy?.snapshot()??null,native_small_manual:small?.snapshot()??null,native_small_receiving:smallReceiving?.snapshot()??null,native_manual:manual?.snapshot()??null,native_additional_heavy:additional?.snapshot()??null,native_long:long?.snapshot()??null,native_source_long:sourceLong?.snapshot()??null,native_receiving:receivingCases.map(c=>c.snapshot()),capabilities:{native_unloaded_walk:true,native_vehicle_route:true,source_whole_HU_long_source_transport:!!sourceLong,source_whole_HU_manual_pickup:!!manual,source_whole_HU_pack_handoff:manual?.partial_native_case===false,source_whole_HU_shipping:manual?.partial_native_case===false,source_whole_HU_receiving:receivingCases.length>0},source_kind:'visual_fixture',engine_operation:false};}
 function dispose(){if(disposed)return;++longEpoch;smallReceiving?.dispose();smallReceiving=undefined;small?.dispose();small=undefined;sourceLong?.dispose();sourceLong=undefined;sourceLongSource=undefined;long?.dispose();long=undefined;longSource=undefined;for(const c of receivingCases)c.dispose();receivingCases=[];manual?.dispose();manual=undefined;additional?.dispose();additional=undefined;heavy?.dispose();heavy=undefined;restore(original);scene.updateMatrixWorld(true);owners.delete(scene);disposed=true;}
 return {preparePedestrianRoute,pedestrianDuration,prepareLongCrossdock,prepareSourceLong,bind,apply,reset,snapshot,dispose};
}
