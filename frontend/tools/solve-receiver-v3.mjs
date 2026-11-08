/** P05.2 bounded receiver reach; native admission required. */
import{readFile,writeFile,mkdir}from'node:fs/promises';
import{pathToFileURL}from'node:url';
import path from'node:path';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const b=await readFile('public/models/v3/worker-manual.glb');
const root=(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene.getObjectByName('worker_base_root');
const side='R';
const frame=root.getObjectByName('joint__torso'),upper=root.getObjectByName('joint__upper_arm_'+side),fore=root.getObjectByName('joint__forearm_'+side),hand=root.getObjectByName('joint__hand_'+side);
root.updateWorldMatrix(true,true);
const elbow=upper.worldToLocal(fore.getWorldPosition(new T.Vector3())),wrist=fore.worldToLocal(hand.getWorldPosition(new T.Vector3())),axis=elbow.clone().normalize(),l1=elbow.length(),l2=wrist.length();
const iface=JSON.parse(await readFile('../assets/v3/iterations/packer/P04.1/hand-interface.json','utf8')),contact=new T.Vector3(...iface.R.lower_pad_contact_local_m);
const workcellPlan=JSON.parse(await readFile('../assets/v3/specs/receiver-workcell.dimensions.json','utf8'));
contact.z-=.005; // Another actual point on the same measured lower-pad end face.
const target=[-.7,1.175,-.343];
const sha=await import('node:crypto');for(const [p,h]of Object.entries(iface.source_hashes))if(sha.createHash('sha256').update(await readFile('../'+p)).digest('hex')!==h)throw Error('Stale measured hand interface');
const wrap=x=>Math.atan2(Math.sin(x),Math.cos(x)),result=[];
const cache=path.resolve('../work/P05-candidates');await mkdir(cache,{recursive:true});let code=ts.transpileModule(await readFile('src/adaptive-v3/motion/receiver.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href}'`);await writeFile(path.join(cache,'receiver.mjs'),code);const{solveReceiverArmPose}=await import(pathToFileURL(path.join(cache,'receiver.mjs')));
for(const x of [-1,-.95,-1.05])for(const z of [-.803,-.75,-.85])for(const lean of [0,.15]){
 root.position.set(x,0,z);root.rotation.set(0,0,0);frame.rotation.set(lean,0,0);root.updateWorldMatrix(true,true);
 const shoulder=frame.worldToLocal(upper.getWorldPosition(new T.Vector3()));
 const desired=frame.getWorldQuaternion(new T.Quaternion()).invert().multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),Math.PI)).multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),Math.PI/2));
 const goal=frame.worldToLocal(new T.Vector3(...target)),wGoal=goal.clone().sub(contact.clone().applyQuaternion(desired)),delta=wGoal.clone().sub(shoulder),d=delta.length(),candidates=[];
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
 const raw_count=candidates.length; const valid=candidates.filter(c=>{try{for(const gap of [.03,.06,.09])solveReceiverArmPose(root,new T.Group(),c.pose,[target[0],target[1],target[2]-gap],c.contact_local,'R');return true;}catch{return false;}});candidates.splice(0,candidates.length,...valid);
 result.push({root:root.position.toArray(),root_euler:[0,0,0],lean,head:[0,.25,0],target,reach_distance_m:d,reach_bounds_m:[Math.abs(l1-l2),l1+l2],raw_count,contact_kind:'actual lower pad end on existing terminal footer',sides:{R:candidates}});
}
const previous=JSON.parse(await readFile('public/data/v3/packer-seam-end.json','utf8')),seed=Object.fromEntries(Object.entries(previous.keys[5].joints).filter(([n])=>n.endsWith('_R')));root.position.set(-1,0,-.803);root.rotation.set(0,0,0);frame.rotation.set(0,0,0);root.updateWorldMatrix(true,true);const pose=solveReceiverArmPose(root,new T.Group(),seed,target,contact.toArray());result.unshift({root:root.position.toArray(),root_euler:[0,0,0],lean:0,head:[.15,0,0],target,raw_count:1,scope:'Rigid180deg rotation of accepted P04 approach; witness5mm inside the same actual pad face, not moved geometry; new native admission required',sides:{R:[{pose,axis:axis.toArray(),contact_local:contact.toArray(),source:'P04-compatible-rigid-orientation'}]}});
const output='../assets/v3/iterations/receiver/P05.2';await mkdir(output,{recursive:true});await writeFile(output+'/contact-candidates.json',JSON.stringify({source_kind:'visual_pose_candidates',engine_operation:false,surface:'screen_footer',scope:'Bounded18service poses; endpoint and short Cartesian approach reach only, no native/contact/action acceptance',bodies:result})+'\n');console.log(JSON.stringify({bodies:result.length,candidates:result.reduce((n,r)=>n+r.sides.R.length,0),raw_candidates:result.reduce((n,r)=>n+r.raw_count,0),bodies_summary:result.map(r=>[r.root,r.lean,r.reach_distance_m,r.reach_bounds_m,r.raw_count,r.sides.R.length])}));
