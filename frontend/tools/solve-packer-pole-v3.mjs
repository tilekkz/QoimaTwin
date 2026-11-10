/** Two-bone elbow-pole candidates. Every result still needs native admission. */
import{readFile,writeFile,mkdir}from'node:fs/promises';
import{pathToFileURL}from'node:url';
import path from'node:path';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const b=await readFile('public/models/v3/worker-manual.glb');
const root=(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene.getObjectByName('worker_base_root');
const side=process.env.QOIMA_PACKER_ARM==='L'?'L':'R';
const frame=root.getObjectByName('joint__torso'),upper=root.getObjectByName('joint__upper_arm_'+side),fore=root.getObjectByName('joint__forearm_'+side),hand=root.getObjectByName('joint__hand_'+side);
root.updateWorldMatrix(true,true);
const elbow=upper.worldToLocal(fore.getWorldPosition(new T.Vector3())),wrist=fore.worldToLocal(hand.getWorldPosition(new T.Vector3())),axis=elbow.clone().normalize(),l1=elbow.length(),l2=wrist.length();
const iface=JSON.parse(await readFile('../assets/v3/iterations/packer/P04.1/hand-interface.json','utf8')),top=process.env.QOIMA_PACKER_PROBE_KIND==='top',contact=new T.Vector3(...iface[side][top?'thumb_face_contact_local_m':'lower_pad_contact_local_m']);
const wrap=x=>Math.atan2(Math.sin(x),Math.cos(x)),result=[];
const cache=path.resolve('../work/P04-candidates');await mkdir(cache,{recursive:true});let code=ts.transpileModule(await readFile('src/adaptive-v3/motion/packer.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href}'`);await writeFile(path.join(cache,'packer.mjs'),code);const{solvePackerArmPose}=await import(pathToFileURL(path.join(cache,'packer.mjs')));
for(const x of side==='L'?[.3]:[.1,.2,.3])for(const z of side==='L'?[.7]:[.7,.75])for(const ankle of top?[.15,.2,.25]:[0])for(const lean of side==='L'?[0]:[0,.15,.3]){
 root.position.set(x,0,z);root.quaternion.copy(new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),Math.PI).multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),ankle)));
 for(const side of ['L','R'])root.getObjectByName('joint__foot_'+side).rotation.set(-ankle,0,0);
 frame.rotation.set(lean,0,0);root.updateWorldMatrix(true,true);
 const floor=root.getObjectByName('anchor_foot_floor_R').getWorldPosition(new T.Vector3());root.position.y-=floor.y;root.position.z+=z-floor.z;root.updateWorldMatrix(true,true);
 const shoulder=frame.worldToLocal(upper.getWorldPosition(new T.Vector3()));
 const desired=frame.getWorldQuaternion(new T.Quaternion()).invert().multiply(new T.Quaternion().setFromEuler(new T.Euler(Math.PI/2,0,0,'XYZ')));
 const target=side==='L'?[.65,.89,.45]:top?[0,1.2,.2]:[0,1.17,.24],goal=frame.worldToLocal(new T.Vector3(...target)),wGoal=goal.clone().sub(contact.clone().applyQuaternion(desired)),delta=wGoal.clone().sub(shoulder),d=delta.length(),candidates=[];
 if(d<l1+l2&&d>Math.abs(l1-l2)){
  const dir=delta.clone().normalize(),along=(d*d+l1*l1-l2*l2)/(2*d),height=Math.sqrt(l1*l1-along*along),centre=shoulder.clone().addScaledVector(dir,along);
  const v=new T.Vector3(0,1,0).cross(dir).normalize(),w=dir.clone().cross(v);
  for(let pole=0;pole<360;pole+=10){
   const E=centre.clone().addScaledVector(v,height*Math.cos(T.MathUtils.degToRad(pole))).addScaledVector(w,height*Math.sin(T.MathUtils.degToRad(pole))),u=E.clone().sub(shoulder).normalize();
   const align=new T.Quaternion().setFromUnitVectors(axis,u);
   for(let spin=-180;spin<180;spin+=10){
    const q1=new T.Quaternion().setFromAxisAngle(u,T.MathUtils.degToRad(spin)).multiply(align),angles=new T.Euler().setFromQuaternion(q1,'XYZ'),a=[angles.x,angles.y,angles.z];
    if(a[0]<-3||a[0]>.7||Math.abs(a[1])>.55||Math.abs(a[2])>.7)continue;
    const r=wGoal.clone().sub(E).applyQuaternion(q1.clone().invert()),A=axis.y*wrist.y+axis.z*wrist.z,B=-axis.y*wrist.z+axis.z*wrist.y,C=axis.x*wrist.x;
    const value=(r.dot(axis)-C)/Math.hypot(A,B);if(Math.abs(value)>1+1e-8)continue;
    for(const beta of [Math.atan2(B,A)+Math.acos(T.MathUtils.clamp(value,-1,1)),Math.atan2(B,A)-Math.acos(T.MathUtils.clamp(value,-1,1))].map(wrap)){
     if(beta< -2.2||beta>.15)continue;
     const bend=new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),beta),p=wrist.clone().applyQuaternion(bend),pp=p.clone().addScaledVector(axis,-p.dot(axis)),rr=r.clone().addScaledVector(axis,-r.dot(axis));
     const twist=Math.atan2(axis.dot(pp.clone().cross(rr)),pp.dot(rr)),q2=new T.Quaternion().setFromAxisAngle(axis,twist).multiply(bend),q12=q1.clone().multiply(q2);
     const actual=shoulder.clone().add(elbow.clone().applyQuaternion(q1)).add(wrist.clone().applyQuaternion(q12)).add(contact.clone().applyQuaternion(desired));if(actual.distanceTo(goal)>1e-7)throw Error('Analytic IK position mismatch');
     let best;
     for(let roll=-Math.PI;roll<=Math.PI+.001;roll+=Math.PI/90){
      const h=new T.Euler().setFromQuaternion(new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),roll).invert().multiply(q12.clone().invert()).multiply(desired),'XYZ');
      const angles=[h.x,h.y,h.z];if(angles.some((v,j)=>Math.abs(v)>[.6,.65,.4][j]-.0001))continue;
      const score=Math.max(...angles.map((v,j)=>Math.abs(v)/[.6,.65,.4][j]));if(!best||score<best.score)best={score,roll,angles};
     }
     if(!best)continue;
     const lift=Math.min(0,Math.max(-.8,a[0]+2.2));
     candidates.push({pose:{['joint__shoulder_lift_'+side]:[lift,0,0],['joint__upper_arm_'+side]:[a[0]-lift,a[1],a[2]],['joint__forearm_'+side]:[beta,0,0],['joint__elbow_swivel_'+side]:[twist,0,0],['joint__palm_roll_'+side]:[0,best.roll,0],['joint__hand_'+side]:best.angles},twist,solution:[a[0],a[2],beta],yaw:a[1],axis:axis.toArray(),error:actual.distanceTo(goal),score:best.score,contact_local:contact.toArray(),elbow_frame:E.toArray(),pole_deg:pole,spin_deg:spin});
    }
   }
  }
 }
 candidates.sort((a,b)=>b.elbow_frame[1]-a.elbow_frame[1]||a.score-b.score);
 if(!top){
  const valid=candidates.filter(c=>{try{solvePackerArmPose(root,new T.Group(),c.pose,side==='L'?[.65,.89,.52]:[0,1.17,.28],c.contact_local,side);if(side==='R')solvePackerArmPose(root,new T.Group(),c.pose,[-.08,1.17,.38],c.contact_local,side);return true;}catch{return false;}});
  candidates.splice(0,candidates.length,...valid);
 }
 result.push({root:root.position.toArray(),root_euler:[-ankle,Math.PI,0],ankle,foot_pose:[-ankle,0,0],lean,head:[.15,0,0],idle_left_upper:[.7,0,0],target,contact_kind:side==='L'?'actual lower pad end on table front edge':top?'actual thumb face on top seam':'actual lower pad end on front tape tail',sides:{[side]:candidates}});
}
const targetFile=top?'top-seam-probe/contact-candidates.json':side==='L'?'table-L-candidates.json':'front-tail-R-candidates.json';
await writeFile('../assets/v3/iterations/packer/P04.1/'+targetFile,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({bodies:result.length,candidates:result.reduce((n,r)=>n+r.sides[side].length,0),bounds:'elbow pole 10deg, shoulder spin10deg; original joint deltas and added shoulder/swivel ranges; no wrist extension'}));
