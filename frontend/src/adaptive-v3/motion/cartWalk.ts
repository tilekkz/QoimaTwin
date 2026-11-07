import * as THREE from 'three';
import type {bindPickerGrip} from './grip';

export type CartWalkTimeline={schema_id:string;source_kind:'visual_fixture';engine_operation:false;duration_s:number;distance_m:number;half_step_m:number;pelvis_drop_m:number;swing_lift_m:number;wheel_radius_m:number;actor_id:string;keys:{t:number;label:string}[]};
export function validateCartWalkTimeline(value:unknown):CartWalkTimeline{
  const d=value as CartWalkTimeline;
  if(!d||d.schema_id!=='qoima.visual-cart-walk.v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.duration_s!==9||d.distance_m!==.84||d.half_step_m!==.14||d.pelvis_drop_m!==.008||d.swing_lift_m!==.012||d.wheel_radius_m!==.075||!Array.isArray(d.keys)||d.keys.length!==19||d.keys.some((k,i)=>k.t!==i*.5||typeof k.label!=='string'))throw Error('Некорректное описание движения тележки.');
  return structuredClone(d);
}
const smooth=(u:number)=>u*u*u*(10+u*(-15+6*u));
const wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));

/** Complete floor-relative targets from time, never from a previous frame. */
export function cartWalkAt(d:CartWalkTimeline,seconds:number){
  if(!Number.isFinite(seconds))throw Error('Время должно быть конечным числом.');
  const time=THREE.MathUtils.clamp(seconds,0,d.duration_s);
  let distance=0,drop=d.pelvis_drop_m,step=-1,u=0;
  const feet={L:{travel:0,lift:0,stance:true},R:{travel:0,lift:0,stance:true}};
  if(time<=1)drop*=smooth(time);
  else if(time>=8){distance=d.distance_m;drop*=1-smooth(time-8);feet.L.travel=feet.R.travel=d.distance_m;}
  else{
    step=Math.min(6,Math.floor(time-1));u=time-1-step;
    distance=step===0?.07*u*u:step===6?.77+.07*(2*u-u*u):.07+(step-1)*.14+.14*u;
    // Completed foot placements are a pure finite schedule, not event effects.
    for(let i=0;i<step;i++)feet[i%2===0?'L':'R'].travel=(i+1)*.14;
    const side=step%2===0?'L':'R',foot=feet[side];
    const end=step===6?.84:(step+1)*.14;
    foot.travel+=(end-foot.travel)*smooth(u);foot.lift=d.swing_lift_m*Math.sin(Math.PI*u)**2;foot.stance=u===0;
  }
  const key=Math.min(d.keys.length-1,Math.floor(time*2));
  return {time,distance,drop,step,u,feet,label:d.keys[key].label,complete:time===d.duration_s,source_kind:d.source_kind,engine_operation:false as const};
}

function prepareArm(actor:THREE.Object3D,side:'L'|'R',cart:THREE.Object3D){
  const find=(name:string)=>{const n=actor.getObjectByName(name);if(!n)throw Error('Нет сустава '+name);return n;};
  const upper=find('joint__upper_arm_'+side),fore=find('joint__forearm_'+side),hand=find('joint__hand_'+side),anchor=find('anchor_hand_grip_'+side);
  actor.updateWorldMatrix(true,true);
  const shoulder=actor.worldToLocal(upper.getWorldPosition(new THREE.Vector3()));
  const target=actor.worldToLocal(cart.getObjectByName('anchor_grip_'+side)!.getWorldPosition(new THREE.Vector3()));
  const desiredHand=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),-Math.PI/2);
  const offset=anchor.position.clone().applyQuaternion(desiredHand);
  const seed=[upper.rotation.x,upper.rotation.z,fore.rotation.x];
  function solve(drop:number){
    const goal=target.clone();goal.y+=drop;const v=[...seed];
    const q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();
    const point=(a:number[])=>{
      q1.setFromEuler(new THREE.Euler(a[0],0,a[1],'XYZ'));q2.setFromAxisAngle(new THREE.Vector3(1,0,0),a[2]);q12.copy(q1).multiply(q2);
      return shoulder.clone().add(fore.position.clone().applyQuaternion(q1)).add(hand.position.clone().applyQuaternion(q12)).add(offset);
    };
    for(let i=0;i<10;i++){
      const p=point(v),error=goal.clone().sub(p);if(error.length()<1e-11)break;
      const columns=v.map((_,j)=>{const a=[...v];a[j]+=1e-5;return point(a).sub(p).multiplyScalar(1e5);});
      const jac=new THREE.Matrix3().set(columns[0].x,columns[1].x,columns[2].x,columns[0].y,columns[1].y,columns[2].y,columns[0].z,columns[1].z,columns[2].z);
      if(Math.abs(jac.determinant())<1e-12)throw Error('Вырожденная цепь руки.');
      error.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=THREE.MathUtils.clamp(error.getComponent(j),-.3,.3);
    }
    if(point(v).distanceTo(goal)>1e-8)throw Error('Рука не достигает рукояти.');
    upper.rotation.set(v[0],0,v[1],'XYZ');fore.rotation.set(v[2],0,0,'XYZ');
    q1.copy(upper.quaternion).multiply(fore.quaternion);hand.quaternion.copy(q1.invert().multiply(desiredHand));
  }
  return solve;
}

/** Existing bound worker/cart only. Caller owns existing carried tote parenting. */
export function createCartWalk(binding:ReturnType<typeof bindPickerGrip>,input:CartWalkTimeline){
  const timeline=validateCartWalkTimeline(input),{actor,cart}=binding;
  if(actor.disposed||actor.role!=='picker'||actor.root.parent!==cart)throw Error('Хват комплектовщика должен быть активен.');
  cart.updateWorldMatrix(true,true);
  if(Math.abs(cart.getWorldPosition(new THREE.Vector3()).y)>1e-6||new THREE.Vector3(0,1,0).transformDirection(cart.matrixWorld).distanceTo(new THREE.Vector3(0,1,0))>1e-6)throw Error('Для движения нужен горизонтальный пол Y0.');
  const originals=new Map<THREE.Object3D,{position:THREE.Vector3;quaternion:THREE.Quaternion}>();
  cart.traverse(n=>originals.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone()}));
  const baseCart=cart.position.clone(),baseActor=actor.root.position.clone(),forward=new THREE.Vector3(0,0,1).applyQuaternion(cart.quaternion);
  const armSolvers=(['L','R'] as const).map(side=>prepareArm(actor.root,side,cart));
  const legs=(['L','R'] as const).map(side=>{
    const thigh=actor.root.getObjectByName('joint__thigh_'+side)!,shin=actor.root.getObjectByName('joint__shin_'+side)!,foot=actor.root.getObjectByName('joint__foot_'+side)!,anchor=actor.root.getObjectByName('anchor_foot_floor_'+side)!;
    const hip=actor.root.worldToLocal(thigh.getWorldPosition(new THREE.Vector3())),floor=actor.root.worldToLocal(anchor.getWorldPosition(new THREE.Vector3()));
    const a=shin.position.clone(),b=foot.position.clone();
    return {side,thigh,shin,foot,anchor,hip,floor,a,b,l1:Math.hypot(a.y,a.z),l2:Math.hypot(b.y,b.z)};
  });
  const wheels=['rear_L','rear_R','front_L','front_R'].map(label=>{
    const node=cart.getObjectByName('joint__wheel_'+label);if(!node)throw Error('Нет колеса '+label);
    const caster=node.parent!;if(caster.quaternion.angleTo(new THREE.Quaternion())>1e-6)throw Error('Поворотные опоры должны смотреть вдоль прямого пути.');
    const inverse=node.matrixWorld.clone().invert(),vertices:THREE.Vector3[]=[];
    node.traverse(n=>{if(n instanceof THREE.Mesh){const p=n.geometry.getAttribute('position');for(let i=0;i<p.count;i++)vertices.push(new THREE.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld).applyMatrix4(inverse));}});
    if(!vertices.length)throw Error('Колесо без геометрии.');
    return {label,node,base:node.position.clone(),vertices,correction:0};
  });
  let state=cartWalkAt(timeline,0),disposed=false;
  function apply(seconds:number){
    if(disposed||actor.disposed||actor.role!=='picker'||actor.root.parent!==cart)throw Error('Движение комплектовщика освобождено.');
    state=cartWalkAt(timeline,seconds);
    for(const [n,b] of originals){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}
    cart.position.copy(baseCart).addScaledVector(forward,state.distance);actor.root.position.copy(baseActor);actor.root.position.y-=state.drop;
    armSolvers.forEach(solve=>solve(state.drop));
    for(const leg of legs){
      const target=state.feet[leg.side],dy=leg.floor.y+state.drop+target.lift-leg.anchor.position.y-leg.hip.y,dz=leg.floor.z+target.travel-state.distance-leg.anchor.position.z-leg.hip.z;
      const r=Math.hypot(dy,dz);if(r>leg.l1+leg.l2+1e-7||r<Math.abs(leg.l1-leg.l2))throw Error('Шаг превышает длину ног.');
      const absolute=Math.atan2(dz,dy)-Math.acos(THREE.MathUtils.clamp((r*r+leg.l1**2-leg.l2**2)/(2*r*leg.l1),-1,1));
      const a=wrap(absolute-Math.atan2(leg.a.z,leg.a.y));
      const second=Math.atan2(dz-leg.l1*Math.sin(absolute),dy-leg.l1*Math.cos(absolute));
      const b=wrap(second-Math.atan2(leg.b.z,leg.b.y)-a);
      leg.thigh.rotation.set(a,0,0);leg.shin.rotation.set(b,0,0);leg.foot.rotation.set(-a-b,0,0);
    }
    const angle=state.distance/timeline.wheel_radius_m,c=Math.cos(angle),s=Math.sin(angle);
    for(const wheel of wheels){
      wheel.node.rotation.set(angle,0,0);const bottom=Math.min(...wheel.vertices.map(v=>v.y*c-v.z*s));
      wheel.correction=timeline.wheel_radius_m+bottom;
      if(wheel.correction< -2e-6||wheel.correction>.000643)throw Error('Колесо вышло за допуск контакта с полом.');
      wheel.node.position.y=wheel.base.y-wheel.correction;
    }
    cart.updateWorldMatrix(true,true);return snapshot();
  }
  function snapshot(){return {...state,actorId:actor.actorId,actor_uuid:actor.root.uuid,cart_uuid:cart.uuid,grip:binding.snapshot(),
    actualFeet:legs.map(l=>({side:l.side,world:l.anchor.getWorldPosition(new THREE.Vector3()).toArray(),target:state.feet[l.side],joint_angles:[l.thigh.rotation.x,l.shin.rotation.x,l.foot.rotation.x]})),
    wheels:wheels.map(w=>({label:w.label,angle:w.node.rotation.x,floor_correction_m:w.correction})),warehouse_headcount_delta:0};}
  function dispose(){if(disposed)return;disposed=true;for(const [n,b] of originals){n.position.copy(b.position);n.quaternion.copy(b.quaternion);}cart.updateWorldMatrix(true,true);}
  apply(0);return {apply,snapshot,dispose,timeline,cart,actor};
}
