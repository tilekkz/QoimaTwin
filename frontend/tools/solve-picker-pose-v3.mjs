import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const bytes=await readFile('public/models/v3/worker-base.glb');
const actor=(await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;
const pose=JSON.parse(await readFile('../assets/v3/specs/picker-push-pose.json','utf8'));
const limits=JSON.parse(await readFile('../assets/v3/specs/worker-base.dimensions.json','utf8')).joints;
const desired=new T.Quaternion().setFromEuler(new T.Euler(3*Math.PI/8,0,Math.PI,'XYZ'));
pose.jointEulerXYZ={};
pose.grip_centres_cart_m=[[-.195,.9775,-.4375],[.195,.9775,-.4375]];
pose.grip_centres_worker_m=[[-.195,.9775,.36],[.195,.9775,.36]];
for(const [side,sign] of [['L',1],['R',-1]]){
 const upper=actor.getObjectByName('joint__upper_arm_'+side),fore=actor.getObjectByName('joint__forearm_'+side),roll=actor.getObjectByName('joint__palm_roll_'+side),hand=actor.getObjectByName('joint__hand_'+side),grip=actor.getObjectByName('anchor_hand_grip_'+side);
 actor.updateWorldMatrix(true,true);
 const shoulder=actor.worldToLocal(upper.getWorldPosition(new T.Vector3()));
 const wrist=fore.worldToLocal(hand.getWorldPosition(new T.Vector3()));
 const goal=new T.Vector3(sign===1?-.195:.195,.9775,.36);
 const offset=grip.position.clone().applyQuaternion(desired);
 const v=[-.55,sign*.23,-.92],q1=new T.Quaternion(),q2=new T.Quaternion(),q12=new T.Quaternion();
 function point(a){q1.setFromEuler(new T.Euler(a[0],0,a[1],'XYZ'));q2.setFromAxisAngle(new T.Vector3(1,0,0),a[2]);q12.copy(q1).multiply(q2);return shoulder.clone().add(fore.position.clone().applyQuaternion(q1)).add(wrist.clone().applyQuaternion(q12)).add(offset);}
 for(let i=0;i<60;i++){
  const p=point(v),e=goal.clone().sub(p);if(e.length()<1e-11)break;
  const c=v.map((_,j)=>{const a=[...v];a[j]+=1e-5;return point(a).sub(p).multiplyScalar(1e5);});
  const jac=new T.Matrix3().set(c[0].x,c[1].x,c[2].x,c[0].y,c[1].y,c[2].y,c[0].z,c[1].z,c[2].z);
  assert(Math.abs(jac.determinant())>1e-12);e.applyMatrix3(jac.invert());for(let j=0;j<3;j++)v[j]+=T.MathUtils.clamp(e.getComponent(j),-.3,.3);
 }
 assert(point(v).distanceTo(goal)<1e-8,'Reach');
 const rollAngle=sign*Math.PI,rollQ=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),rollAngle);
 const h=new T.Euler().setFromQuaternion(rollQ.clone().invert().multiply(q12.clone().invert()).multiply(desired),'XYZ');
 const result={['joint__upper_arm_'+side]:[v[0],0,v[1]],['joint__forearm_'+side]:[v[2],0,0],['joint__palm_roll_'+side]:[0,rollAngle,0],['joint__hand_'+side]:[h.x,h.y,h.z]};
 for(const [name,a] of Object.entries(result)){if(limits[name])a.forEach((angle,j)=>assert(angle>=limits[name].limits_radians_xyz[j][0]&&angle<=limits[name].limits_radians_xyz[j][1],name+' '+a));pose.jointEulerXYZ[name]=a;}
 console.log(JSON.stringify({side,pose:result,palm_direction:new T.Vector3(0,0,1).applyQuaternion(desired).toArray(),anchor_offset:offset.toArray()}));
}
pose.meaning='FIX01.2 overhand cart grip: palm opening down, hand axis collinear with handle (-X), explicit axial pronation, original wrist/arm limits unchanged.';
pose.palm_open_direction_worker=[0,-Math.sin(3*Math.PI/8),Math.cos(3*Math.PI/8)];pose.hand_axis_worker=[-1,0,0];
for(const file of ['../assets/v3/specs/picker-push-pose.json','public/data/v3/picker-push-pose.json'])await writeFile(file,JSON.stringify(pose,null,2)+'\n');
