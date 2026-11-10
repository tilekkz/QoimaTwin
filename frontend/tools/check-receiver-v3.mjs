import assert from'node:assert/strict';
import{readFile,writeFile,mkdir}from'node:fs/promises';
import{createHash}from'node:crypto';
import path from'node:path';
import{pathToFileURL}from'node:url';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const out='../assets/v3/iterations/receiver/P05.2',cache=path.resolve('../work/v3/receiver-check');await mkdir(out,{recursive:true});await mkdir(cache,{recursive:true});
const three=pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href;
for(const [dir,name]of[['motion/','receiver'],['','workerRoles'],['','workerRolesFixture']]){
 let code=ts.transpileModule(await readFile('src/adaptive-v3/'+dir+name+'.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${three}'`).replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.resolve('node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`).replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");await writeFile(path.join(cache,name+'.mjs'),code);
}
const{createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(cache,'workerRoles.mjs'))),{createReceiverAction,validateReceiverTimeline}=await import(pathToFileURL(path.join(cache,'receiver.mjs')));
const inputs={},hash=b=>createHash('sha256').update(b).digest('hex'),loader=new GLTFLoader();
async function load(name,root){const p='public/models/v3/'+name+'.glb',b=await readFile(p);inputs['frontend/'+p]=hash(b);return(await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene.getObjectByName(root);}
const cell=await load('receiver-workcell-fixture','receiver_workcell_root'),template=await load('worker-manual','worker_base_root'),actor=createWorkerInstance(template,'R01','receiver'),worker=actor.root,world=new T.Group();world.add(cell,worker);
world.updateMatrixWorld(true);const pallet=cell.getObjectByName('receiver_existing_pallet'),palletMatrix=pallet.matrixWorld.toArray(),palletUuid=pallet.uuid;assert.equal(pallet.userData.declared_gross_mass_kg,455);let units=0;cell.traverse(n=>{if(n.userData.role==='HU_content_unit_frame')units++;});assert.equal(units,24);
const file='public/data/v3/receiver-v3.json',timeline=JSON.parse(await readFile(file,'utf8'));validateReceiverTimeline(timeline);
for(const p of[file,'src/adaptive-v3/motion/receiver.ts','src/adaptive-v3/workerRoles.ts','src/adaptive-v3/workerRolesFixture.ts','tools/check-receiver-v3.mjs'])inputs['frontend/'+p]=hash(await readFile(p));
for(const p of['assets/v3/blender/receiver-workcell-fixture.blend','assets/v3/blender/worker-manual.blend','assets/v3/iterations/receiver/P05.1/native-workcell.json'])inputs[p]=hash(await readFile('../'+p));
const fingerprint=()=>{world.updateMatrixWorld(true);const nodes=[];world.traverse(n=>nodes.push([n.uuid,n.parent?.uuid,n.visible,...n.position.toArray(),...n.quaternion.toArray(),JSON.stringify(n.userData)]));return hash(JSON.stringify(nodes.sort((a,b)=>a[0].localeCompare(b[0]))));};
const original=fingerprint();for(const mutate of[d=>d.engine_operation=true,d=>d.HU_ref='other',d=>d.contact.workcell_m[0]=0,d=>d.keys[0].joints.joint__head=[1,0,0],d=>d.duration_s=1]){const bad=structuredClone(timeline);mutate(bad);assert.throws(()=>createReceiverAction(cell,actor,bad));assert.equal(fingerprint(),original);}
const action=createReceiverAction(cell,actor,timeline);assert.throws(()=>createReceiverAction(cell,actor,timeline));
const frames=[],states=new Map(),spec=JSON.parse(await readFile('../assets/v3/specs/worker-base.dimensions.json','utf8'));let maxStep=0,witness,previous,runtimeFrames=0;
for(const mode of['receive','scan','idle','blocked']){
 action.setMode(mode);const count=mode==='receive'||mode==='scan'?Math.round(action.timeline.duration_s*100):0;previous=null;
 for(let i=0;i<=count;i++){
  const time=i/100,s=action.apply(time),joints={};runtimeFrames++;
  assert.equal(s.actor_uuid,worker.uuid);assert.equal(s.HU_ref,timeline.HU_ref);assert.equal(s.engine_operation,false);assert.equal(s.inventory_mutated,false);
  assert.equal(s.HU_uuid,palletUuid);assert.deepEqual(pallet.matrixWorld.toArray(),palletMatrix);assert.equal(pallet.userData.declared_gross_mass_kg,455);
  if(s.contact.active)assert(s.contact.error_m<2e-6);
  if(mode==='idle'||mode==='blocked')for(const p of s.palms_worker_local)assert(p.side==='R'?p.direction[0]<-.98:p.direction[0]>.98);
  worker.traverse(n=>{if(n.name.startsWith('joint__')){joints[n.name]={position:n.position.toArray(),quaternion:n.quaternion.toArray()};const lim=spec.joints[n.name]?.limits_radians_xyz;if(lim){const e=new T.Euler().setFromQuaternion(n.quaternion,'XYZ');assert([e.x,e.y,e.z].every((x,j)=>x>=lim[j][0]-1e-7&&x<=lim[j][1]+1e-7),mode+'/'+time+'/'+n.name);}}});
  if(previous)for(const[name,p]of Object.entries(joints)){const step=new T.Quaternion().fromArray(p.quaternion).angleTo(new T.Quaternion().fromArray(previous[name].quaternion));if(step>maxStep){maxStep=step;witness={mode,time,name};}}previous=joints;
  states.set(mode+'/'+i,fingerprint());if(i%5===0)frames.push({mode,time,state:s,joints});
 }
}
assert(maxStep<.08,JSON.stringify({maxStep,witness}));
for(let i=0;i<100;i++){const mode=i%2?'scan':'receive',index=(i*137)%(mode==='scan'?251:Math.round(timeline.duration_s*100)+1);action.setMode(mode);action.apply(index/100);assert.equal(fingerprint(),states.get(mode+'/'+index));}
for(const yaw of[-.7,.3,1.2]){cell.position.set(2,0,-1);cell.rotation.set(0,yaw,0);action.setMode('receive');for(const t of[0,3.4,7,8,9,12,16.6]){const s=action.apply(t);if(s.contact.active)assert(s.contact.error_m<2e-6);}}
cell.position.set(0,0,0);cell.quaternion.identity();action.setMode('receive');action.apply(0);const before=fingerprint();for(const t of[NaN,Infinity,-Infinity]){assert.throws(()=>action.apply(t));assert.equal(fingerprint(),before);}assert.throws(()=>action.setMode('bad'));assert.equal(fingerprint(),before);
action.setMode('idle');assert.equal(action.apply(7).time,0);action.setMode('blocked');assert.equal(action.apply(7).received,false);
action.dispose();assert.equal(fingerprint(),original);assert.throws(()=>action.apply(0));const rebound=createReceiverAction(cell,actor,timeline);rebound.dispose();assert.equal(fingerprint(),original);
const lifecycle=createReceiverAction(cell,actor,timeline);disposeWorkerInstance(actor);lifecycle.dispose();assert.equal(worker.parent,null);assert(!cell.children.some(n=>n.name==='receiver_visual_scan_cue'));
const checks={runtime_frames:runtimeFrames,native_frames:frames.length,arbitrary_seeks:100,maximum_joint_step_per_10ms_rad:maxStep,step_witness:witness,same_actor_and_HU:true,no_inventory_mutation:true,original_body_and_HU_unchanged:true,inward_idle_and_blocked_palms:true,exclusive_binding:true,invalid_inputs_no_mutation:true,dispose_and_rebind_restore:true,disposed_actor_not_resurrected:true,rigid_world_transforms:3};
await writeFile(out+'/runtime-native-poses.json',JSON.stringify({source_kind:'visual_fixture',engine_operation:false,accepted_action:false,input_hashes:inputs,body_root_m:timeline.body_root_m,body_yaw_rad:timeline.body_yaw_rad,contact:timeline.contact,checks,frames,scope:'Runtime kinematic candidate only; current native path and browser acceptance separate.'})+'\n');console.log('RECEIVER_RUNTIME_CANDIDATE',JSON.stringify(checks));
