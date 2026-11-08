import * as THREE from 'three';
import type {WorkerInstance} from '../workerRoles';

type Triple=[number,number,number];
type Pose=Record<string,Triple>;
export type ReceiverMode='receive'|'scan'|'idle'|'blocked';
export type ReceiverTimeline={schema_id:string;source_kind:'visual_fixture';engine_operation:false;duration_s:number;units:string;scope:string;body_root_m:Triple;body_yaw_rad:number;HU_ref:string;preparation:{duration_s:number;return_duration_s:number;abduction_z_rad:number;windows:Record<'upper'|'fold'|'swivel'|'hand',[number,number]>;waypoints?:{at:number;joints:Pose}[]};contact:{local_m:Triple;workcell_m:Triple;surface:string;tangent_twist_rad?:number};keys:{t:number;label:string;joints:Pose}[]};
const occupied=new WeakSet<THREE.Object3D>(),assigned=new WeakSet<WorkerInstance>();
const triple=(v:unknown):v is Triple=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite);
const smooth=(u:number)=>{u=THREE.MathUtils.clamp(u,0,1);return u*u*u*(10+u*(-15+6*u));};
function limits(name:string):[number,number][]{
  if(name==='joint__head')return [[-.25,.25],[-.6,.6],[-.12,.12]];
  if(/^joint__upper_arm_[LR]$/.test(name))return [[-2.2,.7],[-.55,.55],[-.7,.7]];
  if(/^joint__forearm_[LR]$/.test(name))return [[-2.2,.15],[-.12,.12],[-.12,.12]];
  if(/^joint__hand_[LR]$/.test(name))return [[-.6,.6],[-.65,.65],[-.4,.4]];
  if(/^joint__shoulder_lift_[LR]$/.test(name))return [[-.8,0],[0,0],[0,0]];
  if(/^joint__elbow_swivel_[LR]$/.test(name))return [[-Math.PI,Math.PI],[0,0],[0,0]];
  if(/^joint__palm_roll_[LR]$/.test(name))return [[0,0],[-Math.PI,Math.PI],[0,0]];
  throw Error('Неизвестный сустав приёмщика: '+name);
}

export function validateReceiverTimeline(value:unknown):ReceiverTimeline{
  const d=value as ReceiverTimeline;
  if(!d?.preparation||d.preparation.duration_s!==2.4||d.preparation.return_duration_s!==2.4||!Number.isFinite(d.preparation.abduction_z_rad)||d.preparation.abduction_z_rad<.15||d.preparation.abduction_z_rad>.7||!d.preparation.windows||Object.keys(d.preparation.windows).sort().join(',')!=='fold,hand,swivel,upper'||Object.values(d.preparation.windows).some(w=>!Array.isArray(w)||w.length!==2||!w.every(Number.isFinite)||w[0]<0||w[1]>1||w[1]-w[0]<.399999))throw Error('Некорректная подготовка руки приёмщика.');
  if(d.preparation.waypoints!==undefined){if(!Array.isArray(d.preparation.waypoints))throw Error('Некорректные промежуточные позы.');let previous=0;for(const p of d.preparation.waypoints){if(!Number.isFinite(p.at)||p.at<=previous||p.at>=1||!p.joints||typeof p.joints!=='object')throw Error('Некорректная промежуточная поза.');for(const [name,a]of Object.entries(p.joints)){const range=limits(name);if(!name.endsWith('_R')||!triple(a)||a.some((x,j)=>x<range[j][0]-1e-7||x>range[j][1]+1e-7))throw Error('Промежуточная поза вне пределов '+name);}previous=p.at;}}
  const times=[0,.7,1.1,1.5,2.1,2.7,3.7,4.3,4.9,5.5,6.1,6.7,7.1,7.5].map(t=>t<=1.1?2*t:t<=5.5?2*t+1.6:t<=6.1?12.6+(t-5.5)/.6*2.4:2*t+2.8);
  if(d.schema_id!=='qoima.visual-receiver.v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.units!=='m'||d.duration_s!==17.8||!triple(d.body_root_m)||d.body_root_m.join(',')!=='-1,0,-0.803'||d.body_yaw_rad!==0||d.HU_ref!=='v3:fixture:HU:RECEIVE01'||typeof d.scope!=='string'||!Array.isArray(d.keys)||d.keys.length!==times.length)throw Error('Некорректное описание приёмки.');
  const c=d.contact;
  if(!c||(c.tangent_twist_rad!==undefined&&(!Number.isFinite(c.tangent_twist_rad)||Math.abs(c.tangent_twist_rad)>Math.PI))||c.surface!=='screen_footer'||!triple(c.local_m)||!triple(c.workcell_m)||c.local_m.some((x,j)=>Math.abs(x-[.015,-.13,.03475][j])>2e-6)||c.workcell_m.some((x,j)=>Math.abs(x-[-.7,1.175,-.343][j])>2e-6))throw Error('Нет измеренного контакта с терминалом.');
  for(const [i,k]of d.keys.entries()){
    if(k.t!==times[i]||typeof k.label!=='string'||!k.joints||Array.isArray(k.joints)||typeof k.joints!=='object')throw Error('Некорректный этап приёмки.');
    for(const [name,a]of Object.entries(k.joints)){const range=limits(name);if(!triple(a)||a.some((x,j)=>x<range[j][0]-1e-7||x>range[j][1]+1e-7))throw Error('Превышены пределы '+name);}
  }
  return structuredClone(d);
}

/** Free approach stays within2cm of the unchanged terminal contact plane. */
export function receiverArmTarget(serviceTime:number):Triple|null{
  const mapped=(z:number):Triple=>[-.7,1.175,-z-.103];
  if(serviceTime>=2.1&&serviceTime<=4.3){const gap=serviceTime<2.7?.01*(1-smooth((serviceTime-2.1)/.6)):serviceTime<=3.7?0:.01*smooth((serviceTime-3.7)/.6);return mapped(.24+gap);}
  if((serviceTime>=1.5&&serviceTime<2.1)||(serviceTime>4.9&&serviceTime<=5.5)){const u=serviceTime<2.1?smooth((serviceTime-1.5)/.6):1-smooth((serviceTime-4.9)/.6);return mapped(.26-.01*u);}
  return null;
}

/** Absolute Cartesian approach to the rear-facing existing receiving terminal. */
export function solveReceiverArmPose(root:THREE.Object3D,cell:THREE.Object3D,seed:Record<string,Triple>,target:Triple,contact:Triple,side:'L'|'R'='R',tangentTwist=0):Record<string,Triple>{
  root.updateWorldMatrix(true,true);cell.updateWorldMatrix(true,false);
  const frame=root.getObjectByName('joint__torso')!,upper=root.getObjectByName('joint__upper_arm_'+side)!,fore=root.getObjectByName('joint__forearm_'+side)!,hand=root.getObjectByName('joint__hand_'+side)!;
  const shoulder=frame.worldToLocal(upper.getWorldPosition(new THREE.Vector3())),elbow=upper.worldToLocal(fore.getWorldPosition(new THREE.Vector3())),wrist=fore.worldToLocal(hand.getWorldPosition(new THREE.Vector3())),axis=elbow.clone().normalize();
  const desired=frame.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(cell.getWorldQuaternion(new THREE.Quaternion())).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),Math.PI)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),Math.PI/2)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),tangentTwist));
  const sUpper=seed['joint__upper_arm_'+side],sLift=seed['joint__shoulder_lift_'+side],sFore=seed['joint__forearm_'+side];
  const offset=new THREE.Vector3(...contact).applyQuaternion(desired),goal=frame.worldToLocal(cell.localToWorld(new THREE.Vector3(...target))),yaw=sUpper[1],twist=seed['joint__elbow_swivel_'+side][0],roll=seed['joint__palm_roll_'+side][1];
  const v=[sUpper[0]+sLift[0],sUpper[2],sFore[0]],q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();
  const point=(a:number[])=>{q1.setFromEuler(new THREE.Euler(a[0],yaw,a[1],'XYZ'));q2.setFromAxisAngle(axis,twist).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),a[2]));q12.copy(q1).multiply(q2);return shoulder.clone().add(elbow.clone().applyQuaternion(q1)).add(wrist.clone().applyQuaternion(q12)).add(offset);};
  for(let i=0;i<18;i++){
    const p=point(v),e=goal.clone().sub(p);if(e.length()<1e-10)break;
    const c=v.map((_,j)=>{const a=[...v];a[j]+=1e-5;return point(a).sub(p).multiplyScalar(1e5);}),jac=new THREE.Matrix3().set(c[0].x,c[1].x,c[2].x,c[0].y,c[1].y,c[2].y,c[0].z,c[1].z,c[2].z);
    if(Math.abs(jac.determinant())<1e-12)throw Error('Вырожденный подвод кисти приёмщика.');e.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=THREE.MathUtils.clamp(e.getComponent(j),-.25,.25);
  }
  if(point(v).distanceTo(goal)>1e-8)throw Error('Кисть не достигает панели.');
  const h=new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),roll).invert().multiply(q12.clone().invert()).multiply(desired),'XYZ'),lift=Math.min(0,Math.max(-.8,v[0]+2.2));
  const pose:Record<string,Triple>={['joint__shoulder_lift_'+side]:[lift,0,0],['joint__upper_arm_'+side]:[v[0]-lift,yaw,v[1]],['joint__forearm_'+side]:[v[2],0,0],['joint__elbow_swivel_'+side]:[twist,0,0],['joint__palm_roll_'+side]:[0,roll,0],['joint__hand_'+side]:[h.x,h.y,h.z]};
  for(const [name,a]of Object.entries(pose)){const r=limits(name);if(a.some((x,j)=>x<r[j][0]-1e-7||x>r[j][1]+1e-7))throw Error('Подвод вышел за пределы '+name);}
  return pose;
}

/** Consumes one supplied receiver and one existing floor-supported HU. */
export function createReceiverAction(workcell:THREE.Object3D,actor:WorkerInstance,input:ReceiverTimeline){
  const data=validateReceiverTimeline(input),worker=actor.root;
  if(actor.disposed||actor.role!=='receiver'||actor.actorId!=='R01'||assigned.has(actor)||occupied.has(workcell)||workcell.userData.asset_id!=='receiver-workcell-fixture'||workcell.userData.engine_operation!==false)throw Error('Приёмщик или пост недоступен.');
  workcell.updateWorldMatrix(true,true);worker.updateWorldMatrix(true,true);
  if([workcell,worker].some(n=>n.getWorldScale(new THREE.Vector3()).toArray().some(x=>Math.abs(x-1)>1e-7))||Math.abs(workcell.getWorldPosition(new THREE.Vector3()).y)>1e-6||new THREE.Vector3(0,1,0).transformDirection(workcell.matrixWorld).distanceTo(new THREE.Vector3(0,1,0))>1e-6)throw Error('Нужен горизонтальный пост масштаба1:1.');
  const pallet=workcell.getObjectByName('receiver_existing_pallet'),lens=workcell.getObjectByName('anchor_receiver_scan_lens'),label=workcell.getObjectByName('anchor_receiver_scan_target');
  if(!pallet||pallet.userData.fixture_HU_ref!==data.HU_ref||!lens||!label)throw Error('Нет исходной паллеты или интерфейса сканера.');
  const nodes=new Map<string,THREE.Object3D>(),rest=new Map<THREE.Object3D,{position:THREE.Vector3;quaternion:THREE.Quaternion;angles:Triple}>();
  worker.traverse(n=>{if(n.name.startsWith('joint__')){nodes.set(n.name,n);const e=new THREE.Euler().setFromQuaternion(n.quaternion,'XYZ');rest.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone(),angles:n.userData.custom_axis_runtime?[0,0,0]:[e.x,e.y,e.z]});}});
  for(const k of data.keys)for(const name of Object.keys(k.joints))if(!nodes.has(name))throw Error('Нет сустава '+name);
  for(const name of ['joint__hand_R','joint__elbow_swivel_R','joint__head','joint__upper_arm_L'])if(!nodes.has(name))throw Error('Нужен ручной rig приёмщика.');
  const saved={parent:worker.parent,position:worker.position.clone(),quaternion:worker.quaternion.clone()};
  const fields:[THREE.Object3D,string][]=[[worker,'assignment'],[pallet,'visual_received'],[pallet,'visual_scanned']];
  const metadata=fields.map(([node,key])=>({node,key,present:Object.hasOwn(node.userData,key),value:structuredClone(node.userData[key])}));
  // A nonphysical visual cue follows the separately proven actual scan ray.
  const inverse=workcell.matrixWorld.clone().invert(),points=[lens,label].map(n=>n.getWorldPosition(new THREE.Vector3()).applyMatrix4(inverse));
  const beam=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:'#e9aa4c',transparent:true,opacity:.75}));
  beam.name='receiver_visual_scan_cue';beam.userData={role:'nonphysical_visual_scan_cue',engine_operation:false};
  let mode:ReceiverMode='receive',time=0,released=false,labelText='Ожидание паллеты';
  const duration=()=>mode==='scan'?2.5:data.duration_s;
  function assertLive(){if(released||actor.disposed||actor.role!=='receiver'||worker.parent!==workcell)throw Error('Действие приёмщика освобождено.');}
  function snapshot(){
    assertLive();workcell.updateWorldMatrix(true,true);const hand=nodes.get('joint__hand_R')!,point=new THREE.Vector3(...data.contact.local_m).applyMatrix4(hand.matrixWorld).applyMatrix4(workcell.matrixWorld.clone().invert());
    return {time,label:labelText,mode,complete:(mode==='receive'||mode==='scan')&&time===duration(),actorId:actor.actorId,role:actor.role,actor_uuid:worker.uuid,HU_uuid:pallet!.uuid,HU_ref:data.HU_ref,warehouse_headcount_delta:0,source_kind:'visual_fixture' as const,engine_operation:false as const,inventory_mutated:false,scanning:beam.visible,scan_complete:(mode==='receive'&&time>=2.2)||(mode==='scan'&&time>=1.8),received:mode==='receive'&&time>=data.keys[6].t,
      contact:{active:mode==='receive'&&time>=data.keys[5].t&&time<=data.keys[6].t,surface:data.contact.surface,point_workcell_m:point.toArray(),error_m:point.distanceTo(new THREE.Vector3(...data.contact.workcell_m))},palms_worker_local:(['L','R'] as const).map(side=>({side,direction:new THREE.Vector3(0,0,1).transformDirection(nodes.get('joint__hand_'+side)!.matrixWorld).transformDirection(worker.matrixWorld.clone().invert()).toArray()}))};
  }
  function apply(seconds:number){
    assertLive();if(!Number.isFinite(seconds))throw Error('Время должно быть конечным числом.');time=mode==='idle'||mode==='blocked'?0:THREE.MathUtils.clamp(seconds,0,duration());
    worker.position.fromArray(data.body_root_m);worker.rotation.set(0,data.body_yaw_rad,0);
    for(const [n,b]of rest){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}
    let pose:Pose={joint__upper_arm_L:[0,0,-.15],joint__upper_arm_R:[0,0,.15]};
    if(mode==='receive'){
      let i=0;while(i+1<data.keys.length&&data.keys[i+1].t<=time)i++;
      const a=data.keys[i],b=data.keys[Math.min(i+1,data.keys.length-1)],u=b.t===a.t?0:smooth((time-a.t)/(b.t-a.t));labelText=a.label;
      for(const name of new Set([...Object.keys(a.joints),...Object.keys(b.joints)])){const base=rest.get(nodes.get(name)!)!.angles,from=a.joints[name]??base,to=b.joints[name]??base;pose[name]=from.map((x,j)=>x+(to[j]-x)*u) as Triple;}
      // Natural elbow branch; free approach is shorter than the inherited P04 path.
      const legacy=[0,.7,1.1,1.5,2.1,2.7,3.7,4.3,4.9,5.5,6.1,6.7,7.1,7.5],raw=b.t===a.t?0:(time-a.t)/(b.t-a.t),serviceTime=legacy[i]+(legacy[Math.min(i+1,legacy.length-1)]-legacy[i])*raw;
      const forward=time>=data.keys[2].t&&time<=data.keys[3].t,backward=time>=data.keys[9].t&&time<=data.keys[10].t;
      if(forward||backward){
        const u=forward?(time-data.keys[2].t)/data.preparation.duration_s:1-(time-data.keys[9].t)/data.preparation.return_duration_s;
        if(data.preparation.waypoints?.length){
          const stages=[{at:0,joints:data.keys[2].joints},...data.preparation.waypoints,{at:1,joints:data.keys[3].joints}];let stage=0;while(stage+1<stages.length-1&&stages[stage+1].at<=u)stage++;
          const a=stages[stage],b=stages[stage+1],v=smooth((u-a.at)/(b.at-a.at));
          for(const name of Object.keys(data.keys[3].joints).filter(n=>n.endsWith('_R'))){const base=rest.get(nodes.get(name)!)!.angles,from=a.joints[name]??base,to=b.joints[name]??base;pose[name]=from.map((x,j)=>x+(to[j]-x)*v) as Triple;}
        }else{for(const name of Object.keys(data.keys[3].joints).filter(n=>n.endsWith('_R'))){const family=name.startsWith('joint__elbow_swivel_')?'swivel':name.startsWith('joint__forearm_')?'fold':name.startsWith('joint__hand_')||name.startsWith('joint__palm_roll_')?'hand':'upper',[start,end]=data.preparation.windows[family],v=smooth((u-start)/(end-start)),from=data.keys[2].joints[name]??rest.get(nodes.get(name)!)!.angles,to=data.keys[3].joints[name];pose[name]=from.map((x,j)=>x+(to[j]-x)*v) as Triple;}const lift=u<.2?smooth(u/.2):u>.8?1-smooth((u-.8)/.2):1;pose.joint__upper_arm_R[2]+=(data.preparation.abduction_z_rad-pose.joint__upper_arm_R[2])*lift;}
      }
      const target=receiverArmTarget(serviceTime);if(target)Object.assign(pose,solveReceiverArmPose(worker,workcell,data.keys[5].joints,target,data.contact.local_m,'R',data.contact.tangent_twist_rad??0));
      if(serviceTime<=1.1)pose.joint__head=[.1,.15*smooth(serviceTime/.7),0];
      else if(serviceTime<1.5){const u=smooth((serviceTime-1.1)/.4),target=pose.joint__head??rest.get(nodes.get('joint__head')!)!.angles;pose.joint__head=target.map((x,j)=>[.1,.15,0][j]+(x-[.1,.15,0][j])*u) as Triple;}
    }else if(mode==='scan'){labelText=time<.5?'Проверка входящей паллеты':time<1.8?'Сканирование этикетки':'Этикетка проверена';pose.joint__head=[.1,.15*smooth(time/.5),0];}
    else if(mode==='blocked'){labelText='Пост занят · приёмка не начата';pose.joint__head=[.1,.3,0];}
    else labelText='Ожидание задания';
    for(const [name,a]of Object.entries(pose)){const n=nodes.get(name)!;if(n.userData.custom_axis_runtime)n.quaternion.setFromAxisAngle(new THREE.Vector3(...n.userData.custom_axis_runtime).normalize(),a[0]);else n.rotation.set(...a,'XYZ');}
    beam.visible=mode==='receive'?time>=.4&&time<2.2:mode==='scan'&&time>=.5&&time<1.8;
    pallet!.userData.visual_received=mode==='receive'&&time>=data.keys[6].t;pallet!.userData.visual_scanned=(mode==='receive'&&time>=2.2)||(mode==='scan'&&time>=1.8);worker.userData.assignment='receiver_'+mode;
    return snapshot();
  }
  function setMode(next:ReceiverMode){assertLive();if(!['receive','scan','idle','blocked'].includes(next))throw Error('Неизвестное состояние приёмщика.');mode=next;return apply(0);}
  function dispose(){if(released)return;released=true;assigned.delete(actor);occupied.delete(workcell);beam.removeFromParent();beam.geometry.dispose();beam.material.dispose();if(!actor.disposed){worker.removeFromParent();if(saved.parent)saved.parent.add(worker);worker.position.copy(saved.position);worker.quaternion.copy(saved.quaternion);for(const [n,b]of rest){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}}for(const m of metadata){if(actor.disposed&&m.node===worker)continue;if(m.present)m.node.userData[m.key]=m.value;else delete m.node.userData[m.key];}}
  assigned.add(actor);occupied.add(workcell);workcell.add(worker,beam);try{apply(0);}catch(e){dispose();throw e;}
  return {apply,snapshot,setMode,dispose,get timeline(){return {...data,duration_s:duration()};},actor,workcell};
}
