import * as THREE from 'three';
import type {WorkerInstance} from '../workerRoles';

type Triple=[number,number,number];
export type PackerMode='pack'|'idle'|'blocked';
export type PackerTimeline={schema_id:string;source_kind:'visual_fixture';engine_operation:false;units:string;duration_s:number;scope:string;body_root_m:Triple;body_yaw_rad:number;package_id:string;contents_HU_ref:string;contacts:Record<'L'|'R',{local_m:Triple;workcell_m:Triple;surface:string}>;keys:{t:number;label:string;joints:Record<string,Triple>}[]};
const occupied=new WeakSet<THREE.Object3D>(),assigned=new WeakSet<WorkerInstance>();
const triple=(v:unknown):v is Triple=>Array.isArray(v)&&v.length===3&&v.every(x=>typeof x==='number'&&Number.isFinite(x));
function limits(name:string):[number,number][]{
  if(name==='joint__head')return [[-.25,.25],[-.6,.6],[-.12,.12]];
  if(/^joint__upper_arm_[LR]$/.test(name))return [[-2.2,.7],[-.55,.55],[-.7,.7]];
  if(/^joint__forearm_[LR]$/.test(name))return [[-2.2,.15],[-.12,.12],[-.12,.12]];
  if(/^joint__hand_[LR]$/.test(name))return [[-.6,.6],[-.65,.65],[-.4,.4]];
  if(/^joint__shoulder_lift_[LR]$/.test(name))return [[-.8,0],[0,0],[0,0]];
  if(/^joint__elbow_swivel_[LR]$/.test(name))return [[-Math.PI,Math.PI],[0,0],[0,0]];
  if(/^joint__palm_roll_[LR]$/.test(name))return [[0,0],[-Math.PI,Math.PI],[0,0]];
  throw Error('Неизвестный сустав упаковщика: '+name);
}
export function validatePackerTimeline(value:unknown):PackerTimeline{
  const d=value as PackerTimeline;
  const times=[0,.7,1.1,1.5,2.1,2.7,3.7,4.3,4.9,5.5,6.1,6.7,7.1,7.5];
  if(!d||d.schema_id!=='qoima.visual-packer-seam-end.v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.units!=='m'||d.duration_s!==7.5||!triple(d.body_root_m)||d.body_root_m.join(',')!=='0.3,0,0.7'||d.body_yaw_rad!==Math.PI||typeof d.scope!=='string'||!Array.isArray(d.keys)||d.keys.length!==times.length)throw Error('Некорректное описание упаковки.');
  for(const [i,k] of d.keys.entries()){
    if(k.t!==times[i]||typeof k.label!=='string'||!k.joints||typeof k.joints!=='object'||Array.isArray(k.joints))throw Error('Некорректный этап упаковки.');
    for(const [name,a] of Object.entries(k.joints)){const range=limits(name);if(!triple(a)||a.some((x,j)=>x<range[j][0]-1e-7||x>range[j][1]+1e-7))throw Error('Превышены пределы сустава '+name);}
  }
  for(const side of ['L','R'] as const){
    const c=d.contacts?.[side],target=side==='L'?[.65,.89,.45]:[0,1.17,.24],local=side==='L'?[-.015,-.13,.03975]:[.015,-.13,.03975];
    if(!c||!triple(c.local_m)||!triple(c.workcell_m)||typeof c.surface!=='string'||c.workcell_m.some((v,j)=>Math.abs(v-target[j])>1e-7)||c.local_m.some((v,j)=>Math.abs(v-local[j])>2e-6))throw Error('Нет измеренной точки контакта упаковщика.');
  }
  return structuredClone(d);
}
const smooth=(u:number)=>u*u*u*(10+u*(-15+6*u));

/** Deterministic short Cartesian approach from an admitted arm solution. */
export function solvePackerArmPose(root:THREE.Object3D,cell:THREE.Object3D,seed:Record<string,Triple>,target:Triple,contact:Triple,side:'L'|'R'='R'):Record<string,Triple>{
  root.updateWorldMatrix(true,true);cell.updateWorldMatrix(true,false);
  const frame=root.getObjectByName('joint__torso')!,upper=root.getObjectByName('joint__upper_arm_'+side)!,fore=root.getObjectByName('joint__forearm_'+side)!,hand=root.getObjectByName('joint__hand_'+side)!;
  const shoulder=frame.worldToLocal(upper.getWorldPosition(new THREE.Vector3())),elbow=upper.worldToLocal(fore.getWorldPosition(new THREE.Vector3())),wrist=fore.worldToLocal(hand.getWorldPosition(new THREE.Vector3())),axis=elbow.clone().normalize();
  const desired=frame.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(cell.getWorldQuaternion(new THREE.Quaternion())).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI/2,0,0,'XYZ')));
  const sUpper=seed['joint__upper_arm_'+side],sLift=seed['joint__shoulder_lift_'+side],sFore=seed['joint__forearm_'+side];
  const offset=new THREE.Vector3(...contact).applyQuaternion(desired),goal=frame.worldToLocal(cell.localToWorld(new THREE.Vector3(...target))),yaw=sUpper[1],twist=seed['joint__elbow_swivel_'+side][0],roll=seed['joint__palm_roll_'+side][1];
  const v=[sUpper[0]+sLift[0],sUpper[2],sFore[0]],q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();
  const point=(a:number[])=>{q1.setFromEuler(new THREE.Euler(a[0],yaw,a[1],'XYZ'));q2.setFromAxisAngle(axis,twist).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),a[2]));q12.copy(q1).multiply(q2);return shoulder.clone().add(elbow.clone().applyQuaternion(q1)).add(wrist.clone().applyQuaternion(q12)).add(offset);};
  for(let i=0;i<18;i++){
    const p=point(v),e=goal.clone().sub(p);if(e.length()<1e-10)break;
    const c=v.map((_,j)=>{const a=[...v];a[j]+=1e-5;return point(a).sub(p).multiplyScalar(1e5);}),jac=new THREE.Matrix3().set(c[0].x,c[1].x,c[2].x,c[0].y,c[1].y,c[2].y,c[0].z,c[1].z,c[2].z);
    if(Math.abs(jac.determinant())<1e-12)throw Error('Вырожденный подвод кисти упаковщика.');e.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=THREE.MathUtils.clamp(e.getComponent(j),-.25,.25);
  }
  if(point(v).distanceTo(goal)>1e-8)throw Error('Кисть не достигает края ленты.');
  const h=new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),roll).invert().multiply(q12.clone().invert()).multiply(desired),'XYZ'),lift=Math.min(0,Math.max(-.8,v[0]+2.2));
  const pose:Record<string,Triple>={['joint__shoulder_lift_'+side]:[lift,0,0],['joint__upper_arm_'+side]:[v[0]-lift,yaw,v[1]],['joint__forearm_'+side]:[v[2],0,0],['joint__elbow_swivel_'+side]:[twist,0,0],['joint__palm_roll_'+side]:[0,roll,0],['joint__hand_'+side]:[h.x,h.y,h.z]};
  for(const [name,a]of Object.entries(pose)){const r=limits(name);if(a.some((x,j)=>x<r[j][0]-1e-7||x>r[j][1]+1e-7))throw Error('Подвод вышел за пределы '+name);}
  return pose;
}

/** Consumes one existing worker and parcel; never creates stock or another actor. */
export function createPackerAction(workcell:THREE.Object3D,actor:WorkerInstance,input:PackerTimeline){
  const timeline=validatePackerTimeline(input);
  if(actor.disposed||actor.role!=='packer'||assigned.has(actor)||occupied.has(workcell))throw Error('Упаковщик или пост уже занят.');
  workcell.updateWorldMatrix(true,true);actor.root.updateWorldMatrix(true,true);
  if([workcell,actor.root].some(n=>n.getWorldScale(new THREE.Vector3()).toArray().some(v=>Math.abs(v-1)>1e-7))||Math.abs(workcell.getWorldPosition(new THREE.Vector3()).y)>1e-6||new THREE.Vector3(0,1,0).transformDirection(workcell.matrixWorld).distanceTo(new THREE.Vector3(0,1,0))>1e-6)throw Error('Нужен пост масштаба 1:1 на полу Y0.');
  const parcel=workcell.getObjectByName('packer_existing_parcel');if(!parcel)throw Error('На посту нет посылки.');
  if(parcel.userData.fixture_package_id!==timeline.package_id||parcel.userData.fixture_contents_HU_ref!==timeline.contents_HU_ref)throw Error('Идентичность посылки не совпадает.');
  const nodes=new Map<string,THREE.Object3D>(),rest=new Map<THREE.Object3D,{position:THREE.Vector3;quaternion:THREE.Quaternion;angles:Triple}>();
  actor.root.traverse(n=>{if(n.name.startsWith('joint__')){nodes.set(n.name,n);const e=new THREE.Euler().setFromQuaternion(n.quaternion,'XYZ');rest.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone(),angles:n.userData.custom_axis_runtime?[0,0,0]:[e.x,e.y,e.z]});}});
  for(const k of timeline.keys)for(const name of Object.keys(k.joints))if(!nodes.has(name))throw Error('Нет сустава '+name);
  for(const side of ['L','R'])if(!nodes.has('joint__hand_'+side)||!nodes.has('joint__elbow_swivel_'+side))throw Error('Нужен ручной rig упаковщика.');
  const saved={parent:actor.root.parent,position:actor.root.position.clone(),quaternion:actor.root.quaternion.clone(),assignment:actor.root.userData.assignment};
  let mode:PackerMode='pack',time=0,released=false,label='Ожидание';
  function assertLive(){if(released||actor.disposed||actor.role!=='packer'||actor.root.parent!==workcell)throw Error('Действие упаковщика освобождено.');}
  function snapshot(){
    assertLive();workcell.updateWorldMatrix(true,true);const inverse=workcell.matrixWorld.clone().invert();
    return {time,label,mode,complete:mode==='pack'&&time===timeline.duration_s,actorId:actor.actorId,actor_uuid:actor.root.uuid,package_uuid:parcel!.uuid,package_id:timeline.package_id,contents_HU_ref:timeline.contents_HU_ref,warehouse_headcount_delta:0,source_kind:'visual_fixture' as const,engine_operation:false as const,
      seam_end_checked:mode==='pack'&&time>=3.7,final_inspection_complete:mode==='pack'&&time>=7.1,inventory_mutated:false,
      contacts:(['L','R'] as const).map(side=>{const c=timeline.contacts[side],node=nodes.get('joint__hand_'+side)!,point=new THREE.Vector3(...c.local_m).applyMatrix4(node.matrixWorld).applyMatrix4(inverse),palm=new THREE.Vector3(0,0,1).transformDirection(node.matrixWorld).transformDirection(inverse),active=mode==='pack'&&(side==='L'?time>=1.1&&time<=6.1:time>=2.7&&time<=3.7);return {side,active,surface:c.surface,point_workcell_m:point.toArray(),target_workcell_m:c.workcell_m,palm_direction_workcell:palm.toArray(),error_m:point.distanceTo(new THREE.Vector3(...c.workcell_m))};})};
  }
  function apply(seconds:number){
    assertLive();if(!Number.isFinite(seconds))throw Error('Время должно быть конечным числом.');
    time=mode==='pack'?THREE.MathUtils.clamp(seconds,0,timeline.duration_s):0;
    actor.root.position.fromArray(timeline.body_root_m);actor.root.rotation.set(0,timeline.body_yaw_rad,0);
    for(const [n,b] of rest){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}
    if(mode==='pack'){
      let i=0;while(i+1<timeline.keys.length&&timeline.keys[i+1].t<=time)i++;
      const a=timeline.keys[i],b=timeline.keys[Math.min(i+1,timeline.keys.length-1)],u=b.t===a.t?0:smooth((time-a.t)/(b.t-a.t));label=a.label;
      const pose:Record<string,Triple>={};
      for(const name of new Set([...Object.keys(a.joints),...Object.keys(b.joints)])){
        const n=nodes.get(name)!,base=rest.get(n)!.angles,from=a.joints[name]??base,to=b.joints[name]??base,v=from.map((x,j)=>x+(to[j]-x)*u) as Triple;
        pose[name]=v;
      }
      if(time>=2.1&&time<=4.3){
        const clearance=time<2.7?.04*(1-smooth((time-2.1)/.6)):time<=3.7?0:.04*smooth((time-3.7)/.6);
        Object.assign(pose,solvePackerArmPose(actor.root,workcell,timeline.keys[5].joints,[0,1.17,.24+clearance],timeline.contacts.R.local_m));
      }
      if((time>=1.5&&time<2.1)||(time>4.9&&time<=5.5)){
        const u=time<2.1?smooth((time-1.5)/.6):1-smooth((time-4.9)/.6);
        Object.assign(pose,solvePackerArmPose(actor.root,workcell,timeline.keys[5].joints,[-.08*(1-u),1.17,.38-.10*u],timeline.contacts.R.local_m));
      }
      if((time>=.7&&time<=1.1)||(time>=6.1&&time<=6.7)){
        const gap=time<=1.1?.07*(1-smooth((time-.7)/.4)):.07*smooth((time-6.1)/.6);
        Object.assign(pose,solvePackerArmPose(actor.root,workcell,timeline.keys[2].joints,[.65,.89,.45+gap],timeline.contacts.L.local_m,'L'));
      }
      for(const [name,v]of Object.entries(pose)){const n=nodes.get(name)!;if(n.userData.custom_axis_runtime)n.quaternion.setFromAxisAngle(new THREE.Vector3(...n.userData.custom_axis_runtime).normalize(),v[0]);else n.rotation.set(...v,'XYZ');}
    }else{
      for(const [name,v]of Object.entries(timeline.keys[0].joints))nodes.get(name)!.rotation.set(...v,'XYZ');
      if(mode==='blocked'){label='Пост занят · операция не начата';nodes.get('joint__head')!.rotation.set(.1,.35,0);}else label='Ожидание задания';
    }
    actor.root.userData.assignment=mode==='pack'?'packing_seam_end':mode==='blocked'?'packing_blocked':'packing_idle';return snapshot();
  }
  function setMode(next:PackerMode){assertLive();if(!['pack','idle','blocked'].includes(next))throw Error('Неизвестное состояние упаковщика.');mode=next;return apply(0);}
  function dispose(){if(released)return;released=true;assigned.delete(actor);occupied.delete(workcell);if(actor.disposed)return;actor.root.removeFromParent();if(saved.parent)saved.parent.add(actor.root);actor.root.position.copy(saved.position);actor.root.quaternion.copy(saved.quaternion);for(const [n,b]of rest){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}if(saved.assignment===undefined)delete actor.root.userData.assignment;else actor.root.userData.assignment=saved.assignment;}
  assigned.add(actor);occupied.add(workcell);workcell.add(actor.root);
  try{apply(0);}catch(e){dispose();throw e;}
  return {apply,snapshot,setMode,dispose,timeline,actor,workcell};
}
