/** P05.4 deterministic native-rig arm solution; no model or historical evidence writes. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(frontend),sha=b=>createHash('sha256').update(b).digest('hex');
export async function solveReceiverArmPath(){
 const inputs={},cache=await mkdtemp(path.join(tmpdir(),'qoima-receiver-solve-')),three=pathToFileURL(path.join(frontend,'node_modules/three/build/three.module.js')).href;
 const source=async p=>{const b=await readFile(path.join(repo,p));inputs[p]=sha(b);return b;};
 let actor,disposeWorkerInstance;
 try{
  for(const [folder,name]of [['motion/','receiver'],['','workerRoles'],['','workerRolesFixture']]){
   let code=ts.transpileModule((await source('frontend/src/adaptive-v3/'+folder+name+'.ts')).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
   code=code.replaceAll("from 'three'",`from '${three}'`).replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.join(frontend,'node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`).replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");
   await writeFile(path.join(cache,name+'.mjs'),code);
  }
  const Roles=await import(pathToFileURL(path.join(cache,'workerRoles.mjs'))),{solveReceiverArmPose,receiverArmTarget}=await import(pathToFileURL(path.join(cache,'receiver.mjs')));disposeWorkerInstance=Roles.disposeWorkerInstance;
  const loader=new GLTFLoader(),load=async(id,name)=>{const b=await source('frontend/public/models/v3/'+id+'.glb');return (await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene.getObjectByName(name);};
  const template=await load('worker-manual','worker_base_root'),cell=await load('receiver-workcell-fixture','receiver_workcell_root');actor=Roles.createWorkerInstance(template,'R01','receiver');
  const root=actor.root,world=new T.Group();world.add(cell,root);
  const plan=JSON.parse(await source('assets/v3/specs/receiver-workcell.dimensions.json')),historical=JSON.parse(await source('assets/v3/iterations/receiver/P05.2/native-contact-search.json'));
  const contact={local_m:historical.admitted.candidate.contact_local,workcell_m:plan.confirmation_candidate_xyz_m,surface:'screen_footer',tangent_twist_rad:Math.PI/6};
  assert(contact.local_m.every((x,i)=>Math.abs(x-[.015,-.13,.03475][i])<2e-6));assert.deepEqual(contact.workcell_m,[-.7,1.175,-.343]);
  root.position.fromArray(plan.receiver_candidate_root);root.rotation.y=plan.receiver_candidate_yaw_rad;world.updateMatrixWorld(true);
  // The seed selects the low elbow branch; resulting joints are solved and limit-checked.
  const seed={joint__upper_arm_R:[-1.67,-.2,.54],joint__shoulder_lift_R:[0,0,0],joint__forearm_R:[-1,0,0],joint__elbow_swivel_R:[1.5,0,0],joint__palm_roll_R:[0,-5*Math.PI/16,0]};
  const restPose=Object.fromEntries([...Object.keys(seed),'joint__hand_R'].map(n=>{const node=root.getObjectByName(n),e=new T.Euler().setFromQuaternion(node.quaternion,'XYZ');return [n,node.userData.custom_axis_runtime?[0,0,0]:[e.x,e.y,e.z]];}));const A=structuredClone(restPose),B=structuredClone(restPose);A.joint__upper_arm_R=[0,0,.7];B.joint__upper_arm_R=[-.5,0,.7];B.joint__forearm_R=[-1,0,0];
  const poses={},checks=[];
  for(const [name,service]of [['approach',1.5],['lead',2.1],['contact',2.7]]){
   const target=receiverArmTarget(service),pose=solveReceiverArmPose(root,cell,seed,target,contact.local_m,'R',contact.tangent_twist_rad);poses[name]=pose;
   for(const [n,a]of Object.entries(pose)){const node=root.getObjectByName(n);if(node.userData.custom_axis_runtime)node.quaternion.setFromAxisAngle(new T.Vector3(...node.userData.custom_axis_runtime).normalize(),a[0]);else node.rotation.set(...a,'XYZ');}
   world.updateMatrixWorld(true);const hand=root.getObjectByName('joint__hand_R'),point=cell.worldToLocal(hand.localToWorld(new T.Vector3(...contact.local_m))),error=point.distanceTo(new T.Vector3(...target));assert(error<2e-6);
   checks.push({name,target_m:target,actual_contact_m:point.toArray(),error_m:error});
  }
  await source('frontend/tools/solve-receiver-v3.mjs');
  return {source_kind:'visual_fixture',engine_operation:false,accepted_action:false,body_root_m:plan.receiver_candidate_root,body_yaw_rad:plan.receiver_candidate_yaw_rad,contact,seed,poses,preparation_waypoints:[{at:.25,joints:A},{at:.55,joints:B}],checks,input_hashes:inputs,scope:'Three native-rig endpoint solutions within original limits; dense runtime and sampled native clearance are separate gates. Historical contact evidence supplies only the measured pad coordinate, not current arm admission.'};
 }finally{if(actor)disposeWorkerInstance(actor);await rm(cache,{recursive:true,force:true});}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(await solveReceiverArmPath(),null,2));
