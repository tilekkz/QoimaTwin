import * as THREE from 'three';
import type {XYZ} from './warehouseTypes';

type Side='L'|'R';type Q=[number,number,number,number];
type Limits=[[number,number],[number,number],[number,number]];
export class WarehouseGaitError extends Error{constructor(readonly reason:'UNSUPPORTED_RIG'|'UNSUPPORTED_PATH'|'GAIT_UNREACHABLE'|'JOINT_LIMIT'|'INVALID_TIME',message:string){super(message);}}
export type NativeGaitNode={name:string;parent:string;position:XYZ;quaternion:Q;scale:XYZ;matrix_auto_update:boolean;matrix_world_auto_update:boolean;limits:Limits|null;mesh:{positions:number[];indices:number[]|null}|null};
export type NativeWorkerGaitRig={asset_id:string;root_matrix_auto_update:boolean;root_matrix_world_auto_update:boolean;nodes:NativeGaitNode[];legs:{side:Side;hip:XYZ;a:XYZ;b:XYZ;sole:XYZ;floor:XYZ;vertices:XYZ[]}[]};
type Foot={point:XYZ;yaw_rad:number};type Feet=Record<Side,Foot>;
type SpeedProfile={length_m:number;peak_m_s:number;acceleration_m_s2:number;ramp_s:number;cruise_s:number;duration_s:number;start_s:number;origin:XYZ;direction:XYZ};
export type WorkerGaitPhase={kind:'prepare'|'turn_step'|'walk_step'|'retreat_step'|'settle';start_s:number;end_s:number;swing:Side|null;root:XYZ;yaw_from:number;yaw_to:number;feet_from:Feet;feet_to:Feet;arms_from:number;arms_to:number;margin_from:number;margin_to:number;profile:SpeedProfile|null};
export type WorkerGaitPose={at_s:number;stage:WorkerGaitPhase['kind']|'route_end';root_world:XYZ;yaw_rad:number;speed_m_s:number;body_drop_m:number;feet:Record<Side,Foot&{stance:boolean;lift_m:number}>;joint_rotations:Record<string,Q>;maximum_IK_error_m:number;completed_jobs:0};
export type CompiledWorkerGait={duration_s:number;phases:WorkerGaitPhase[];source_speed_m_s:number;assumptions:{step_advance_max_m:.22;retreat_speed_cap_m_s:.35;escape_distance_m:number;turn_clearance_radius_m:number;turn_stance_half_width_m:number;swing_lift_m:.018;turn_increment_max_rad:number;turn_step_duration_s:.32;acceleration_m_s2:.8;stance_model:string};sample:(at_s:number)=>WorkerGaitPose};
const modelBrand=new WeakSet<object>(),axisY=new THREE.Vector3(0,1,0),smooth=(u:number)=>u*u*u*(10+u*(-15+6*u)),wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
function fail(reason:WarehouseGaitError['reason'],message:string):never{throw new WarehouseGaitError(reason,message);}
function freeze<T>(value:T):T{if(value&&typeof value==='object'&&!Object.isFrozen(value)){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}
const tuple=(v:THREE.Vector3)=>v.toArray() as XYZ,rotation=(v:THREE.Quaternion)=>v.toArray() as Q,vector=(v:XYZ)=>new THREE.Vector3(...v);
const required=['pelvis','torso','head',...['upper_arm','forearm','hand','thigh','shin','foot'].flatMap(n=>['L','R'].map(s=>n+'_'+s))].map(n=>'joint__'+n);

/** Native calibration only; the walk context independently verifies the source GLB bytes. */
export function deriveNativeWorkerGaitRig(root:THREE.Object3D):NativeWorkerGaitRig{
 if(!['worker-base','worker-manual'].includes(root.userData.asset_id))fail('UNSUPPORTED_RIG','Нужен исходный rig работника V3.');root.updateWorldMatrix(true,true);const nodes:NativeGaitNode[]=[];
 root.traverse(n=>{if(n===root)return;let limits:Limits|null=null;if(n.name.startsWith('joint__')&&n.userData.limits_xyz_json){const value=JSON.parse(n.userData.limits_xyz_json);if(!Array.isArray(value)||value.length!==3||value.some((r:unknown)=>!Array.isArray(r)||r.length!==2||!r.every(Number.isFinite)))fail('UNSUPPORTED_RIG','Некорректные пределы сустава.');limits=value as Limits;}
  let mesh:NativeGaitNode['mesh']=null;if(n instanceof THREE.Mesh){const p=n.geometry.getAttribute('position'),ix=n.geometry.index,positions:number[]=[];for(let i=0;i<p.count;i++)positions.push(p.getX(i),p.getY(i),p.getZ(i));mesh={positions,indices:ix?Array.from({length:ix.count},(_,i)=>ix.getX(i)):null};}
  nodes.push({name:n.name,parent:n.parent===root?'$root':n.parent!.name,position:tuple(n.position),quaternion:rotation(n.quaternion),scale:tuple(n.scale),matrix_auto_update:n.matrixAutoUpdate,matrix_world_auto_update:n.matrixWorldAutoUpdate,limits,mesh});
 });
 for(const name of required)if(!nodes.find(n=>n.name===name)?.limits)fail('UNSUPPORTED_RIG','Нет исходных пределов '+name);
 const legs=(['L','R'] as const).map(side=>{const thigh=root.getObjectByName('joint__thigh_'+side)!,shin=root.getObjectByName('joint__shin_'+side)!,foot=root.getObjectByName('joint__foot_'+side)!,sole=root.getObjectByName('anchor_foot_floor_'+side);if(!sole||shin.parent!==thigh||foot.parent!==shin||sole.parent!==foot)fail('UNSUPPORTED_RIG','Неподдерживаемая цепь ноги.');
  const vertices:XYZ[]=[],inverse=foot.matrixWorld.clone().invert();foot.traverse(n=>{if(n instanceof THREE.Mesh){const p=n.geometry.getAttribute('position');for(let i=0;i<p.count;i++)vertices.push(tuple(new THREE.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld).applyMatrix4(inverse)));}});
  const hip=tuple(root.worldToLocal(thigh.getWorldPosition(new THREE.Vector3()))),floor=tuple(root.worldToLocal(sole!.getWorldPosition(new THREE.Vector3())));if(!vertices.length||Math.abs(floor[1])>2e-6||Math.abs(Math.min(...vertices.map(v=>v[1]))-sole!.position.y)>2e-6)fail('UNSUPPORTED_RIG','Подошва не связана с исходным полом.');
  return{side,hip,a:tuple(shin.position),b:tuple(foot.position),sole:tuple(sole!.position),floor,vertices};});
 const rig=freeze({asset_id:root.userData.asset_id as string,root_matrix_auto_update:root.matrixAutoUpdate,root_matrix_world_auto_update:root.matrixWorldAutoUpdate,nodes,legs});modelBrand.add(rig);return rig;
}
/** Entire unchanged native mesh, including rotated feet/fingertips; no width-only envelope. */
export function nativeWorkerGaitBounds(rig:NativeWorkerGaitRig,pose:WorkerGaitPose){
 if(!modelBrand.has(rig))fail('UNSUPPORTED_RIG','Нужна исходная native-калибровка.');const matrices=new Map<string,THREE.Matrix4>(),box=new THREE.Box3();matrices.set('$root',new THREE.Matrix4().compose(vector(pose.root_world),new THREE.Quaternion().setFromAxisAngle(axisY,pose.yaw_rad),new THREE.Vector3(1,1,1)));
 for(const n of rig.nodes){const parent=matrices.get(n.parent);if(!parent)fail('UNSUPPORTED_RIG','Разорван исходный native-граф.');const matrix=new THREE.Matrix4().compose(vector(n.position),new THREE.Quaternion(...(pose.joint_rotations[n.name]??n.quaternion)),vector(n.scale)).premultiply(parent);matrices.set(n.name,matrix);if(n.mesh)for(let i=0;i<n.mesh.positions.length;i+=3)box.expandByPoint(new THREE.Vector3(n.mesh.positions[i],n.mesh.positions[i+1],n.mesh.positions[i+2]).applyMatrix4(matrix));}
 return{min:tuple(box.min),max:tuple(box.max)};
}
function velocityProfile(length:number,speed:number,start_s:number,origin:XYZ,direction:XYZ):SpeedProfile{const peak=Math.min(speed,Math.sqrt(.8*length)),ramp=peak/.8,cruise=Math.max(0,length/peak-ramp);return{length_m:length,peak_m_s:peak,acceleration_m_s2:.8,ramp_s:ramp,cruise_s:cruise,duration_s:2*ramp+cruise,start_s,origin,direction};}
function distanceTime(p:SpeedProfile,d:number){const rampDistance=.5*p.peak_m_s*p.ramp_s;if(d<=rampDistance)return Math.sqrt(2*Math.max(0,d)/p.acceleration_m_s2);if(d<p.length_m-rampDistance)return p.ramp_s+(d-rampDistance)/p.peak_m_s;return p.duration_s-Math.sqrt(2*Math.max(0,p.length_m-d)/p.acceleration_m_s2);}
function distanceAt(p:SpeedProfile,t:number){t=Math.max(0,Math.min(p.duration_s,t-p.start_s));if(t<p.ramp_s)return{distance:.5*p.acceleration_m_s2*t*t,speed:p.acceleration_m_s2*t};if(t<p.ramp_s+p.cruise_s)return{distance:.5*p.peak_m_s*p.ramp_s+p.peak_m_s*(t-p.ramp_s),speed:p.peak_m_s};const left=p.duration_s-t;return{distance:p.length_m-.5*p.acceleration_m_s2*left*left,speed:p.acceleration_m_s2*left};}
function solveLeg(rig:NativeWorkerGaitRig,side:Side,root:XYZ,rootYaw:number,target:Foot):{rotations:Record<string,Q>;error:number}{
 const leg=rig.legs.find(l=>l.side===side)!,a=vector(leg.a),b=vector(leg.b),local=vector(target.point).sub(vector(root)).applyAxisAngle(axisY,-rootYaw),desired=new THREE.Quaternion().setFromAxisAngle(axisY,wrap(target.yaw_rad-rootYaw)),goal=local.sub(vector(leg.sole).applyQuaternion(desired)).sub(vector(leg.hip)),twist=wrap(target.yaw_rad-rootYaw)*.30;
 const l1=Math.hypot(a.y,a.z),l2=Math.hypot(b.y,b.z),r=Math.hypot(goal.y,goal.z),absolute=Math.atan2(goal.z,goal.y)-Math.acos(THREE.MathUtils.clamp((r*r+l1*l1-l2*l2)/(2*r*l1),-1,1)),first=wrap(absolute-Math.atan2(a.z,a.y)),second=wrap(Math.atan2(goal.z-l1*Math.sin(absolute),goal.y-l1*Math.cos(absolute))-Math.atan2(b.z,b.y)-first),values=[first,0,second];
 const q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();function point(v:number[]){q1.setFromEuler(new THREE.Euler(v[0],0,0,'XYZ'));q2.setFromEuler(new THREE.Euler(v[2],twist,v[1],'XYZ'));q12.copy(q1).multiply(q2);return a.clone().applyQuaternion(q1).add(b.clone().applyQuaternion(q12));}
 for(let i=0;i<30;i++){const p=point(values),error=goal.clone().sub(p);if(error.length()<1e-10)break;const columns=values.map((_,j)=>{const v=[...values];v[j]+=1e-5;return point(v).sub(p).multiplyScalar(1e5);}),jac=new THREE.Matrix3().set(columns[0].x,columns[1].x,columns[2].x,columns[0].y,columns[1].y,columns[2].y,columns[0].z,columns[1].z,columns[2].z);if(Math.abs(jac.determinant())<1e-12)fail('GAIT_UNREACHABLE','Вырожденная опорная цепь ноги.');error.applyMatrix3(jac.invert());for(let j=0;j<3;j++)values[j]+=THREE.MathUtils.clamp(error.getComponent(j),-.3,.3);}
 const error=point(values).distanceTo(goal);if(error>2e-7)fail('GAIT_UNREACHABLE','Исходная нога не достигает целевой подошвы.');
 const foot=q12.clone().invert().multiply(desired),angles=[new THREE.Euler(values[0],0,0,'XYZ'),new THREE.Euler(values[2],twist,values[1],'XYZ'),new THREE.Euler().setFromQuaternion(foot,'XYZ')],names=['joint__thigh_'+side,'joint__shin_'+side,'joint__foot_'+side],rotations:Record<string,Q>={};
 for(let i=0;i<3;i++){const ranges=rig.nodes.find(n=>n.name===names[i])!.limits!,v=[angles[i].x,angles[i].y,angles[i].z];if(v.some((a,k)=>a<ranges[k][0]-1e-8||a>ranges[k][1]+1e-8))fail('JOINT_LIMIT','Шаг выходит за исходный предел '+names[i]);rotations[names[i]]=rotation(new THREE.Quaternion().setFromEuler(angles[i]));}
 return{rotations,error};
}

/** New unloaded human travel primitive. Prepared nine-second cart clip is neither used nor rescaled. */
export function compileNativeWorkerGait(rig:NativeWorkerGaitRig,points:XYZ[],startYaw:number,speed:number,fixedBounds:readonly {min:XYZ;max:XYZ}[]=[]):CompiledWorkerGait{
 if(!modelBrand.has(rig)||!points.length||!Number.isFinite(startYaw)||!Number.isFinite(speed)||speed<=0||speed>1.2||points.some(p=>p.length!==3||!p.every(Number.isFinite)||Math.abs(p[1])>1e-8))fail('UNSUPPORTED_PATH','Нужен горизонтальный исходный маршрут и скорость профиля.');
 const phases:WorkerGaitPhase[]=[],origin=[...points[0]] as XYZ;let time=0,centre=[...origin] as XYZ,yaw=startYaw,next:Side='L',margin=0;
 const nominal=(side:Side,p:XYZ,heading:number,half:number|null=null):Foot=>{const point=vector(rig.legs.find(l=>l.side===side)!.floor);if(half!==null)point.x=Math.sign(point.x)*half;return{point:tuple(point.applyAxisAngle(axisY,heading).add(vector(p))),yaw_rad:heading};};
 let feet:Feet={L:nominal('L',centre,yaw),R:nominal('R',centre,yaw)};const copyFeet=()=>structuredClone(feet);
 function step(kind:'turn_step'|'walk_step'|'retreat_step',toYaw:number,toFeet:Feet,from:number,to:number,profile:SpeedProfile|null){phases.push({kind,start_s:from,end_s:to,swing:next,root:[...centre],yaw_from:yaw,yaw_to:toYaw,feet_from:copyFeet(),feet_to:structuredClone(toFeet),arms_from:0,arms_to:0,margin_from:margin,margin_to:.0005,profile});time=to;feet=structuredClone(toFeet);yaw=toYaw;margin=.0005;next=next==='L'?'R':'L';}
 const groups:{start:XYZ;end:XYZ;direction:XYZ;length:number}[]=[];
 for(let i=1;i<points.length;i++){const delta=vector(points[i]).sub(vector(points[i-1])),length=delta.length();if(length<1e-10)continue;const direction=tuple(delta.multiplyScalar(1/length)),previous=groups.at(-1);if(previous&&vector(previous.direction).distanceTo(vector(direction))<1e-9){previous.end=[...points[i]];previous.length+=length;}else groups.push({start:[...points[i-1]],end:[...points[i]],direction,length});}
 if(groups.length){phases.push({kind:'prepare',start_s:0,end_s:.35,swing:null,root:[...centre],yaw_from:yaw,yaw_to:yaw,feet_from:copyFeet(),feet_to:copyFeet(),arms_from:0,arms_to:0,margin_from:0,margin_to:0,profile:null});time=.35;}
 // Retreat is derived solely from native rest geometry and source fixed bounds, on the first original edge.
 let radius=0;const matrices=new Map<string,THREE.Matrix4>([['$root',new THREE.Matrix4()]]);
 for(const n of rig.nodes){const matrix=new THREE.Matrix4().compose(vector(n.position),new THREE.Quaternion(...n.quaternion),vector(n.scale)).premultiply(matrices.get(n.parent)!);matrices.set(n.name,matrix);if(n.mesh)for(let i=0;i<n.mesh.positions.length;i+=3){const p=new THREE.Vector3(n.mesh.positions[i],n.mesh.positions[i+1],n.mesh.positions[i+2]).applyMatrix4(matrix);radius=Math.max(radius,Math.hypot(p.x,p.z));}}
 // Separating-axis support for two native soles at adjacent turn headings, with2mm reserve.
 const turnIncrement=Math.PI/12,sourceHalf=Math.max(...rig.legs.map(l=>Math.abs(l.floor[0]))),soleX=Math.max(...rig.legs.flatMap(l=>l.vertices.map(p=>Math.abs(p[0]-l.sole[0])))),soleZ=Math.max(...rig.legs.flatMap(l=>l.vertices.map(p=>Math.abs(p[2]-l.sole[2])))),turnHalf=Math.max(sourceHalf,Math.ceil((soleX+soleZ*Math.tan(turnIncrement/2)+.002)*1000)/1000),expandedFootRadius=Math.max(...rig.legs.flatMap(l=>l.vertices.map(p=>Math.hypot(turnHalf+Math.abs(p[0]-l.sole[0]),p[2]-l.sole[2]))));
 const turnRadius=Math.max(radius,expandedFootRadius)+.002,clear=(point:XYZ)=>fixedBounds.every(b=>Math.hypot(Math.max(b.min[0]-point[0],0,point[0]-b.max[0]),Math.max(b.min[2]-point[2],0,point[2]-b.max[2]))>=turnRadius);
 let escapeDistance=0;
 function translate(group:{start:XYZ;end:XYZ;direction:XYZ;length:number},cap:number,kind:'walk_step'|'retreat_step'){
  const profile=velocityProfile(group.length,cap,time,group.start,group.direction),steps=Math.ceil(group.length/.22),advance=group.length/steps;
  for(let i=0;i<=steps;i++){const from=i===0?0:(i-.5)*advance,to=i===steps?group.length:(i+.5)*advance,target=i===steps?group.length:(i+1)*advance,toFeet=copyFeet(),at=tuple(vector(group.start).addScaledVector(vector(group.direction),target));toFeet[next]=nominal(next,at,yaw);step(kind,yaw,toFeet,profile.start_s+distanceTime(profile,from),profile.start_s+distanceTime(profile,to),profile);}
  centre=[...group.end];
 }
 const first=groups[0];
 if(first&&Math.abs(wrap(Math.atan2(first.direction[0],first.direction[2])-yaw))>1e-8&&!clear(centre)){
  const forward=new THREE.Vector3(0,0,1).applyAxisAngle(axisY,yaw);if(forward.dot(vector(first.direction))>-.999999)fail('UNSUPPORTED_PATH','Тесный исходный разворот требует допуска прямого шага назад по первому исходному ребру.');
  const available=vector(points[1]).distanceTo(vector(points[0]));
  for(let distance=.01;distance<available-.01;distance+=.01){const candidate=tuple(vector(first.start).addScaledVector(vector(first.direction),distance));if(clear(candidate)){escapeDistance=distance;break;}}
  if(!escapeDistance)fail('UNSUPPORTED_PATH','Первое исходное ребро не даёт места для полного native-разворота.');
  const end=tuple(vector(first.start).addScaledVector(vector(first.direction),escapeDistance));translate({start:[...first.start],end,direction:first.direction,length:escapeDistance},Math.min(speed,.35),'retreat_step');first.start=[...end];first.length-=escapeDistance;
 }
 for(const group of groups){const targetYaw=yaw+wrap(Math.atan2(group.direction[0],group.direction[2])-yaw),delta=targetYaw-yaw,count=Math.ceil(Math.abs(delta)/(Math.PI/12)-1e-10),firstYaw=yaw;
  if(count)for(let i=0;i<2;i++){const toFeet=copyFeet();toFeet[next]=nominal(next,centre,yaw,turnHalf);step('turn_step',yaw,toFeet,time,time+.32,null);}
  for(let i=0;i<count;i++){const to=firstYaw+delta*(i+1)/count,toFeet=copyFeet();toFeet[next]=nominal(next,centre,to,turnHalf);step('turn_step',to,toFeet,time,time+.32,null);}
  if(count){const toFeet=copyFeet();toFeet[next]=nominal(next,centre,yaw,turnHalf);step('turn_step',yaw,toFeet,time,time+.32,null);for(let i=0;i<2;i++){const toFeet=copyFeet();toFeet[next]=nominal(next,centre,yaw);step('turn_step',yaw,toFeet,time,time+.32,null);}}
  translate(group,speed,'walk_step');
 }
 if(groups.length){phases.push({kind:'settle',start_s:time,end_s:time+.35,swing:null,root:[...centre],yaw_from:yaw,yaw_to:yaw,feet_from:copyFeet(),feet_to:copyFeet(),arms_from:0,arms_to:0,margin_from:margin,margin_to:0,profile:null});time+=.35;}
 if(phases.length>4096)fail('UNSUPPORTED_PATH','Маршрут превышает ограничение фаз осмотра.');const endRoot=[...centre] as XYZ,endYaw=yaw;
 function sample(seconds:number):WorkerGaitPose{
  if(!Number.isFinite(seconds))fail('INVALID_TIME','Время должно быть конечным числом.');const at_s=Math.max(0,Math.min(time,seconds)),phase=phases.find(p=>at_s>=p.start_s&&at_s<p.end_s),rotations=Object.fromEntries(rig.nodes.filter(n=>n.name.startsWith('joint__')).map(n=>[n.name,[...n.quaternion] as Q]));
  if(at_s===0)return freeze({at_s,stage:phases.length?'prepare' as const:'route_end' as const,root_world:[...origin] as XYZ,yaw_rad:startYaw,speed_m_s:0,body_drop_m:0,feet:{L:{...nominal('L',origin,startYaw),stance:true,lift_m:0},R:{...nominal('R',origin,startYaw),stance:true,lift_m:0}},joint_rotations:rotations,maximum_IK_error_m:0,completed_jobs:0 as const});
  if(!phase)return freeze({at_s,stage:'route_end' as const,root_world:[...endRoot] as XYZ,yaw_rad:endYaw,speed_m_s:0,body_drop_m:0,feet:{L:{...nominal('L',endRoot,endYaw),stance:true,lift_m:0},R:{...nominal('R',endRoot,endYaw),stance:true,lift_m:0}},joint_rotations:rotations,maximum_IK_error_m:0,completed_jobs:0 as const});
  const u=(at_s-phase.start_s)/(phase.end_s-phase.start_s),ease=smooth(u),heading=phase.yaw_from+(phase.yaw_to-phase.yaw_from)*ease,position=vector(phase.root);let currentSpeed=0;
  if(phase.profile){const value=distanceAt(phase.profile,at_s);position.copy(vector(phase.profile.origin)).addScaledVector(vector(phase.profile.direction),value.distance);currentSpeed=value.speed;}
  const targets={} as WorkerGaitPose['feet'];for(const side of ['L','R'] as const){const from=phase.feet_from[side],to=phase.feet_to[side],swing=phase.swing===side,lift=swing?.018*Math.sin(Math.PI*u)**2:0;targets[side]={point:tuple(vector(from.point).lerp(vector(to.point),swing?ease:0).add(new THREE.Vector3(0,lift,0))),yaw_rad:from.yaw_rad+wrap(to.yaw_rad-from.yaw_rad)*(swing?ease:0),stance:!swing||u===0,lift_m:lift};}
  let drop=0;for(const leg of rig.legs){const foot=targets[leg.side],local=vector(foot.point).sub(position).applyAxisAngle(axisY,-heading),ankle=local.sub(vector(leg.sole).applyAxisAngle(axisY,foot.yaw_rad-heading)),dx=ankle.x-leg.hip[0],dz=ankle.z-leg.hip[2],length=vector(leg.a).length()+vector(leg.b).length();drop=Math.max(drop,leg.hip[1]-ankle.y-Math.sqrt(Math.max(0,length*length-dx*dx-dz*dz)));}
  drop=Math.max(0,drop)+phase.margin_from+(phase.margin_to-phase.margin_from)*ease;position.y-=drop;let maximumError=0;
  for(const side of ['L','R'] as const){const solution=solveLeg(rig,side,tuple(position),heading,targets[side]);Object.assign(rotations,solution.rotations);maximumError=Math.max(maximumError,solution.error);}
  return freeze({at_s,stage:phase.kind,root_world:tuple(position),yaw_rad:heading,speed_m_s:currentSpeed,body_drop_m:drop,feet:targets,joint_rotations:rotations,maximum_IK_error_m:maximumError,completed_jobs:0 as const});
 }
 const result=freeze({duration_s:time,phases,source_speed_m_s:speed,assumptions:{step_advance_max_m:.22 as const,retreat_speed_cap_m_s:.35 as const,escape_distance_m:escapeDistance,turn_clearance_radius_m:turnRadius,turn_stance_half_width_m:turnHalf,swing_lift_m:.018 as const,turn_increment_max_rad:Math.PI/12,turn_step_duration_s:.32 as const,acceleration_m_s2:.8 as const,stance_model:'Flat native sole held at one unchanged world position AND yaw throughout stance. Swing endpoints are explicit finite footfalls; no planted-foot root-yaw snap.'},sample});
 for(const phase of phases)for(let i=0;i<=8;i++)sample(phase.start_s+(phase.end_s-phase.start_s)*i/8);return result;
}
