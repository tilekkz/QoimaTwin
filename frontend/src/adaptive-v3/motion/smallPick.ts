import * as T from 'three';
import type {WorkerInstance} from '../workerRoles';
import {bindSmallGripper} from './smallGripper';

type Triple=[number,number,number];
type Pose=Record<string,Triple>;
export type SmallPickTimeline={schema_id:string;source_kind:'visual_fixture';engine_operation:false;duration_s:number;actor_id:string;scope:string;seeds:{low:Pose;raised:Pose;deposit:Pose};arm_guides?:{t:number;pose:Pose}[];keys:{t:number;label:string}[]};
const smooth=(u:number)=>{u=T.MathUtils.clamp(u,0,1);return u*u*u*(10+u*(-15+6*u));};
const lerp=T.MathUtils.lerp,leased=new WeakSet<T.Object3D>();
const times=[0,1.2,2,3,4,5.2,6.4,14.4,15.6,31.6,33,34,34.8,36];
export function validateSmallPickTimeline(value:unknown):SmallPickTimeline{
  const d=value as SmallPickTimeline;
  if(!d||d.schema_id!=='qoima.visual-small-pick.v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.duration_s!==36||d.actor_id!=='P01'||typeof d.scope!=='string'||!Array.isArray(d.keys)||d.keys.length!==times.length||d.keys.some((k,i)=>k.t!==times[i]||typeof k.label!=='string'))throw Error('Некорректный цикл отбора SMALL.');
  for(const seed of [d.seeds?.low,d.seeds?.raised,d.seeds?.deposit]){
    const names=['joint__torso','joint__head','joint__upper_arm_L','joint__shoulder_lift_R','joint__upper_arm_R','joint__forearm_R','joint__elbow_swivel_R','joint__palm_roll_R','joint__hand_R'];
    if(!seed||Object.keys(seed).sort().join(',')!==names.sort().join(','))throw Error('Нет исходной позы отбора.');
    for(const [name,v]of Object.entries(seed))if(!/^joint__[a-zA-Z_]+$/.test(name)||!Array.isArray(v)||v.length!==3||!v.every(Number.isFinite))throw Error('Некорректная исходная поза.');
  }
  if(d.arm_guides){if(!Array.isArray(d.arm_guides)||d.arm_guides.length<2||d.arm_guides[0].t!==31.6||d.arm_guides.at(-1)!.t!==36||d.arm_guides.some((g,i)=>!Number.isFinite(g.t)||(i>0&&g.t<=d.arm_guides![i-1].t)||!g.pose||Object.values(g.pose).some(v=>!Array.isArray(v)||v.length!==3||!v.every(Number.isFinite))))throw Error('Некорректные опорные позы руки.');}
  return structuredClone(d);
}

/** Finite foot placements, independent of playback history. Lead then follow. */
function together(seconds:number,distance:number,cycles:number){
  const duration=cycles*2+2,t=T.MathUtils.clamp(seconds,0,duration),stride=distance/cycles;
  const feet={L:{travel:0,lift:0,stance:true},R:{travel:0,lift:0,stance:true}};
  let travel=0,drop=.014;
  if(t<1)drop*=smooth(t);
  else if(t>=duration-1){travel=distance;feet.L.travel=feet.R.travel=distance;drop*=1-smooth(t-duration+1);}
  else{
    const step=Math.min(cycles*2-1,Math.floor(t-1)),u=t-1-step,cycle=Math.floor(step/2),leading=step%2===0;
    feet.L.travel=feet.R.travel=cycle*stride;
    if(!leading)feet.L.travel+=stride;
    const side=leading?'L':'R',foot=feet[side];foot.travel+=stride*smooth(u);foot.lift=.012*Math.sin(Math.PI*u)**2;foot.stance=u===0;
    travel=cycle*stride+stride*.5*(step%2+smooth(u));
  }
  return {travel,drop,feet};
}

type MotionGait=ReturnType<typeof together>&{root_offset:Triple;feet:{L:{travel:number;lift:number;stance:boolean;offset:Triple};R:{travel:number;lift:number;stance:boolean;offset:Triple}}};
function routedGait(seconds:number,backward=false):MotionGait{
 const g=backward?together(seconds,.32,3):together(seconds,7,7);
 const point=(s:number):Triple=>backward?[0,0,s]:s<=3?[.13*s,0,0]:[.39+.36*(s-3)/4,0,-.45*(s-3)/4];
 const arc=(s:number)=>backward?s:s<=3?.13*s:.39+Math.hypot(.36,.45)*(s-3)/4;
 return {...g,travel:arc(g.travel),root_offset:point(g.travel),feet:{L:{...g.feet.L,travel:arc(g.feet.L.travel),offset:point(g.feet.L.travel)},R:{...g.feet.R,travel:arc(g.feet.R.travel),offset:point(g.feet.R.travel)}}};
}

export function smallPickAt(input:SmallPickTimeline,seconds:number){
  if(!Number.isFinite(seconds))throw Error('Время должно быть конечным числом.');
  const time=T.MathUtils.clamp(seconds,0,36),u=(a:number,b:number)=>smooth((time-a)/(b-a));
  const body:Triple=[1.2,0,.88],tool:Triple=[.945,1.2645,.32];
  let angle=Math.PI*.75,opening=0,seedWeight=1,torso=.15;
  let gait:MotionGait|undefined,direction=new T.Vector3();
  if(time<=1.2){const v=u(0,1.2);tool[1]=lerp(1.2645,1.17,v);angle=lerp(Math.PI*.75,Math.PI*5/8,v);seedWeight=1-v;}
  else if(time<=2){tool[1]=1.17;angle=Math.PI*5/8;opening=u(1.2,2);seedWeight=0;}
  else if(time<=3){tool[1]=lerp(1.17,1.1245,u(2,3));angle=Math.PI*5/8;opening=1;seedWeight=0;}
  else if(time<=4){tool[1]=1.1245;angle=Math.PI*5/8;opening=1-u(3,4);seedWeight=0;}
  else if(time<=5.2){tool[1]=lerp(1.1245,1.17,u(4,5.2));angle=Math.PI*5/8;seedWeight=0;}
  else if(time<=6.4){const v=u(5.2,6.4);tool[1]=lerp(1.17,1.2645,v);angle=lerp(Math.PI*5/8,Math.PI*.75,v);seedWeight=v;}
  else if(time<=14.4){gait=routedGait(time-6.4,true);direction.set(0,0,1);}
  else if(time<=15.6){body[2]+=.32;tool[2]+=.32;const v=u(14.4,15.6);tool[1]=lerp(1.2645,1.1,v);angle=lerp(Math.PI*.75,Math.PI*5/8,v);seedWeight=1-v;}
  else{
    body[2]+=.32;tool[2]+=.32;tool[1]=1.1;angle=Math.PI*5/8;seedWeight=0;
    direction.set(.75,0,-.45).normalize();
    if(time<=31.6)gait=routedGait(time-15.6);
    else{
      body[0]+=Math.hypot(.75,.45)*direction.x;body[2]+=Math.hypot(.75,.45)*direction.z;tool[0]+=Math.hypot(.75,.45)*direction.x;tool[2]+=Math.hypot(.75,.45)*direction.z;
      const v=u(31.6,33);tool[0]=lerp(tool[0],1.75,v);tool[1]=lerp(1.1,.957,v);tool[2]=lerp(tool[2],.02,v);torso=.15;
      if(time>=33){opening=u(33,34);tool[1]=.957;}
      if(time>=34){opening=1-u(34,34.8);}
      if(time>=34.8){tool[0]=lerp(1.75,1.63,u(34.8,35.2));tool[1]=lerp(.957,1.08,u(35.2,36));tool[2]=lerp(.02,.15,u(35.2,36));}
    }
  }
  if(time>=14.4)torso=time<=15.6?.15*(1-u(14.4,15.6)):time<=32.2?0:time<=33?.15*u(32.2,33):time<35.2?.15:.15*(1-u(35.2,36));
  if(gait){body[0]+=gait.root_offset[0];body[2]+=gait.root_offset[2];body[1]-=gait.drop;tool[0]+=gait.root_offset[0];tool[2]+=gait.root_offset[2];}
  const attached=time>=4&&time<=33,fall=time>33;
  const bottom=time<4?1.1225:fall?Math.max(.64,.955-.5*9.81*(time-33)**2):tool[1]-.002;
  let label=input.keys[0].label;for(const key of input.keys)if(time>=key.t)label=key.label;
  return {time,body,tool,angle,opening,seedWeight,depositWeight:u(31.6,33),torso,gait,direction:direction.toArray() as Triple,attached,fall,package_bottom_m:bottom,label,complete:time===36,source_kind:'visual_fixture' as const,engine_operation:false as const};
}

function linear(matrix:number[][],rhs:number[]){
  const n=rhs.length,a=matrix.map((row,i)=>[...row,rhs[i]]);
  for(let c=0;c<n;c++){
    let pivot=c;for(let r=c+1;r<n;r++)if(Math.abs(a[r][c])>Math.abs(a[pivot][c]))pivot=r;
    if(Math.abs(a[pivot][c])<1e-20)throw Error('Вырожденный расчёт суставов.');[a[c],a[pivot]]=[a[pivot],a[c]];
    const divisor=a[c][c];for(let j=c;j<=n;j++)a[c][j]/=divisor;
    for(let r=0;r<n;r++)if(r!==c){const f=a[r][c];for(let j=c;j<=n;j++)a[r][j]-=f*a[c][j];}
  }
  return a.map(row=>row[n]);
}
const q=(a:Triple)=>new T.Quaternion().setFromEuler(new T.Euler(...a,'XYZ'));
function solve3(point:(v:number[])=>T.Vector3,goal:T.Vector3,initial:number[]){
  const v=[...initial];
  for(let i=0;i<30;i++){
    const p=point(v),e=goal.clone().sub(p);if(e.length()<1e-10)break;
    const c=v.map((_,j)=>{const b=[...v];b[j]+=1e-5;return point(b).sub(p).multiplyScalar(1e5);});
    const jac=new T.Matrix3().set(c[0].x,c[1].x,c[2].x,c[0].y,c[1].y,c[2].y,c[0].z,c[1].z,c[2].z);
    if(Math.abs(jac.determinant())<1e-12)throw Error('Вырожденная цепь отбора.');
    e.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=T.MathUtils.clamp(e.getComponent(j),-.2,.2);
  }
  if(point(v).distanceTo(goal)>1e-8)throw Error('Цель отбора вне досягаемости.');
  return v;
}

/** One supplied actor/tool and the four existing package objects. No stock creation. */
export function createSmallPickMotion(cell:T.Object3D,actor:WorkerInstance,tool:T.Object3D,input:SmallPickTimeline){
  const timeline=validateSmallPickTimeline(input),worker=actor.root;
  if(cell.userData.asset_id!=='picker-pick-source-fixture'||cell.userData.engine_operation!==false||worker.userData.asset_id!=='worker-small-pick'||actor.disposed||actor.role!=='picker'||actor.actorId!=='P01'||leased.has(cell)||leased.has(worker)||leased.has(tool))throw Error('Занят комплектовщик или инструмент.');
  cell.updateWorldMatrix(true,true);worker.updateWorldMatrix(true,true);tool.updateWorldMatrix(true,true);
  if([cell,worker,tool].some(n=>n.getWorldScale(new T.Vector3()).toArray().some(v=>Math.abs(v-1)>1e-7))||Math.abs(cell.getWorldPosition(new T.Vector3()).y)>1e-6||new T.Vector3(0,1,0).transformDirection(cell.matrixWorld).distanceTo(new T.Vector3(0,1,0))>1e-6)throw Error('Нужен горизонтальный стенд масштаба1:1.');
  const nodes=new Map<string,T.Object3D>();worker.traverse(n=>{if(n.name.startsWith('joint__'))nodes.set(n.name,n);});
  const node=(name:string)=>{const n=nodes.get(name);if(!n)throw Error('Нет сустава '+name);return n;};
  const units=[17,23].map(i=>{const n=cell.getObjectByName('primary_unit__'+i);if(!n)throw Error('Нет исходной упаковки '+i);return n;});
  const allUnits:T.Object3D[]=[];cell.traverse(n=>{if(n.userData.role==='visual_primary_package_instance')allUnits.push(n);});
  if(allUnits.map(n=>n.name).sort().join(',')!==['14','17','20','23'].map(i=>'primary_unit__'+i).join(','))throw Error('Изменился состав исходной коробки.');
  const caseNode=cell.getObjectByName('small_case_open_partial_root');if(!caseNode)throw Error('Нет исходной внешней коробки.');
  const tote=cell.getObjectByName('order-tote')!;if(!tote)throw Error('Нет существующего лотка.');
  const saved=new Map<T.Object3D,{parent:T.Object3D|null;position:T.Vector3;quaternion:T.Quaternion}>();
  for(const root of [worker,tool,...units])root.traverse(n=>saved.set(n,{parent:n.parent,position:n.position.clone(),quaternion:n.quaternion.clone()}));
  const metadataTargets:[T.Object3D,string[]][]=[[caseNode,['fixture_remaining_primary_packages','fixture_current_case_gross_mass_kg']],[tote,['visual_contents_ids','visual_incoming_ids','visual_contents_settled']],[tool,['visual_carried_primary_ids']],[worker,['assignment']]];
  const metadata=metadataTargets.flatMap(([n,keys])=>keys.map(key=>({node:n,key,present:Object.hasOwn(n.userData,key),value:structuredClone(n.userData[key])})));
  const workerNodes=new Set<T.Object3D>();worker.traverse(n=>workerNodes.add(n));
  const frame=node('joint__torso'),upper=node('joint__upper_arm_R'),fore=node('joint__forearm_R'),hand=node('joint__hand_R'),grip=worker.getObjectByName('anchor_hand_grip_R')!;
  const shoulder=frame.worldToLocal(upper.getWorldPosition(new T.Vector3())),elbow=upper.worldToLocal(fore.getWorldPosition(new T.Vector3())),wrist=fore.worldToLocal(hand.getWorldPosition(new T.Vector3())),axis=elbow.clone().normalize();
  const legs=(['L','R'] as const).map(side=>{const thigh=node('joint__thigh_'+side),shin=node('joint__shin_'+side),foot=node('joint__foot_'+side),anchor=worker.getObjectByName('anchor_foot_floor_'+side)!;return {side,thigh,shin,foot,anchor,hip:worker.worldToLocal(thigh.getWorldPosition(new T.Vector3())),floor:worker.worldToLocal(anchor.getWorldPosition(new T.Vector3())),a:thigh.worldToLocal(shin.getWorldPosition(new T.Vector3())),b:shin.worldToLocal(foot.getWorldPosition(new T.Vector3()))};});
  const gripper=bindSmallGripper(tool);let state=smallPickAt(timeline,0),released=false,armPose:Pose={};
  function pose(name:string,v:Triple){const n=node(name);if(n.userData.custom_axis_runtime)n.quaternion.setFromAxisAngle(new T.Vector3(...n.userData.custom_axis_runtime).normalize(),v[0]);else n.quaternion.copy(q(v));}
  function arm(seed:Pose,angle:number){
    worker.updateWorldMatrix(true,true);const target=cell.localToWorld(new T.Vector3(...state.tool).add(new T.Vector3(0,.148,.23))),goal=frame.worldToLocal(target);
    const desired=frame.getWorldQuaternion(new T.Quaternion()).invert().multiply(cell.getWorldQuaternion(new T.Quaternion())).multiply(q([angle,0,0]));
    const offset=grip.position.clone().applyQuaternion(desired);
    const v=[seed.joint__upper_arm_R[0]+seed.joint__shoulder_lift_R[0],seed.joint__upper_arm_R[2],seed.joint__forearm_R[0],seed.joint__upper_arm_R[1],seed.joint__elbow_swivel_R[0],seed.joint__palm_roll_R[1]],ranges=[[-3,.7],[-.7,.7],[-2.2,.15],[-.55,.55],[-Math.PI,Math.PI],[-Math.PI,Math.PI]];
    function evaluate(a:number[]){
      const first=q([a[0],a[3],a[1]]),second=first.clone().multiply(new T.Quaternion().setFromAxisAngle(axis,a[4])).multiply(q([a[2],0,0]));
      const point=shoulder.clone().add(elbow.clone().applyQuaternion(first)).add(wrist.clone().applyQuaternion(second)).add(offset),h=new T.Euler().setFromQuaternion(q([0,a[5],0]).invert().multiply(second.invert()).multiply(desired),'XYZ');
      const error=point.sub(goal),angles=[h.x,h.y,h.z],limits=[.599,.649,.399];
      return {h,residual:[error.x,error.y,error.z,...angles.map((x,j)=>.15*Math.sign(x)*Math.max(0,Math.abs(x)-limits[j]))]};
    }
    for(let i=0;i<160;i++){
      const r=evaluate(v).residual;if(Math.hypot(...r)<1e-10)break;
      const columns=v.map((_,j)=>{const a=[...v];a[j]+=1e-5;return evaluate(a).residual.map((x,k)=>(x-r[k])*1e5);});
      const fixed=new Set<number>();let delta:number[]=[];
      for(let pass=0;pass<v.length;pass++){
        const matrix=columns.map((c,j)=>columns.map((d,k)=>fixed.has(j)||fixed.has(k)?(j===k?1:0):c.reduce((sum,x,i)=>sum+x*d[i],j===k?1e-9:0))),rhs=columns.map((c,j)=>fixed.has(j)?0:-c.reduce((sum,x,i)=>sum+x*r[i],0));
        delta=linear(matrix,rhs);
        const blocked=delta.map((x,j)=>((v[j]<=ranges[j][0]+1e-9&&x<0)||(v[j]>=ranges[j][1]-1e-9&&x>0))?j:-1).filter(j=>j>=0&&!fixed.has(j));
        if(!blocked.length)break;blocked.forEach(j=>fixed.add(j));
      }
      for(let j=0;j<v.length;j++)v[j]=T.MathUtils.clamp(v[j]+T.MathUtils.clamp(delta[j],-.15,.15),ranges[j][0],ranges[j][1]);
    }
    const solved=evaluate(v);if(Math.hypot(...solved.residual)>1e-8)throw Error('Инструмент вне пределов досягаемости: '+JSON.stringify({v,r:solved.residual}));
    const h=solved.h,yaw=v[3],twist=v[4],roll=v[5],lift=Math.min(0,Math.max(-.8,v[0]+2.2));
    const angles:Pose={joint__shoulder_lift_R:[lift,0,0],joint__upper_arm_R:[v[0]-lift,yaw,v[1]],joint__forearm_R:[v[2],0,0],joint__elbow_swivel_R:[twist,0,0],joint__palm_roll_R:[0,roll,0],joint__hand_R:[h.x,h.y,h.z]};
    const limits:Record<string,[number,number][]>={joint__shoulder_lift_R:[[-.8,0],[0,0],[0,0]],joint__upper_arm_R:[[-2.2,.7],[-.55,.55],[-.7,.7]],joint__forearm_R:[[-2.2,.15],[0,0],[0,0]],joint__hand_R:[[-.6,.6],[-.65,.65],[-.4,.4]]};
    armPose=angles;
    for(const [name,a]of Object.entries(angles)){if(limits[name]&&a.some((x,i)=>x<limits[name][i][0]-1e-7||x>limits[name][i][1]+1e-7))throw Error('Предел отбора '+name+' '+a);pose(name,a);}
  }
  function apply(seconds:number){
    if(released||actor.disposed||actor.role!=='picker')throw Error('Отбор освобождён.');
    const next=smallPickAt(timeline,seconds);state=next;
    for(const [n,b]of saved){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}
    if(worker.parent!==cell)cell.add(worker);if(tool.parent!==cell)cell.add(tool);
    worker.position.fromArray(state.body);worker.rotation.set(0,Math.PI,0);tool.position.fromArray(state.tool);tool.quaternion.identity();
    pose('joint__torso',[state.torso,0,0]);pose('joint__head',[-.25,0,.12]);pose('joint__upper_arm_L',[.6,0,0]);
    const blendedSeed=state.seedWeight+.25*Math.sin(Math.PI*state.seedWeight);
    const seed:Pose={};for(const name of Object.keys(timeline.seeds.low))seed[name]=timeline.seeds.low[name].map((x,j)=>lerp(lerp(x,timeline.seeds.raised[name][j],blendedSeed),timeline.seeds.deposit[name][j],state.depositWeight)) as Triple;
    if(timeline.arm_guides&&state.time>=31.6){const guides=timeline.arm_guides;let lo=0,hi=guides.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(guides[mid].t<=state.time)lo=mid;else hi=mid;}const a=guides[lo],b=guides[hi],u=T.MathUtils.clamp((state.time-a.t)/(b.t-a.t),0,1);for(const name of Object.keys(a.pose))seed[name]=a.pose[name].map((x,j)=>lerp(x,b.pose[name][j],u)) as Triple;}
    arm(seed,state.angle);
    const drive=gripper.apply(state.opening,state.angle),close=.0225-.02*Math.max(...Array.from({length:32},(_,i)=>Math.cos(state.angle-(i+.5)*Math.PI/16)));
    node('joint__finger_upper_R').position.set(0,-close,0);node('joint__finger_lower_R').position.set(0,close,0);node('joint__finger_thumb_R').position.set(0,0,-.005);
    pose('joint__thumb_press_R',[state.opening>0?drive.manual_thumb_press_rad:0,0,0]);
    if(state.gait){
      const rootOffset=new T.Vector3(...state.gait.root_offset);
      for(const leg of legs){
        const foot=state.gait.feet[leg.side],target=leg.floor.clone().add(new T.Vector3(...foot.offset).sub(rootOffset).applyAxisAngle(new T.Vector3(0,1,0),-Math.PI));target.y+=state.gait.drop+foot.lift;
        const goal=target.sub(leg.anchor.position).sub(leg.hip);
        const point=(v:number[])=>leg.a.clone().applyQuaternion(q([v[0],0,v[1]])).add(leg.b.clone().applyQuaternion(q([v[0],0,v[1]]).multiply(q([v[2],0,0]))));
        const v=solve3(point,goal,[-.15,0,.3]);
        leg.thigh.quaternion.copy(q([v[0],0,v[1]]));leg.shin.quaternion.copy(q([v[2],0,0]));leg.foot.quaternion.copy(leg.thigh.quaternion.clone().multiply(leg.shin.quaternion).invert());
      }
    }
    units.forEach((unit,i)=>{
      if(timeAttached()){tool.add(unit);unit.position.set(i===0?-.0325:.0325,-.002,0);unit.quaternion.identity();}
      else if(state.fall){tote.add(unit);unit.position.set((i===0?-.0325:.0325),state.package_bottom_m-.62,0);unit.quaternion.identity();}
      else{const b=saved.get(unit)!;b.parent!.add(unit);unit.position.copy(b.position);unit.quaternion.copy(b.quaternion);}
    });
    caseNode!.userData.fixture_remaining_primary_packages=state.time>=4?2:4;caseNode!.userData.fixture_current_case_gross_mass_kg=state.time>=4?.17:.24;
    const ids=units.map(n=>n.name),settled=state.fall&&state.package_bottom_m===.64;tote.userData.visual_contents_ids=settled?ids:[];tote.userData.visual_incoming_ids=state.fall&&!settled?ids:[];tote.userData.visual_contents_settled=settled;tool.userData.visual_carried_primary_ids=state.attached?ids:[];worker.userData.assignment='small_pick_visual_fixture';
    cell.updateWorldMatrix(true,true);return snapshot();
  }
  function timeAttached(){return state.attached;}
  function snapshot(){return {...state,arm_pose:structuredClone(armPose),actorId:actor.actorId,actor_uuid:worker.uuid,tool_uuid:tool.uuid,package_ids:units.map(n=>n.name),package_uuids:units.map(n=>n.uuid),package_parents:units.map(n=>n.parent?.name),grip_error_m:grip.getWorldPosition(new T.Vector3()).distanceTo(cell.localToWorld(new T.Vector3(...state.tool).add(new T.Vector3(0,.148,.23)))),warehouse_headcount_delta:0,inventory_mutated:false};}
  function dispose(){if(released)return;released=true;gripper.dispose();for(const [n,b]of saved){if(actor.disposed&&workerNodes.has(n))continue;if(b.parent)b.parent.add(n);else n.removeFromParent();n.position.copy(b.position);n.quaternion.copy(b.quaternion);}for(const m of metadata){if(actor.disposed&&workerNodes.has(m.node))continue;if(m.present)m.node.userData[m.key]=m.value;else delete m.node.userData[m.key];}for(const n of [cell,worker,tool])leased.delete(n);}
  for(const n of [cell,worker,tool])leased.add(n);
  try{apply(0);}catch(e){dispose();throw e;}
  return {apply,snapshot,dispose,timeline,actor,tool,cell};
}
