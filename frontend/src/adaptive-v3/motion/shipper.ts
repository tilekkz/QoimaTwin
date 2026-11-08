import * as THREE from 'three';
import type {WorkerInstance} from '../workerRoles';
type Triple=[number,number,number];type Pose=Record<string,Triple>;
export type ShipperMode='place'|'scan'|'idle'|'blocked';
export type ShipperTimeline={schema_id:string;source_kind:'visual_fixture';engine_operation:false;units:string;duration_s:number;scan_duration_s:number;scope:string;body_root_m:Triple;body_yaw_rad:number;package_id:string;contents_HU_ref:string;pallet_HU_ref:string;contact:{local_m:Triple;workcell_m:Triple;surface:string};placement:{start_s:number;duration_s:number;distance_m:number;pelvis_drop_m:number;swing_lift_m:number;cycles:number;return_start_s:number;return_duration_s:number};keys:{t:number;label:string;joints:Pose}[]};
const occupied=new WeakSet<THREE.Object3D>(),assigned=new WeakSet<WorkerInstance>();
const triple=(v:unknown):v is Triple=>Array.isArray(v)&&v.length===3&&v.every(x=>typeof x==='number'&&Number.isFinite(x));
const smooth=(x:number)=>{const u=THREE.MathUtils.clamp(x,0,1);return u*u*u*(10+u*(-15+6*u));};
const wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
function limits(name:string):[number,number][]{
  if(name==='joint__head')return [[-.25,.25],[-.6,.6],[-.12,.12]];
  if(/^joint__upper_arm_[LR]$/.test(name))return [[-2.2,.7],[-.55,.55],[-.7,.7]];
  if(/^joint__forearm_[LR]$/.test(name))return [[-2.2,.15],[-.12,.12],[-.12,.12]];
  if(/^joint__hand_[LR]$/.test(name))return [[-.6,.6],[-.65,.65],[-.4,.4]];
  if(/^joint__shoulder_lift_[LR]$/.test(name))return [[-.8,0],[0,0],[0,0]];
  if(/^joint__elbow_swivel_[LR]$/.test(name))return [[-Math.PI,Math.PI],[0,0],[0,0]];
  if(/^joint__palm_roll_[LR]$/.test(name))return [[0,0],[-Math.PI,Math.PI],[0,0]];
  throw Error('Неизвестный сустав отгрузчика: '+name);
}
export function solveShipperArmPose(root:THREE.Object3D,cell:THREE.Object3D,seed:Record<string,Triple>,target:Triple,contact:Triple,side:'L'|'R'='R'):Record<string,Triple>{
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
    if(Math.abs(jac.determinant())<1e-12)throw Error('Вырожденный подвод кисти отгрузчика.');e.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=THREE.MathUtils.clamp(e.getComponent(j),-.25,.25);
  }
  if(point(v).distanceTo(goal)>1e-8)throw Error('Кисть не достигает края ленты.');
  const h=new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),roll).invert().multiply(q12.clone().invert()).multiply(desired),'XYZ'),lift=Math.min(0,Math.max(-.8,v[0]+2.2));
  const pose:Record<string,Triple>={['joint__shoulder_lift_'+side]:[lift,0,0],['joint__upper_arm_'+side]:[v[0]-lift,yaw,v[1]],['joint__forearm_'+side]:[v[2],0,0],['joint__elbow_swivel_'+side]:[twist,0,0],['joint__palm_roll_'+side]:[0,roll,0],['joint__hand_'+side]:[h.x,h.y,h.z]};
  for(const [name,a]of Object.entries(pose)){const r=limits(name);if(a.some((x,j)=>x<r[j][0]-1e-7||x>r[j][1]+1e-7))throw Error('Подвод вышел за пределы '+name);}
  return pose;
}

export function validateShipperTimeline(value:unknown):ShipperTimeline{
  const d=value as ShipperTimeline,times=[0,1.4,2.2,3,4.2,5.4,13.4,14.6,15.8,17,24.2,25.4,26.2,27];
  if(!d||d.schema_id!=='qoima.visual-shipper.v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.units!=='m'||d.duration_s!==27||d.scan_duration_s!==2.5||!triple(d.body_root_m)||d.body_root_m.join(',')!=='-0.39,0,1.85'||d.body_yaw_rad!==Math.PI||typeof d.scope!=='string'||d.package_id!=='v3:fixture:package:SMALL001'||d.contents_HU_ref!=='v3:fixture:HU:SMALL001'||d.pallet_HU_ref!=='v3:fixture:HU:OUTBOUND01'||!Array.isArray(d.keys)||d.keys.length!==14)throw Error('Некорректное описание отгрузки.');
  for(const[i,k]of d.keys.entries()){
    if(Math.abs(k.t-times[i])>1e-10||typeof k.label!=='string'||!k.joints||typeof k.joints!=='object'||Array.isArray(k.joints))throw Error('Некорректный этап отгрузки.');
    for(const[name,a]of Object.entries(k.joints)){const r=limits(name);if(!triple(a)||a.some((x,j)=>x<r[j][0]-1e-7||x>r[j][1]+1e-7))throw Error('Превышены пределы '+name);}
  }
  const c=d.contact;if(!c||!triple(c.local_m)||!triple(c.workcell_m)||c.surface!=='rear_paper_and_tape'||c.local_m.some((x,j)=>Math.abs(x-[.015,-.13,.03975][j])>2e-6)||c.workcell_m.some((x,j)=>Math.abs(x-[-.69,1.17,1.39][j])>1e-10))throw Error('Нет измеренной поверхности укладки.');
  for(const[k,v]of Object.entries({start_s:5.4,duration_s:6,distance_m:.16,pelvis_drop_m:.008,swing_lift_m:.012,cycles:2,return_start_s:17,return_duration_s:6}))if(d.placement?.[k as keyof ShipperTimeline['placement']]!==v)throw Error('Некорректный путь укладки.');
  return structuredClone(d);
}

/** Two short step-together cycles: fixed stance soles, lowered pelvis, no teleport. */
export function shipperPlacementAt(seconds:number){
  const t=THREE.MathUtils.clamp(seconds,0,6),feet={L:{travel:0,lift:0,stance:true},R:{travel:0,lift:0,stance:true}};
  const phase=THREE.MathUtils.clamp((t-.5)/1.25,0,4),completed=Math.min(4,Math.floor(phase));
  for(let i=0;i<completed;i++)feet[i%2===0?'L':'R'].travel=(Math.floor(i/2)+1)*.08;
  if(completed<4&&phase>0){const u=phase-completed,side=completed%2===0?'L':'R';feet[side].travel+=(Math.floor(completed/2)+1)*.08*smooth(u)-feet[side].travel*smooth(u);feet[side].lift=.012*Math.sin(Math.PI*u)**2;feet[side].stance=u===0;}
  return {distance:(feet.L.travel+feet.R.travel)/2,drop:.008*smooth(Math.min(t/.5,(6-t)/.5,1)),feet};
}

export function createShipperAction(workcell:THREE.Object3D,actor:WorkerInstance,input:ShipperTimeline){
  const data=validateShipperTimeline(input),worker=actor.root;
  if(actor.disposed||actor.role!=='shipper'||assigned.has(actor)||occupied.has(workcell))throw Error('Отгрузчик или пост уже занят.');
  workcell.updateWorldMatrix(true,true);worker.updateWorldMatrix(true,true);
  if([workcell,worker].some(n=>n.getWorldScale(new THREE.Vector3()).toArray().some(x=>Math.abs(x-1)>1e-7))||Math.abs(workcell.getWorldPosition(new THREE.Vector3()).y)>1e-6||new THREE.Vector3(0,1,0).transformDirection(workcell.matrixWorld).distanceTo(new THREE.Vector3(0,1,0))>1e-6)throw Error('Нужен горизонтальный пост масштаба1:1.');
  const parcel=workcell.getObjectByName('shipper_existing_parcel'),pallet=workcell.getObjectByName('shipper_existing_pallet'),lens=workcell.getObjectByName('anchor_shipper_scan_lens'),target=workcell.getObjectByName('anchor_shipper_scan_target');
  if(!parcel||parcel.userData.fixture_package_id!==data.package_id||parcel.userData.fixture_contents_HU_ref!==data.contents_HU_ref||!pallet||pallet.userData.fixture_HU_ref!==data.pallet_HU_ref||!lens||!target)throw Error('Нет исходного груза или сканера.');
  const nodes=new Map<string,THREE.Object3D>(),rest=new Map<THREE.Object3D,{position:THREE.Vector3;quaternion:THREE.Quaternion;angles:Triple}>();
  worker.traverse(n=>{if(n.name.startsWith('joint__')){nodes.set(n.name,n);const e=new THREE.Euler().setFromQuaternion(n.quaternion,'XYZ');rest.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone(),angles:n.userData.custom_axis_runtime?[0,0,0]:[e.x,e.y,e.z]});}});
  for(const k of data.keys)for(const name of Object.keys(k.joints))if(!nodes.has(name))throw Error('Нет сустава '+name);
  for(const name of ['joint__hand_R','joint__elbow_swivel_R','joint__thigh_L','joint__thigh_R'])if(!nodes.has(name))throw Error('Нужен ручной rig отгрузчика.');
  const saved={parent:worker.parent,position:worker.position.clone(),quaternion:worker.quaternion.clone(),parcelPosition:parcel.position.clone(),parcelQuaternion:parcel.quaternion.clone()};
  const metadata=([[worker,'assignment'],[parcel,'visual_placed'],[parcel,'visual_scanned']] as [THREE.Object3D,string][]).map(([node,key])=>({node,key,present:Object.hasOwn(node.userData,key),value:structuredClone(node.userData[key])}));
  worker.updateWorldMatrix(true,true);
  const legs=(['L','R'] as const).map(side=>{const thigh=nodes.get('joint__thigh_'+side)!,shin=nodes.get('joint__shin_'+side)!,foot=nodes.get('joint__foot_'+side)!,anchor=worker.getObjectByName('anchor_foot_floor_'+side)!;const hip=worker.worldToLocal(thigh.getWorldPosition(new THREE.Vector3())),floor=worker.worldToLocal(anchor.getWorldPosition(new THREE.Vector3())),a=shin.position.clone(),b=foot.position.clone();return {side,thigh,shin,foot,anchor,hip,floor,a,b,l1:Math.hypot(a.y,a.z),l2:Math.hypot(b.y,b.z)};});
  const inverse=workcell.matrixWorld.clone().invert(),beam=new THREE.Line(new THREE.BufferGeometry().setFromPoints([lens,target].map(n=>n.getWorldPosition(new THREE.Vector3()).applyMatrix4(inverse))),new THREE.LineBasicMaterial({color:'#e9aa4c',transparent:true,opacity:.75}));beam.name='shipper_visual_scan_cue';beam.userData={role:'nonphysical_visual_scan_cue',engine_operation:false};
  let mode:ShipperMode='place',time=0,released=false,label='Ожидание посылки',gait=shipperPlacementAt(0),parcelDistance=0;
  const duration=()=>mode==='scan'?2.5:data.duration_s;
  function assertLive(){if(released||actor.disposed||actor.role!=='shipper'||worker.parent!==workcell)throw Error('Действие отгрузчика освобождено.');}
  function snapshot(){
    assertLive();workcell.updateWorldMatrix(true,true);const inverse=workcell.matrixWorld.clone().invert(),point=new THREE.Vector3(...data.contact.local_m).applyMatrix4(nodes.get('joint__hand_R')!.matrixWorld).applyMatrix4(inverse),goal=new THREE.Vector3(...data.contact.workcell_m).add(new THREE.Vector3(0,-gait.drop,-gait.distance));
    return {time,label,mode,complete:(mode==='place'||mode==='scan')&&time===duration(),actorId:actor.actorId,role:actor.role,actor_uuid:worker.uuid,package_uuid:parcel!.uuid,package_id:data.package_id,contents_HU_ref:data.contents_HU_ref,pallet_uuid:pallet!.uuid,pallet_HU_ref:data.pallet_HU_ref,warehouse_headcount_delta:0,source_kind:'visual_fixture' as const,engine_operation:false as const,inventory_mutated:false,scanning:beam.visible,scan_complete:(mode==='place'&&time>=2.2)||(mode==='scan'&&time>=1.8),placed:mode==='place'&&time>=11.4,displacement_m:parcelDistance,body_distance_m:gait.distance,parcel_root_workcell_m:parcel!.position.toArray(),body_root_workcell_m:worker.position.toArray(),contact:{active:mode==='place'&&time>=5.4&&time<=13.4,surface:data.contact.surface,point_workcell_m:point.toArray(),target_workcell_m:goal.toArray(),error_m:point.distanceTo(goal)},actualFeet:legs.map(l=>({side:l.side,world:l.anchor.getWorldPosition(new THREE.Vector3()).toArray(),target:gait.feet[l.side],joint_angles:[l.thigh.rotation.x,l.shin.rotation.x,l.foot.rotation.x]})),palms_worker_local:(['L','R'] as const).map(side=>({side,direction:new THREE.Vector3(0,0,1).transformDirection(nodes.get('joint__hand_'+side)!.matrixWorld).transformDirection(worker.matrixWorld.clone().invert()).toArray()}))};
  }
  function apply(seconds:number){
    assertLive();if(!Number.isFinite(seconds))throw Error('Время должно быть конечным числом.');time=mode==='idle'||mode==='blocked'?0:THREE.MathUtils.clamp(seconds,0,duration());
    for(const[n,b]of rest){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}const forward=shipperPlacementAt(mode==='place'?time-5.4:0),back=shipperPlacementAt(mode==='place'?time-17:0);parcelDistance=forward.distance;gait=mode==='place'&&time>=17?{distance:forward.distance-back.distance,drop:back.drop,feet:{L:{...back.feet.L,travel:forward.distance-back.feet.L.travel},R:{...back.feet.R,travel:forward.distance-back.feet.R.travel}}}:forward;
    worker.position.fromArray(data.body_root_m).add(new THREE.Vector3(0,-gait.drop,-gait.distance));worker.rotation.set(0,data.body_yaw_rad,0);parcel!.position.copy(saved.parcelPosition).add(new THREE.Vector3(0,0,-parcelDistance));parcel!.quaternion.copy(saved.parcelQuaternion);
    const pose:Pose={joint__upper_arm_L:[0,0,-.15],joint__upper_arm_R:[0,0,.15]};
    if(mode==='place'){
      const service=time<5.4?time/2:time<=11.4?2.7:time<17?(time-6)/2:time<=23?5.5:(time-12)/2,legacy=[0,.7,1.1,1.5,2.1,2.7,3.7,4.3,4.9,5.5,6.1,6.7,7.1,7.5];let i=0;while(i+1<legacy.length&&legacy[i+1]<=service)i++;
      const a=data.keys[i],b=data.keys[Math.min(i+1,data.keys.length-1)],u=legacy[i]===legacy[Math.min(i+1,legacy.length-1)]?0:smooth((service-legacy[i])/(legacy[Math.min(i+1,legacy.length-1)]-legacy[i]));label=time>=5.4&&time<11.4?'Укладка на выход':time>=17&&time<23?'Отход от ленты':a.label;
      for(const name of new Set([...Object.keys(a.joints),...Object.keys(b.joints)])){const base=rest.get(nodes.get(name)!)!.angles,from=a.joints[name]??base,to=b.joints[name]??base;pose[name]=from.map((x,j)=>x+(to[j]-x)*u) as Triple;}
      const mapped=(x:number,z:number):Triple=>[x-.69,1.17-gait.drop,z+1.15-gait.distance];
      if(service>=2.1&&service<=4.3){const gap=service<2.7?.04*(1-smooth((service-2.1)/.6)):service<=3.7?0:.04*smooth((service-3.7)/.6);Object.assign(pose,solveShipperArmPose(worker,workcell,data.keys[5].joints,mapped(0,.24+gap),data.contact.local_m));}
      if((service>=1.5&&service<2.1)||(service>4.9&&service<=5.5)){const u=service<2.1?smooth((service-1.5)/.6):1-smooth((service-4.9)/.6);Object.assign(pose,solveShipperArmPose(worker,workcell,data.keys[5].joints,mapped(-.08*(1-u),.38-.10*u),data.contact.local_m));}
      if(service<=1.1)pose.joint__head=[.1,-.15*smooth(service/.7),0];
      else if(service<1.5){const u=smooth((service-1.1)/.4),to=pose.joint__head??[0,0,0];pose.joint__head=to.map((x,j)=>[.1,-.15,0][j]+(x-[.1,-.15,0][j])*u) as Triple;}
    }else if(mode==='scan'){label=time<.5?'Проверка посылки':time<1.8?'Сканирование этикетки':'Этикетка проверена';pose.joint__head=[.1,-.15*smooth(time/.5),0];}
    else if(mode==='blocked'){label='Выход занят · отгрузка не начата';pose.joint__head=[.1,-.3,0];}else label='Ожидание задания';
    for(const[name,a]of Object.entries(pose)){const n=nodes.get(name)!;if(n.userData.custom_axis_runtime)n.quaternion.setFromAxisAngle(new THREE.Vector3(...n.userData.custom_axis_runtime).normalize(),a[0]);else n.rotation.set(...a,'XYZ');}
    if(mode==='place'&&((time>5.4&&time<11.4)||(time>17&&time<23)))for(const leg of legs){
      const foot=gait.feet[leg.side],dy=leg.floor.y+gait.drop+foot.lift-leg.anchor.position.y-leg.hip.y,dz=leg.floor.z+foot.travel-gait.distance-leg.anchor.position.z-leg.hip.z,r=Math.hypot(dy,dz);
      if(r>leg.l1+leg.l2+1e-7||r<Math.abs(leg.l1-leg.l2))throw Error('Шаг превышает длину ног.');
      const absolute=Math.atan2(dz,dy)-Math.acos(THREE.MathUtils.clamp((r*r+leg.l1**2-leg.l2**2)/(2*r*leg.l1),-1,1)),a=wrap(absolute-Math.atan2(leg.a.z,leg.a.y)),second=Math.atan2(dz-leg.l1*Math.sin(absolute),dy-leg.l1*Math.cos(absolute)),b=wrap(second-Math.atan2(leg.b.z,leg.b.y)-a);leg.thigh.rotation.set(a,0,0);leg.shin.rotation.set(b,0,0);leg.foot.rotation.set(-a-b,0,0);
    }
    beam.visible=mode==='place'?time>=.4&&time<2.2:mode==='scan'&&time>=.5&&time<1.8;parcel!.userData.visual_placed=mode==='place'&&time>=11.4;parcel!.userData.visual_scanned=(mode==='place'&&time>=2.2)||(mode==='scan'&&time>=1.8);worker.userData.assignment='shipper_'+mode;return snapshot();
  }
  function setMode(next:ShipperMode){assertLive();if(!['place','scan','idle','blocked'].includes(next))throw Error('Неизвестное состояние отгрузчика.');mode=next;return apply(0);}
  function dispose(){if(released)return;released=true;assigned.delete(actor);occupied.delete(workcell);beam.removeFromParent();beam.geometry.dispose();beam.material.dispose();parcel!.position.copy(saved.parcelPosition);parcel!.quaternion.copy(saved.parcelQuaternion);if(!actor.disposed){worker.removeFromParent();if(saved.parent)saved.parent.add(worker);worker.position.copy(saved.position);worker.quaternion.copy(saved.quaternion);for(const[n,b]of rest){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}}for(const m of metadata){if(actor.disposed&&m.node===worker)continue;if(m.present)m.node.userData[m.key]=m.value;else delete m.node.userData[m.key];}}
  assigned.add(actor);occupied.add(workcell);workcell.add(worker,beam);try{apply(0);}catch(e){dispose();throw e;}
  return {apply,snapshot,setMode,dispose,get timeline(){return {...data,duration_s:duration()};},actor,workcell};
}

/** Consumes one existing worker and parcel; never creates stock or another actor. */
