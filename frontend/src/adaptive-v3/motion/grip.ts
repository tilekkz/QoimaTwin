import * as THREE from 'three';
import type {WorkerInstance} from '../workerRoles';

const assignedActors=new WeakSet<WorkerInstance>();
const occupiedCarts=new WeakMap<THREE.Object3D,WorkerInstance>();
const armNames=['joint__upper_arm_L','joint__forearm_L','joint__palm_roll_L','joint__hand_L','joint__upper_arm_R','joint__forearm_R','joint__palm_roll_R','joint__hand_R'] as const;
type Triple=[number,number,number];
export type PickerPushPose={schema_id:string;units:string;worker_scale:number;cart_offset_in_worker_m:Triple;grip_radius_m:number;grip_centres_cart_m:Triple[];jointEulerXYZ:Record<string,Triple>};

export function validatePickerPushPose(value:unknown):PickerPushPose{
  const p=value as PickerPushPose;
  const triple=(v:unknown):v is Triple=>Array.isArray(v)&&v.length===3&&v.every(x=>typeof x==='number'&&Number.isFinite(x));
  if(!p||p.schema_id!=='qoima.picker-push-pose.v3'||p.units!=='m'||p.worker_scale!==1||!triple(p.cart_offset_in_worker_m)||p.cart_offset_in_worker_m.join(',')!=='0,0,0.7975'||p.grip_radius_m!==.0225||!Array.isArray(p.grip_centres_cart_m)||p.grip_centres_cart_m.length!==2||p.grip_centres_cart_m.some((v,i)=>!triple(v)||v.join(',')!==[i===0?-.195:.195,.9775,-.4375].join(','))||Object.keys(p.jointEulerXYZ??{}).length!==armNames.length||armNames.some(n=>!triple(p.jointEulerXYZ[n])||p.jointEulerXYZ[n].some(a=>Math.abs(a)>Math.PI)))throw Error('Некорректная поза комплектовщика.');
  return structuredClone(p);
}

function requireUnitWorldScale(node:THREE.Object3D){
  node.updateWorldMatrix(true,false);
  if(node.getWorldScale(new THREE.Vector3()).toArray().some(v=>Math.abs(v-1)>1e-7))throw Error('Масштаб работника и тележки должен оставаться 1:1.');
}

/** Bind one existing employee to one existing cart; no clone or registry write. */
export function bindPickerGrip(cart:THREE.Object3D,actor:WorkerInstance,input:PickerPushPose){
  const pose=validatePickerPushPose(input);
  if(actor.disposed||actor.role!=='picker')throw Error('Нужен действующий комплектовщик.');
  if(assignedActors.has(actor))throw Error('Работник уже держит тележку.');
  if(occupiedCarts.has(cart))throw Error('Тележка уже занята.');
  if(cart===actor.root||actor.root.getObjectById(cart.id))throw Error('Тележка не может быть дочерним узлом работника.');
  if(actor.root.scale.toArray().some(v=>Math.abs(v-1)>1e-7))throw Error('Масштаб работника должен оставаться 1:1.');
  requireUnitWorldScale(cart);requireUnitWorldScale(actor.root);
  const hands=['L','R'].map(side=>actor.root.getObjectByName('anchor_hand_grip_'+side));
  const grips=['L','R'].map(side=>cart.getObjectByName('anchor_grip_'+side));
  const joints=new Map<string,THREE.Object3D>();
  for(const name of armNames){const n=actor.root.getObjectByName(name);if(!n)throw Error('Нет сустава '+name);joints.set(name,n);}
  if([...hands,...grips].some(n=>!n))throw Error('Отсутствует точка хвата.');
  const saved={parent:actor.root.parent,position:actor.root.position.clone(),quaternion:actor.root.quaternion.clone(),assignment:actor.root.userData.assignment,cartAnchor:actor.root.userData.cartAnchor};
  // Preserve the whole articulated pose: release also restores a future gait.
  const priorJoints=new Map<THREE.Object3D,THREE.Quaternion>();
  actor.root.traverse(n=>{if(n.name.startsWith('joint__'))priorJoints.set(n,n.quaternion.clone());});
  let released=false;
  function snapshot(){
    cart.updateWorldMatrix(true,true);const inverse=cart.matrixWorld.clone().invert();
    const point=(n:THREE.Object3D)=>n.getWorldPosition(new THREE.Vector3()).applyMatrix4(inverse);
    const axes=(n:THREE.Object3D)=>new THREE.Vector3(1,0,0).transformDirection(n.matrixWorld).transformDirection(inverse);
    const palm=(n:THREE.Object3D)=>new THREE.Vector3(0,0,1).transformDirection(n.matrixWorld).transformDirection(inverse);
    return {actorId:actor.actorId,actor_uuid:actor.root.uuid,cart_uuid:cart.uuid,role:actor.role,warehouse_headcount_delta:0,assignment:'pushing_existing_cart',root_local:actor.root.position.toArray(),scale:actor.root.scale.toArray(),
      hands:['L','R'].map((side,i)=>({side,hand_cart_m:point(hands[i]!).toArray(),handle_cart_m:point(grips[i]!).toArray(),error_m:point(hands[i]!).distanceTo(point(grips[i]!)),hand_axis_cart:axes(hands[i]!).toArray(),axis_error:Math.min(axes(hands[i]!).distanceTo(new THREE.Vector3(1,0,0)),axes(hands[i]!).distanceTo(new THREE.Vector3(-1,0,0))),palm_direction_cart:palm(hands[i]!).toArray(),palm_down_error:palm(hands[i]!).distanceTo(new THREE.Vector3(0,-Math.sin(3*Math.PI/8),Math.cos(3*Math.PI/8)))}))};
  }
  function reset(){
    if(released||actor.disposed)throw Error('Привязка хвата освобождена.');
    if(actor.role!=='picker')throw Error('Перед сменой роли нужно освободить тележку.');
    requireUnitWorldScale(cart);
    actor.root.position.fromArray(pose.cart_offset_in_worker_m).negate();actor.root.quaternion.identity();
    for(const n of priorJoints.keys())n.quaternion.identity();
    for(const [name,angles] of Object.entries(pose.jointEulerXYZ))joints.get(name)!.rotation.set(...angles,'XYZ');
    actor.root.userData.assignment='pushing_existing_cart';actor.root.userData.cartAnchor='anchor_handle_centre';
    if(snapshot().hands.some(h=>h.error_m>2e-5||h.axis_error>2e-5||h.palm_down_error>2e-5))throw Error('Кисти не совпали с реальной рукоятью или хватом сверху.');
  }
  function release(){
    if(released)return;released=true;assignedActors.delete(actor);if(occupiedCarts.get(cart)===actor)occupiedCarts.delete(cart);
    if(actor.disposed)return;
    actor.root.removeFromParent();if(saved.parent)saved.parent.add(actor.root);
    actor.root.position.copy(saved.position);actor.root.quaternion.copy(saved.quaternion);
    for(const [node,q] of priorJoints)node.quaternion.copy(q);
    for(const key of ['assignment','cartAnchor'] as const){if(saved[key]===undefined)delete actor.root.userData[key];else actor.root.userData[key]=saved[key];}
  }
  assignedActors.add(actor);occupiedCarts.set(cart,actor);cart.add(actor.root);
  try{reset();}catch(error){release();throw error;}
  return {actor,cart,reset,snapshot,release};
}
