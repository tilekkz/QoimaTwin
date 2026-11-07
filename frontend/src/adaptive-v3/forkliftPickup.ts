import * as THREE from 'three';

export type PickupKey={t:number;phase:string;label:string;root_z:number;fork_top:number;reach:number;attached:boolean};
export type PickupTimeline={schema_id:string;source_kind:string;engine_operation:boolean;duration_s:number;asset_id:string;HU_id:string;operator_id:string;vehicle_id:string;reservation_scope:string;action_space_bounds_m:{min:number[];max:number[]};stock_support_y_m:number;stock_centre_z_m:number;fork_halfspacing_m:number;attached_HU_local_xyz_m:[number,number,number];exclusive_resources:string[];keys:PickupKey[]};

export function validatePickupTimeline(value:unknown):PickupTimeline{
  if(!value||typeof value!=='object')throw Error('Нет описания цикла.');
  const d=value as PickupTimeline;
  if(d.schema_id!=='qoima.visual-pallet-pickup.v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.duration_s!==30||d.asset_id!=='forklift-pallet-low-fixture'||!Array.isArray(d.keys)||d.keys.length<2)throw Error('Неизвестное описание цикла.');
  if(d.keys[0].t!==0||d.keys.at(-1)!.t!==d.duration_s||d.fork_halfspacing_m!==.4||d.stock_support_y_m!==.18||d.stock_centre_z_m!==1.4||d.attached_HU_local_xyz_m.join(',')!=='0,0,0.6'||new Set(d.exclusive_resources).size!==3)throw Error('Нарушены опоры или ресурсы цикла.');
  d.keys.forEach((k,i)=>{
    if(![k.t,k.root_z,k.fork_top,k.reach].every(Number.isFinite)||typeof k.attached!=='boolean'||typeof k.label!=='string'||typeof k.phase!=='string'||(i&&k.t<=d.keys[i-1].t)||k.fork_top<.18||k.fork_top>1.5||k.reach<0||k.reach>.4)throw Error('Некорректный этап цикла.');
    const next=d.keys[i+1];if(!next)return;
    if(Math.min(k.fork_top,next.fork_top)<.7&&(k.reach!==.4||next.reach!==.4))throw Error('Низкие вилы требуют полного вылета.');
    if(k.root_z!==next.root_z&&!['controlled_insert','controlled_withdraw'].includes(k.phase)&&(k.fork_top!==.7||next.fork_top!==.7||k.reach!==0||next.reach!==0))throw Error('Для движения нужен транспортный профиль.');
  });
  return d;
}

/** Absolute time -> complete pose. No accumulated displacement or event effects. */
export function pickupAt(d:PickupTimeline,seconds:number){
  if(!Number.isFinite(seconds))throw Error('Время должно быть конечным числом.');
  const time=Math.max(0,Math.min(d.duration_s,seconds));let index=0;
  while(index+1<d.keys.length&&d.keys[index+1].t<=time)index++;
  const a=d.keys[index],b=d.keys[index+1]??a,u=a===b?0:(time-a.t)/(b.t-a.t);
  const lerp=(x:number,y:number)=>x+(y-x)*u;
  const rootZ=lerp(a.root_z,b.root_z),forkTop=lerp(a.fork_top,b.fork_top),reach=lerp(a.reach,b.reach);
  const controlled=['controlled_insert','controlled_withdraw'].includes(a.phase);
  return {time,index,phase:a.phase,label:a.label,rootZ,forkTop,reach,attached:a.attached,
    HU_id:d.HU_id,HU_count:1,HU_world:[0,a.attached?forkTop:d.stock_support_y_m,a.attached?rootZ+1+reach:d.stock_centre_z_m],
    mode:controlled?'controlled_straight_handling':a.root_z!==b.root_z?'high_retracted_transit':'stopped_handling',
    signedWheelDistance:rootZ-d.keys[0].root_z,complete:time===d.duration_s};
}

/** Mutates only the existing native fixture nodes; a seek never creates a HU. */
export function createPickupFixture(root:THREE.Group,timeline:PickupTimeline){
  const find=(name:string)=>{const n=root.getObjectByName(name);if(!n)throw Error('В сборке отсутствует '+name);return n;};
  const vehicle=find('forklift_root'),carriage=find('joint__carriage'),reach=find('joint__reach');
  const cargo=find('pallet-load__HU'),stockParent=cargo.parent!;
  const bind=new Map<THREE.Object3D,{position:THREE.Vector3;quaternion:THREE.Quaternion;scale:THREE.Vector3}>();
  vehicle.traverse(n=>bind.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone(),scale:n.scale.clone()}));
  const cargoQuaternion=cargo.quaternion.clone(),cargoScale=cargo.scale.clone();const cargoUuid=cargo.uuid;
  let state=pickupAt(timeline,0);
  function apply(seconds:number){
    state=pickupAt(timeline,seconds);
    for(const [node,b] of bind){node.position.copy(b.position);node.quaternion.copy(b.quaternion);node.scale.copy(b.scale);}
    vehicle.position.set(0,0,state.rootZ);carriage.position.set(0,state.forkTop,.04);reach.position.set(0,0,.36+state.reach);
    for(const [side,sign] of [['L',-1],['R',1]] as const){
      find('joint__fork_'+side).position.set(sign*timeline.fork_halfspacing_m,0,0);
      find('joint__wheel_front_'+side).rotateX(state.signedWheelDistance/.3);
      find('joint__wheel_rear_'+side).rotateX(state.signedWheelDistance/.225);
    }
    const parent=state.attached?reach:stockParent;if(cargo.parent!==parent)parent.add(cargo);
    if(state.attached)cargo.position.fromArray(timeline.attached_HU_local_xyz_m);
    else cargo.position.set(0,timeline.stock_support_y_m,timeline.stock_centre_z_m);
    cargo.quaternion.copy(cargoQuaternion);cargo.scale.copy(cargoScale);root.updateMatrixWorld(true);
    return snapshot();
  }
  function snapshot(){
    return {...state,cargoUuid,actualHUWorld:cargo.getWorldPosition(new THREE.Vector3()).toArray(),cargoParent:cargo.parent?.name,
      source_kind:timeline.source_kind,engine_operation:false,exclusive_resources:state.complete?[]:timeline.exclusive_resources,reservation_scope:timeline.reservation_scope};
  }
  apply(0);
  return {apply,snapshot,timeline,root};
}
