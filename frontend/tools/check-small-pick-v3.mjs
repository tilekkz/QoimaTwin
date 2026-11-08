import assert from'node:assert/strict';
import{readFile,writeFile,mkdir}from'node:fs/promises';
import path from'node:path';
import{pathToFileURL}from'node:url';
import{createHash}from'node:crypto';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const output='../assets/v3/iterations/worker-base/P03.5.3.3',cache=path.resolve('../work/v3/small-pick-check');await mkdir(output,{recursive:true});await mkdir(cache,{recursive:true});
const three=pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href;
for(const name of ['smallGripper','smallPick']){
 let code=ts.transpileModule(await readFile('src/adaptive-v3/motion/'+name+'.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${three}'`).replaceAll("from './smallGripper'","from './smallGripper.mjs'");await writeFile(path.join(cache,name+'.mjs'),code);
}
for(const name of ['workerRoles','workerRolesFixture']){
 let code=ts.transpileModule(await readFile('src/adaptive-v3/'+name+'.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${three}'`).replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.resolve('node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`).replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");await writeFile(path.join(cache,name+'.mjs'),code);
}
const{createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(cache,'workerRoles.mjs')));
const{createSmallPickMotion,validateSmallPickTimeline}=await import(pathToFileURL(path.join(cache,'smallPick.mjs')));
const inputs={},loader=new GLTFLoader();
async function load(name,root){const p='public/models/v3/'+name+'.glb',bytes=await readFile(p);inputs['frontend/'+p]=createHash('sha256').update(bytes).digest('hex');const scene=(await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;return scene.getObjectByName(root);}
const cell=await load('picker-pick-source-fixture','picker_pick_source_fixture_root'),template=await load('worker-small-pick','worker_base_root'),tool=await load('small-package-gripper','small-package-gripper');
assert(cell&&template&&tool);const actor=createWorkerInstance(template,'P01','picker'),worker=actor.root;const world=new T.Group();world.add(cell,worker,tool);world.updateMatrixWorld(true);
const file='public/models/v3/small-pick-v3.json',bytes=await readFile(file);inputs['frontend/'+file]=createHash('sha256').update(bytes).digest('hex');for(const name of ['smallPick','smallGripper'])inputs['frontend/src/adaptive-v3/motion/'+name+'.ts']=createHash('sha256').update(await readFile('src/adaptive-v3/motion/'+name+'.ts')).digest('hex');const timeline=validateSmallPickTimeline(JSON.parse(bytes));
const buildGuides=process.env.QOIMA_BUILD_PICK_GUIDES==='1';
const armKeys=['joint__shoulder_lift_R','joint__upper_arm_R','joint__forearm_R','joint__elbow_swivel_R','joint__palm_roll_R','joint__hand_R'];
const seedArm=seed=>Object.fromEntries(armKeys.map(k=>[k,seed[k]]));
if(buildGuides)delete timeline.arm_guides;
for(const name of ['workerRoles','workerRolesFixture'])inputs['frontend/src/adaptive-v3/'+name+'.ts']=createHash('sha256').update(await readFile('src/adaptive-v3/'+name+'.ts')).digest('hex');
for(const name of ['worker-small-pick','small-package-gripper','picker-pick-source-fixture'])inputs['assets/v3/blender/'+name+'.blend']=createHash('sha256').update(await readFile('../assets/v3/blender/'+name+'.blend')).digest('hex');
inputs['frontend/tools/check-small-pick-v3.mjs']=createHash('sha256').update(await readFile('tools/check-small-pick-v3.mjs')).digest('hex');
const fingerprint=()=>{world.updateMatrixWorld(true);const nodes=[];world.traverse(n=>nodes.push([n.uuid,n.parent?.uuid,...n.position.toArray(),...n.quaternion.toArray(),...(n.morphTargetInfluences??[]),JSON.stringify(n.userData)]));return createHash('sha256').update(JSON.stringify(nodes.sort((a,b)=>a[0].localeCompare(b[0])))).digest('hex');};
const original=fingerprint();for(const mutation of [d=>d.engine_operation=true,d=>d.duration_s=1,d=>d.seeds.low={},d=>d.keys[0].t=.1]){const bad=structuredClone(timeline);mutation(bad);assert.throws(()=>validateSmallPickTimeline(bad));assert.equal(fingerprint(),original);}
const motion=createSmallPickMotion(cell,actor,tool,timeline);assert.throws(()=>createSmallPickMotion(cell,actor,tool,timeline));
let previousJoints=null,maximumAngularStep=0,angularStepWitness=null;const builtGuides=[],frames=[],states=new Map(),spec=JSON.parse(await readFile('../assets/v3/specs/worker-base.dimensions.json','utf8'));
for(let i=0;i<=3600;i++){
 const time=i/100;let state;try{state=motion.apply(time);}catch(e){console.log('SMALL_PICK_CANDIDATE_REJECTED',time,e.message);throw e;}
 assert(state.grip_error_m<2e-6);assert.equal(state.package_uuids.length,2);
 const joints={};worker.traverse(n=>{if(n.name.startsWith('joint__')){joints[n.name]={position:n.position.toArray(),quaternion:n.quaternion.toArray()};const lim=spec.joints[n.name]?.limits_radians_xyz;if(lim){const e=new T.Euler().setFromQuaternion(n.quaternion,'XYZ');assert([e.x,e.y,e.z].every((v,j)=>v>=lim[j][0]-1e-7&&v<=lim[j][1]+1e-7),`${time}/${n.name}: ${e.x},${e.y},${e.z}`);}}});
 const units=[17,23].map(id=>{const n=cell.getObjectByName('primary_unit__'+id);return {id:n.name,parent:n.parent.name,world_position:n.getWorldPosition(new T.Vector3()).toArray(),world_quaternion:n.getWorldQuaternion(new T.Quaternion()).toArray()};});
 if(previousJoints)for(const [name,p]of Object.entries(joints)){const a=new T.Quaternion().fromArray(previousJoints[name].quaternion),b=new T.Quaternion().fromArray(p.quaternion),angle=a.angleTo(b);if(angle>maximumAngularStep){maximumAngularStep=angle;angularStepWitness={time,name};}}previousJoints=joints;
 if(i%10===0||(time>=31.6&&i%2===0)||(time>33&&time<33.4))frames.push({time,state,joints,units});states.set(i,fingerprint());
 if(buildGuides&&i>=3160){if(i%5===0)builtGuides.push({t:time,pose:state.arm_pose});if(i<3600){const next=timeline.arm_waypoints?.find(k=>k.t>time+1e-9)??{t:36,pose:time>=34?state.arm_pose:seedArm(timeline.seeds.deposit)};motion.timeline.arm_guides=[{t:time,pose:state.arm_pose},next];}}
}
if(buildGuides){motion.dispose();assert.equal(fingerprint(),original);disposeWorkerInstance(actor);timeline.arm_guides=builtGuides;await writeFile(file,JSON.stringify(timeline)+'\n');console.log('SMALL_PICK_GUIDES_BUILT',JSON.stringify({guides:builtGuides.length,maximumAngularStep,angularStepWitness}));process.exit(0);}
assert(maximumAngularStep<.08,JSON.stringify({maximumAngularStep,angularStepWitness}));
for(let i=0;i<100;i++){const index=(i*137)%3601;motion.apply(index/100);assert.equal(fingerprint(),states.get(index));}
for(const yaw of [-.7,.3,1.2]){cell.position.set(2,0,-1);cell.rotation.set(0,yaw,0);for(const time of [0,3.5,6.4,14.4,20,33.2,36])assert(motion.apply(time).grip_error_m<2e-6);}
cell.position.set(0,0,0);cell.quaternion.identity();motion.apply(0);
const beforeInvalid=fingerprint();for(const t of [NaN,Infinity,-Infinity]){assert.throws(()=>motion.apply(t));assert.equal(fingerprint(),beforeInvalid);}
motion.dispose();assert.equal(fingerprint(),original);assert.throws(()=>motion.apply(0));const rebound=createSmallPickMotion(cell,actor,tool,timeline);rebound.dispose();assert.equal(fingerprint(),original);disposeWorkerInstance(actor);assert(actor.disposed);assert.throws(()=>createSmallPickMotion(cell,actor,tool,timeline));
const report={source_kind:'visual_fixture',engine_operation:false,accepted_action:false,input_hashes:inputs,frames,checks:{runtime_frames:3601,maximum_joint_angle_change_per_10ms_rad:maximumAngularStep,maximum_angle_step_witness:angularStepWitness,native_frames_exported:frames.length,arbitrary_seeks:100,invalid_time_rejected:3,exclusive_binding:true,disposal_restores_hierarchy_and_transforms:true,source_package_objects_conserved:true},scope:'Runtime kinematic candidate only, actual native path clearance/contact/support gate pending. Actual existing P01 role factory and additive worker template; browser acceptance is separate.'};
await writeFile(output+'/runtime-native-poses.json',JSON.stringify(report)+'\n');console.log('SMALL_PICK_RUNTIME_CANDIDATE',JSON.stringify(report.checks));
