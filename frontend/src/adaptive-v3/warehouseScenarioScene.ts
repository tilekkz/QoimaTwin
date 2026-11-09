import * as THREE from 'three';
import {deriveNativeWorkerGaitRig,compileNativeWorkerGait,type CompiledWorkerGait} from './warehouseWorkerGait';
import {createWarehouseCargo} from './warehouseCargo';
import {createWarehouseHeavyInboundScene} from './warehouseHeavyInboundScene';
import type {WarehouseHeavyInboundPlan} from './warehouseHeavyInboundPlan';
import {isWarehouseScenarioPlan} from './warehouseScenarioExecution';
import type {WarehouseBundle,XYZ} from './warehouseTypes';

export type ScenarioNativeRoute={route_id:string;actor_id:string;mode:string;points_world:XYZ[];start_yaw_rad:number;speed_m_s:number;duration_s:number;from_node_id?:string};
type ActorFrame={actor_id:string;vehicle_id:string|null;role:string;position:XYZ;yaw_rad:number;activity:string;job_id:string|null;route_id:string|null;route_at_s:number};
type VehicleFrame={vehicle_id:string;actor_id:string;position:XYZ;yaw_rad:number;fork_top_m:number;extension_m:number;rear_steer_rad:{L:number;R:number};wheel_angles_rad:Record<string,number>};
type CargoFrame={handling_unit_id:string;position:XYZ|null;yaw_rad:number;visible:boolean;attached:boolean;location:unknown};
export type ScenarioNativeSample={at_s:number;actors:readonly ActorFrame[];vehicles:readonly VehicleFrame[];cargo:readonly CargoFrame[];native_heavy_local_s:number|null;native_heavy:unknown};
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
 let plan:ScenarioNativePlan|undefined,heavySource:WarehouseHeavyInboundPlan|undefined,heavy:ReturnType<typeof createWarehouseHeavyInboundScene>|undefined,current:ScenarioNativeSample|undefined,disposed=false,refusal:string|null=null;
 owners.add(scene);
 function alive(){requireValue(!disposed,'SCENARIO_SCENE_DISPOSED');}
 function preparePedestrianRoute(route:ScenarioNativeRoute){
  alive();requireValue(route.mode==='pedestrian','NATIVE_PEDESTRIAN_ROUTE_REQUIRED');const actor=actors.get(route.actor_id),worker=bundle.registry.workers.find(w=>w.actor_id===route.actor_id);requireValue(actor&&worker&&!worker.assigned_vehicle_id,'ORIGINAL_UNSEATED_ACTOR_REQUIRED');
  const cached=gaits.get(route.route_id);if(cached){requireValue(JSON.stringify(cached.route.points_world)===JSON.stringify(route.points_world)&&cached.route.actor_id===route.actor_id,'SCENARIO_ROUTE_ID_REUSED');return motion(cached.gait);}
  let rig=rigCache.get(route.actor_id);if(!rig){const previous=original.map(r=>save(r.node));try{restore(original);scene.updateMatrixWorld(true);rig=deriveNativeWorkerGaitRig(actor);rigCache.set(route.actor_id,rig);}finally{restore(previous);scene.updateMatrixWorld(true);}}
  const points=route.points_world.length?route.points_world:[bundle.layout.walk.nodes.find(n=>n.node_id===route.from_node_id)?.world_pos??(rests.get(actor)!.p.toArray() as XYZ)];requireValue(route.points_world.length>0||route.duration_s===0,'NONEMPTY_NATIVE_ROUTE_REQUIRED');
  const gait=compileNativeWorkerGait(rig,points,route.start_yaw_rad,route.speed_m_s,fixed);gaits.set(route.route_id,{route:structuredClone(route),gait});return motion(gait);
 }
 function motion(gait:CompiledWorkerGait){return {duration_s:gait.duration_s,sample:(at_s:number)=>{const p=gait.sample(at_s);return {position:[...p.root_world] as XYZ,yaw_rad:p.yaw_rad};},native_timing:true as const};}
 const pedestrianDuration=(route:ScenarioNativeRoute)=>preparePedestrianRoute(route).duration_s;
 function reset(){alive();heavy?.apply(0);restore(original);scene.updateMatrixWorld(true);current=undefined;refusal=null;}
 function bind(value:ScenarioNativePlan,options:{native_heavy_plan?:WarehouseHeavyInboundPlan}={}){alive();requireValue(isWarehouseScenarioPlan(value),'ISSUED_SCENARIO_PLAN_REQUIRED');heavy?.dispose();heavy=undefined;heavySource=undefined;restore(original);scene.updateMatrixWorld(true);for(const r of value.routes)if(r.mode==='pedestrian'&&!gaits.has(r.route_id))preparePedestrianRoute(r);plan=value;current=undefined;if(value.jobs.some(j=>j.native_case==='connected_pallet455')){heavySource=options.native_heavy_plan;requireValue(heavySource,'SCENARIO_NATIVE_HEAVY_PLAN_REQUIRED');heavy=createWarehouseHeavyInboundScene(scene,bundle,heavySource);}return snapshot();}
 function vehiclePose(row:VehicleFrame){const root=vehicles.get(row.vehicle_id);requireValue(root,'UNKNOWN_SCENARIO_VEHICLE');const m=pose(row.position,row.yaw_rad);if(root.parent)m.premultiply(root.parent.matrixWorld.clone().invert());m.decompose(root.position,root.quaternion,root.scale);for(const name of ['joint__carriage','joint__reach','joint__fork_L','joint__fork_R'])requireValue(root.getObjectByName(name),'SCENARIO_FORK_JOINT_MISSING');root.getObjectByName('joint__carriage')!.position.y=row.fork_top_m;const reach=root.getObjectByName('joint__reach')!;reach.position.z=rests.get(reach)!.p.z+row.extension_m;for(const side of ['L','R'] as const){const steer=root.getObjectByName('joint__rear_steer_'+side)!;steer.quaternion.copy(rests.get(steer)!.q).multiply(new THREE.Quaternion().setFromAxisAngle(Y,row.rear_steer_rad[side]));for(const axle of ['front','rear']){const n=root.getObjectByName('joint__wheel_'+axle+'_'+side)!;n.quaternion.copy(rests.get(n)!.q).multiply(new THREE.Quaternion().setFromAxisAngle(X,row.wheel_angles_rad[axle+'_'+side]));}}root.updateWorldMatrix(true,true);}
 function apply(at_s:number){alive();requireValue(plan,'SCENARIO_PLAN_NOT_BOUND');const next=plan.sample(at_s),previous=original.map(r=>save(r.node)),old=current;try{
   requireValue(next.cargo.filter(h=>sourceCargo.has(h.handling_unit_id)).length===sourceCargo.size,'SCENARIO_SOURCE_STOCK_IDENTITY_CHANGED');
   for(const h of next.cargo){const source=sourceCargo.get(h.handling_unit_id);if(!source){if(!h.visible&&h.position===null&&!h.attached)continue;requireValue(!!heavySource&&h.handling_unit_id===heavySource.fixture.receipt.handling_unit_id,'UNKNOWN_SCENARIO_CARGO');continue;}requireValue(!h.attached&&h.visible&&h.position!==null&&new THREE.Vector3(...h.position).distanceTo(new THREE.Vector3(...source.position))<=2e-6&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-source.yaw_rad),Math.cos(h.yaw_rad-source.yaw_rad)))<=1e-8,'SCENARIO_NATIVE_HU_HANDOFF_REQUIRED:'+h.handling_unit_id);}
   restore(original);scene.updateMatrixWorld(true);
   if(heavy)heavy.apply(next.native_heavy_local_s??0);
   for(const row of next.actors){const root=actors.get(row.actor_id),worker=bundle.registry.workers.find(w=>w.actor_id===row.actor_id);requireValue(root&&worker,'UNKNOWN_SCENARIO_ACTOR');if(worker.assigned_vehicle_id)continue;requireValue(row.role===worker.baseline_role,'SCENARIO_ROLE_TRANSITION_ADAPTER_REQUIRED');if(row.route_id){const prepared=gaits.get(row.route_id);requireValue(prepared&&prepared.route.actor_id===row.actor_id,'SCENARIO_NATIVE_ROUTE_NOT_PREPARED:'+row.route_id);const p=prepared.gait.sample(row.route_at_s),m=pose(p.root_world,p.yaw_rad);if(root.parent)m.premultiply(root.parent.matrixWorld.clone().invert());m.decompose(root.position,root.quaternion,root.scale);for(const[name,q]of Object.entries(p.joint_rotations)){const n=root.getObjectByName(name);requireValue(n,'SCENARIO_NATIVE_GAIT_JOINT_MISSING');n.quaternion.fromArray(q);}root.updateWorldMatrix(true,true);}else{const m=pose(row.position,row.yaw_rad);if(root.parent)m.premultiply(root.parent.matrixWorld.clone().invert());m.decompose(root.position,root.quaternion,root.scale);root.updateWorldMatrix(true,true);}}
   for(const row of next.vehicles)if(!(heavy&&row.vehicle_id==='FL01'&&next.native_heavy_local_s!==null&&next.native_heavy_local_s<heavySource!.duration_s))vehiclePose(row);
   current=next;refusal=null;return snapshot();
  }catch(e){try{heavy?.apply(old?.native_heavy_local_s??0);}finally{restore(previous);scene.updateMatrixWorld(true);}current=old;refusal=e instanceof Error?e.message:String(e);throw e;}}
 function snapshot(){return {ready:!!plan&&!disposed,disposed,at_s:current?.at_s??null,refusal,actors:actors.size,vehicles:vehicles.size,stock_HUs:sourceCargo.size,prepared_native_routes:gaits.size,native_routes:[...gaits].map(([route_id,{gait}])=>({route_id,duration_s:gait.duration_s,phases:gait.phases.length})),actor_frames:[...actors].map(([actor_id,n])=>({actor_id,uuid:n.uuid,parent_uuid:n.parent?.uuid,position:n.getWorldPosition(new THREE.Vector3()).toArray(),quaternion:n.getWorldQuaternion(new THREE.Quaternion()).toArray()})),vehicle_frames:[...vehicles].map(([vehicle_id,n])=>({vehicle_id,uuid:n.uuid,position:n.getWorldPosition(new THREE.Vector3()).toArray(),quaternion:n.getWorldQuaternion(new THREE.Quaternion()).toArray()})),native_heavy:heavy?.snapshot()??null,capabilities:{native_unloaded_walk:true,native_vehicle_route:true,source_whole_HU_manual_pickup:false,source_whole_HU_pack_handoff:false,source_whole_HU_shipping:false},source_kind:'visual_fixture',engine_operation:false};}
 function dispose(){if(disposed)return;heavy?.dispose();heavy=undefined;restore(original);scene.updateMatrixWorld(true);owners.delete(scene);disposed=true;}
 return {preparePedestrianRoute,pedestrianDuration,bind,apply,reset,snapshot,dispose};
}
