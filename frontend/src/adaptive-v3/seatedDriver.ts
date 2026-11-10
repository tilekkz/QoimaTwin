import * as THREE from 'three';
import type {WorkerInstance} from './workerRoles';

const boundActors=new WeakSet<WorkerInstance>();
const occupiedVehicles=new WeakMap<THREE.Object3D,WorkerInstance>();

export type SeatedDriverPose={schema_id:string;worker_glb_sha256:string;driver:{worker_root_translation:[number,number,number];jointEulerXYZ:Record<string,[number,number,number]>;minimum_helmet_roof_gap_m:number;expected_grips:Record<string,number[]>;expected_soles:Record<string,number[]>}};

export function validateSeatedDriverPose(value:unknown):SeatedDriverPose{
  const d=value as SeatedDriverPose;
  if(!d||d.schema_id!=='qoima.seated-driver.v3'||!d.driver||d.driver.worker_root_translation?.join(',')!=='0,0.29,-0.615'||Object.keys(d.driver.jointEulerXYZ??{}).length!==15)throw Error('Некорректная поза водителя.');
  for(const [name,angles] of Object.entries(d.driver.jointEulerXYZ))if(!name.startsWith('joint__')||!Array.isArray(angles)||angles.length!==3||!angles.every(Number.isFinite))throw Error('Некорректный сустав водителя.');
  return d;
}

/** Reparent the existing instance: no actor creation, cloning or registry edit. */
export function bindSeatedDriver(vehicle:THREE.Object3D,actor:WorkerInstance,pose:SeatedDriverPose){
  if(actor.disposed||actor.role!=='forklift_driver')throw Error('Для посадки нужен действующий работник с ролью водителя.');
  if(boundActors.has(actor))throw Error('Этот работник уже назначен в машину.');
  if(occupiedVehicles.has(vehicle))throw Error('Место водителя уже занято.');
  if(actor.root.scale.toArray().some(v=>Math.abs(v-1)>1e-7))throw Error('Масштаб работника должен оставаться1:1.');
  for(const name of ['anchor_driver_seat','anchor_footrest_L','anchor_footrest_R','anchor_steering_grip_L','anchor_steering_grip_R'])if(!vehicle.getObjectByName(name))throw Error('В машине отсутствует '+name);
  const joints=new Map<string,THREE.Object3D>();
    for(const name of Object.keys(pose.driver.jointEulerXYZ)){const n=actor.root.getObjectByName(name);if(!n)throw Error('В работнике отсутствует '+name);joints.set(name,n);}
    const previousParent=actor.root.parent,previousPosition=actor.root.position.clone(),previousQuaternion=actor.root.quaternion.clone();
    const previousJoints=new Map<THREE.Object3D,THREE.Quaternion>();
    actor.root.traverse(n=>{if(n.name.startsWith('joint__'))previousJoints.set(n,n.quaternion.clone());});
    const previousAssignment=actor.root.userData.assignment,previousAnchor=actor.root.userData.vehicleAnchor;
    let released=false;boundActors.add(actor);occupiedVehicles.set(vehicle,actor);
    vehicle.add(actor.root);
    actor.root.userData.assignment='seated_existing_actor';actor.root.userData.vehicleAnchor='anchor_driver_seat';
    function reset(){
      if(actor.disposed||released)throw Error('Привязка водителя уже освобождена.');
      if(actor.role!=='forklift_driver')throw Error('Перед сменой роли водитель должен покинуть привязку к машине.');
      actor.root.position.fromArray(pose.driver.worker_root_translation);actor.root.quaternion.identity();
      for(const side of ['L','R'])actor.root.getObjectByName('joint__palm_roll_'+side)?.quaternion.identity();
      for(const [name,angles] of Object.entries(pose.driver.jointEulerXYZ))joints.get(name)!.rotation.set(...angles,'XYZ');
      vehicle.updateMatrixWorld(true);
    }
    function snapshot(){
      vehicle.updateWorldMatrix(true,true);const point=(n:THREE.Object3D)=>vehicle.worldToLocal(n.getWorldPosition(new THREE.Vector3())).toArray();
      const seat=point(actor.root.getObjectByName('anchor_seat_contact')!);
      const hands=Object.fromEntries(['L','R'].map(side=>[side,point(actor.root.getObjectByName('anchor_hand_grip_'+side)!)]));
      const feet=Object.fromEntries(['L','R'].map(side=>[side,point(actor.root.getObjectByName('anchor_foot_floor_'+side)!)]));
      return {actorId:actor.actorId,role:actor.role,disposed:actor.disposed,assignment:'seated_existing_actor',warehouse_headcount_delta:0,
        root_local:actor.root.position.toArray(),scale:actor.root.scale.toArray(),seat_local:seat,hands_local:hands,feet_local:feet,
        seat_error_m:new THREE.Vector3().fromArray(seat).distanceTo(new THREE.Vector3().fromArray(point(vehicle.getObjectByName('anchor_driver_seat')!))),
        grip_error_m:Object.fromEntries(['L','R'].map(side=>[side,new THREE.Vector3().fromArray(hands[side]).distanceTo(new THREE.Vector3().fromArray(point(vehicle.getObjectByName('anchor_steering_grip_'+side)!)))])),
        sole_error_m:Object.fromEntries(['L','R'].map(side=>[side,new THREE.Vector3().fromArray(feet[side]).distanceTo(new THREE.Vector3().fromArray(point(vehicle.getObjectByName('anchor_footrest_'+side)!)))]))};
    }
    function release(){
      if(released)return;released=true;boundActors.delete(actor);if(occupiedVehicles.get(vehicle)===actor)occupiedVehicles.delete(vehicle);
      if(actor.disposed)return;
      actor.root.removeFromParent();if(previousParent)previousParent.add(actor.root);
      actor.root.position.copy(previousPosition);actor.root.quaternion.copy(previousQuaternion);
      for(const [node,q] of previousJoints)node.quaternion.copy(q);
      if(previousAssignment===undefined)delete actor.root.userData.assignment;else actor.root.userData.assignment=previousAssignment;
      if(previousAnchor===undefined)delete actor.root.userData.vehicleAnchor;else actor.root.userData.vehicleAnchor=previousAnchor;
    }
    reset();return {actor,reset,snapshot,release};
}
