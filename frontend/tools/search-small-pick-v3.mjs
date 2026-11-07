/** Candidate generation only. Native mesh clearance is the subsequent gate. */
import {readFile,writeFile} from 'node:fs/promises';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
const bytes=await readFile('public/models/v3/worker-manual.glb');
const actor=(await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;
const root=actor.getObjectByName('worker_base_root'),frame=root.getObjectByName('joint__torso');
const upper=root.getObjectByName('joint__upper_arm_R'),fore=root.getObjectByName('joint__forearm_R'),hand=root.getObjectByName('joint__hand_R'),grip=root.getObjectByName('anchor_hand_grip_R');
root.updateWorldMatrix(true,true);
const wrist=fore.worldToLocal(hand.getWorldPosition(new T.Vector3())),elbow=upper.worldToLocal(fore.getWorldPosition(new T.Vector3())),axis=elbow.clone().normalize();
const limits=JSON.parse(await readFile('../assets/v3/specs/worker-base.dimensions.json','utf8')).joints;
const bodies=JSON.parse(await readFile('../assets/v3/iterations/worker-base/P03.5.3/reach-probe/pick-clear-bodies.json','utf8')).clear;
const candidates=[],seen=new Set();
for(let bi=0;bi<bodies.length;bi++){
 const body=bodies[bi];root.position.fromArray(body.root);root.rotation.y=Math.PI;frame.rotation.x=body.torso_x;root.updateWorldMatrix(true,true);
 const shoulder=frame.worldToLocal(upper.getWorldPosition(new T.Vector3()));
 const desired=new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),-body.torso_x).multiply(new T.Quaternion().setFromEuler(new T.Euler(Math.PI/2,0,Math.PI,'XYZ'))),offset=grip.position.clone().applyQuaternion(desired);
 const target=[.945,1.14,.32],goal=frame.worldToLocal(new T.Vector3(...target));
 for(const yaw of [-.5,-.25,0,.25,.5])for(const twist of [-Math.PI,-3*Math.PI/4,-Math.PI/2,-Math.PI/4,0,Math.PI/4,Math.PI/2,3*Math.PI/4,Math.PI]){
  const qr=new T.Quaternion().setFromAxisAngle(axis,twist),q1=new T.Quaternion(),q2=new T.Quaternion(),q12=new T.Quaternion();
  function point(a){q1.setFromEuler(new T.Euler(a[0],yaw,a[1],'XYZ'));q2.copy(qr).multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),a[2]));q12.copy(q1).multiply(q2);return shoulder.clone().add(elbow.clone().applyQuaternion(q1)).add(wrist.clone().applyQuaternion(q12)).add(offset);}
  for(const seed of [[-.8,0,-.5],[-1.8,0,-1.1],[-2.6,0,-1.8]]){
   const v=[...seed];
   for(let i=0;i<60;i++){
    const p=point(v),e=goal.clone().sub(p);if(e.length()<1e-9)break;
    const c=v.map((_,j)=>{const a=[...v];a[j]+=1e-5;return point(a).sub(p).multiplyScalar(1e5);});
    const jac=new T.Matrix3().set(c[0].x,c[1].x,c[2].x,c[0].y,c[1].y,c[2].y,c[0].z,c[1].z,c[2].z);
    if(Math.abs(jac.determinant())<1e-12)break;e.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=T.MathUtils.clamp(e.getComponent(j),-.25,.25);
   }
   const error=point(v).distanceTo(goal);if(error>1e-7)continue;
   const lift=Math.min(0,Math.max(-.8,v[0]+2.2));
   const basePose={joint__torso:[body.torso_x,0,0],joint__head:body.head,joint__upper_arm_L:body.idle_left_upper,joint__shoulder_lift_R:[lift,0,0],joint__upper_arm_R:[v[0]-lift,yaw,v[1]],joint__forearm_R:[v[2],0,0]};
   if(Object.entries(basePose).some(([name,a])=>limits[name]&&a.some((angle,j)=>angle<limits[name].limits_radians_xyz[j][0]-1e-6||angle>limits[name].limits_radians_xyz[j][1]+1e-6)))continue;
   const signature=[bi,yaw,twist,...v.map(a=>Math.round(a*1e5))].join(',');if(seen.has(signature))continue;seen.add(signature);
   let best;
   for(let roll=-Math.PI;roll<=Math.PI+.001;roll+=Math.PI/180){
    const rq=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),roll),hq=new T.Euler().setFromQuaternion(rq.invert().multiply(q12.clone().invert()).multiply(desired),'XYZ');
    const values=[hq.x,hq.y,hq.z];if(values.some((angle,j)=>Math.abs(angle)>[.6,.65,.4][j]-1e-4))continue;
    const score=Math.max(...values.map((a,j)=>Math.abs(a)/[.6,.65,.4][j]));
    if(!best||score<best.score)best={score,roll,values};
   }
   if(!best)continue;
   candidates.push({target,body_index:bi,root:body.root,pose:{...basePose,joint__elbow_swivel_R:[twist,0,0],joint__palm_roll_R:[0,best.roll,0],joint__hand_R:best.values},twist_axis_runtime:axis.toArray(),error,score:best.score});
  }
 }
}
candidates.sort((a,b)=>a.score-b.score);
await writeFile('../assets/v3/iterations/worker-base/P03.5.3/reach-probe/pick-search-candidates.json',JSON.stringify([{label:'source',target:[.945,1.14,.32],candidates}],null,2)+'\n');
console.log(JSON.stringify({clear_bodies:bodies.length,candidates:candidates.length,examples:candidates.slice(0,2)}));
