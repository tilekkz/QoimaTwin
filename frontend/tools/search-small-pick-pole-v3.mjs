/** P03.5.3 analytical candidate search only; native geometry admission follows. */
import{readFile,writeFile,mkdir}from'node:fs/promises';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const b=await readFile('public/models/v3/worker-manual.glb');
const root=(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene.getObjectByName('worker_base_root');
const frame=root.getObjectByName('joint__torso'),upper=root.getObjectByName('joint__upper_arm_R'),fore=root.getObjectByName('joint__forearm_R'),hand=root.getObjectByName('joint__hand_R'),grip=root.getObjectByName('anchor_hand_grip_R');
root.updateWorldMatrix(true,true);
const elbow=upper.worldToLocal(fore.getWorldPosition(new T.Vector3())),wrist=fore.worldToLocal(hand.getWorldPosition(new T.Vector3())),axis=elbow.clone().normalize(),l1=elbow.length(),l2=wrist.length();
const sideProbe=process.env.QOIMA_PICK_SIDE==='1',gripperProbe=process.env.QOIMA_PICK_GRIPPER==='1',raised=process.env.QOIMA_PICK_RAISE==='1';
const fixedHandle=process.env.QOIMA_PICK_FIXED_HANDLE==='1';
const fineBodies=process.env.QOIMA_PICK_FINE_BODIES==='1';
const directory=fineBodies?(raised?'tool-fine-raised-reach':'tool-fine-pick-reach'):gripperProbe?(raised?(fixedHandle?'gripper-raised-fixed-reach-probe':'gripper-raised-reach-probe'):'gripper-reach-probe'):sideProbe?'side-pole-probe':'pole-probe';
const query=process.env.QOIMA_PICK_QUERY?JSON.parse(await readFile(process.env.QOIMA_PICK_QUERY,'utf8')):null;
if(query&&(!/^[a-z0-9-]+$/.test(query.directory)||!Array.isArray(query.bodies)||query.target.length!==3||!query.target.every(Number.isFinite)||!Number.isFinite(query.angle)))throw Error('Invalid bounded reach query');
const bodies=query?.bodies??JSON.parse(await readFile('../assets/v3/iterations/worker-base/P03.5.3/'+(fineBodies?'tool-fine-bodies/bodies.json':sideProbe?'side-pole-probe/bodies.json':'reach-probe/pick-clear-bodies.json'),'utf8')).clear;
const wrap=x=>Math.atan2(Math.sin(x),Math.cos(x)),result=[];
for(const[bi,body]of bodies.entries()){
 root.position.fromArray(body.root);root.rotation.set(0,Math.PI,0);frame.rotation.set(body.torso_x,0,0);root.updateWorldMatrix(true,true);
 const shoulder=frame.worldToLocal(upper.getWorldPosition(new T.Vector3()));
 const desired=frame.getWorldQuaternion(new T.Quaternion()).invert().multiply(new T.Quaternion().setFromEuler(new T.Euler(query?query.angle:gripperProbe?(raised&&!fixedHandle?Math.PI*3/4:Math.PI*5/8):Math.PI/2,0,0,'XYZ')));
 const contact=grip.position.clone(),target=query?.target??(gripperProbe?[.945,raised?1.4125:1.2725,.55]:[.945,1.14,.32]),goal=frame.worldToLocal(new T.Vector3(...target)),wGoal=goal.clone().sub(contact.clone().applyQuaternion(desired)),delta=wGoal.clone().sub(shoulder),d=delta.length(),candidates=[];
 if(d<l1+l2&&d>Math.abs(l1-l2)){
  const dir=delta.clone().normalize(),along=(d*d+l1*l1-l2*l2)/(2*d),height=Math.sqrt(l1*l1-along*along),centre=shoulder.clone().addScaledVector(dir,along);
  const v=new T.Vector3(0,1,0).cross(dir).normalize(),w=dir.clone().cross(v);
  for(let pole=0;pole<360;pole+=5){
   const E=centre.clone().addScaledVector(v,height*Math.cos(T.MathUtils.degToRad(pole))).addScaledVector(w,height*Math.sin(T.MathUtils.degToRad(pole))),u=E.clone().sub(shoulder).normalize();
   const align=new T.Quaternion().setFromUnitVectors(axis,u);
   for(let spin=-180;spin<180;spin+=5){
    const q1=new T.Quaternion().setFromAxisAngle(u,T.MathUtils.degToRad(spin)).multiply(align),a=new T.Euler().setFromQuaternion(q1,'XYZ');
    if(a.x< -3||a.x>.7||Math.abs(a.y)>.55||Math.abs(a.z)>.7)continue;
    const r=wGoal.clone().sub(E).applyQuaternion(q1.clone().invert()),A=axis.y*wrist.y+axis.z*wrist.z,B=-axis.y*wrist.z+axis.z*wrist.y,C=axis.x*wrist.x;
    const value=(r.dot(axis)-C)/Math.hypot(A,B);if(Math.abs(value)>1+1e-8)continue;
    for(const beta of[ Math.atan2(B,A)+Math.acos(T.MathUtils.clamp(value,-1,1)),Math.atan2(B,A)-Math.acos(T.MathUtils.clamp(value,-1,1))].map(wrap)){
     if(beta< -2.2||beta>.15)continue;
     const bend=new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),beta),p=wrist.clone().applyQuaternion(bend),pp=p.clone().addScaledVector(axis,-p.dot(axis)),rr=r.clone().addScaledVector(axis,-r.dot(axis));
     const twist=Math.atan2(axis.dot(pp.clone().cross(rr)),pp.dot(rr)),q2=new T.Quaternion().setFromAxisAngle(axis,twist).multiply(bend),q12=q1.clone().multiply(q2);
     const actual=shoulder.clone().add(elbow.clone().applyQuaternion(q1)).add(wrist.clone().applyQuaternion(q12)).add(contact.clone().applyQuaternion(desired));if(actual.distanceTo(goal)>1e-7)throw Error('Analytic IK mismatch');
     let best;
     for(let roll=-Math.PI;roll<=Math.PI+.001;roll+=Math.PI/90){
      const h=new T.Euler().setFromQuaternion(new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),roll).invert().multiply(q12.clone().invert()).multiply(desired),'XYZ'),angles=[h.x,h.y,h.z];
      if(angles.some((v,j)=>Math.abs(v)>[.6,.65,.4][j]-.0001))continue;
      const score=Math.max(...angles.map((v,j)=>Math.abs(v)/[.6,.65,.4][j]));if(!best||score<best.score)best={score,roll,angles};
     }
     if(!best)continue;
     const lift=Math.min(0,Math.max(-.8,a.x+2.2));
     candidates.push({root:body.root,body_index:bi,target,pose:{joint__torso:[body.torso_x,0,0],joint__head:body.head,joint__upper_arm_L:body.idle_left_upper,joint__shoulder_lift_R:[lift,0,0],joint__upper_arm_R:[a.x-lift,a.y,a.z],joint__forearm_R:[beta,0,0],joint__elbow_swivel_R:[twist,0,0],joint__palm_roll_R:[0,best.roll,0],joint__hand_R:best.angles},twist_axis_runtime:axis.toArray(),error:actual.distanceTo(goal),score:best.score,elbow_world:frame.localToWorld(E.clone()).toArray(),pole_deg:pole,spin_deg:spin});
    }
   }
  }
 }
 candidates.sort((a,b)=>b.elbow_world[1]-a.elbow_world[1]||a.score-b.score);
 result.push(...candidates);
}
result.sort((a,b)=>b.elbow_world[1]-a.elbow_world[1]||a.score-b.score);
const out='../assets/v3/iterations/worker-base/P03.5.3/'+(query?.directory??directory);await mkdir(out,{recursive:true});
await writeFile(out+'/candidates.json',JSON.stringify({source_kind:'visual_reach_candidates',engine_operation:false,target:query?.target??(gripperProbe?[.945,raised?1.4125:1.2725,.55]:[.945,1.14,.32]),scope:`${bodies.length}body-clear configurations; elbow pole5deg, shoulder spin5deg, palm roll2deg. Same existing rig/limits/primary packages/four fixed walls. ${gripperProbe?'Elevated external handle arm reach only; no tool geometry, contact or action acceptance in this probe.':'Direct two-package top grip; no action acceptance.'}`,candidates:result},null,query||fixedHandle||fineBodies?0:2)+'\n');
console.log(JSON.stringify({bodies:bodies.length,candidates:result.length,max_elbow_y:result[0]?.elbow_world[1],first:result[0]}));
