import assert from 'node:assert/strict';
import{readFile,writeFile,mkdir}from'node:fs/promises';
import{createHash}from'node:crypto';
import{pathToFileURL}from'node:url';
import path from'node:path';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const root=path.resolve('..'),work=path.join(root,'work/P04-qa'),out=path.join(root,'assets/v3/iterations/packer/P04.2');await mkdir(work,{recursive:true});await mkdir(out,{recursive:true});
const sha=b=>createHash('sha256').update(b).digest('hex'),sources={};
for(const [name,relative]of[['workerRoles','workerRoles'],['workerRolesFixture','workerRolesFixture'],['packer','motion/packer']]){
 const source=await readFile('src/adaptive-v3/'+relative+'.ts','utf8');sources[relative]=sha(source);let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/build/three.module.js')).href}'`).replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`).replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");await writeFile(path.join(work,name+'.mjs'),code);
}
const{createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(work,'workerRoles.mjs'))),{validatePackerTimeline,createPackerAction}=await import(pathToFileURL(path.join(work,'packer.mjs')));
const input=JSON.parse(await readFile('public/data/v3/packer-seam-end.json','utf8')),timeline=validatePackerTimeline(input);
for(const bad of [{...input,engine_operation:true},{...input,body_root_m:[.1,0,.5]},{...input,keys:input.keys.slice(1)}])assert.throws(()=>validatePackerTimeline(bad));
const tamper=structuredClone(input);tamper.keys[1].joints.joint__hand_R=[2,0,0];assert.throws(()=>validatePackerTimeline(tamper));
const parse=async f=>{const b=await readFile(f);return(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;};
const template=await parse('public/models/v3/worker-manual.glb'),fixture=await parse('public/models/v3/packer-workcell-fixture.glb'),cell=fixture.getObjectByName('packer_workcell_root');
const original=JSON.stringify(template.toJSON()),parcel=cell.getObjectByName('packer_existing_parcel'),parcelParent=parcel.parent,parcelTransform=parcel.matrix.toArray();
const actor=createWorkerInstance(template,'PK01','packer'),before={p:actor.root.position.toArray(),q:actor.root.quaternion.toArray()};const priorJoints={};actor.root.traverse(n=>{if(n.name.startsWith('joint__'))priorJoints[n.name]={p:n.position.toArray(),q:n.quaternion.toArray()};});const action=createPackerAction(cell,actor,timeline);
assert.throws(()=>createPackerAction(cell,actor,timeline));assert.throws(()=>action.apply(NaN));
const all=[];cell.traverse(n=>all.push(n));const matrices=()=>{cell.updateWorldMatrix(true,true);return all.map(n=>[n.uuid,...n.matrixWorld.elements]);};
const uuid=actor.root.uuid,packageUuid=parcel.uuid,native=[],limits=JSON.parse(await readFile('../assets/v3/specs/worker-base.dimensions.json','utf8')).joints;
let worstContact=0;
for(let i=0;i<=750;i++){
 const t=i/100,s=action.apply(t);assert.equal(s.actor_uuid,uuid);assert.equal(s.package_uuid,packageUuid);assert.equal(s.inventory_mutated,false);assert.equal(parcel.parent,parcelParent);assert.deepEqual(parcel.matrix.toArray(),parcelTransform);
 for(const c of s.contacts)if(c.active){worstContact=Math.max(worstContact,c.error_m);assert(c.error_m<2e-6);}
 actor.root.traverse(n=>{if(limits[n.name])n.rotation.toArray().slice(0,3).forEach((a,j)=>assert(a>=limits[n.name].limits_radians_xyz[j][0]-1e-6&&a<=limits[n.name].limits_radians_xyz[j][1]+1e-6,'Original rig limit '+n.name));});
 if(i%5===0){const joints={};actor.root.traverse(n=>{if(n.name.startsWith('joint__'))joints[n.name]={position:n.position.toArray(),quaternion:n.quaternion.toArray(),world:[...n.matrixWorld.elements]};});native.push({time:t,mode:s.mode,worker:{position:actor.root.position.toArray(),quaternion:actor.root.quaternion.toArray()},joints,contacts:s.contacts});}
}
for(let i=0;i<100;i++){const t=((i*317)%750)/100;action.apply(t);const a=matrices();action.apply(((i*173)%750)/100);action.apply(t);assert.deepEqual(matrices(),a);}
for(const mode of ['idle','blocked']){action.setMode(mode);const a=matrices(),s=action.apply(5);assert.equal(s.time,0);assert.equal(s.final_inspection_complete,false);assert.deepEqual(matrices(),a);const joints={};actor.root.traverse(n=>{if(n.name.startsWith('joint__'))joints[n.name]={position:n.position.toArray(),quaternion:n.quaternion.toArray()};});native.push({time:0,mode,worker:{position:actor.root.position.toArray(),quaternion:actor.root.quaternion.toArray()},joints,contacts:s.contacts});}
action.setMode('pack');assert.equal(action.apply(7.5).complete,true);assert.equal(action.apply(0).final_inspection_complete,false);
for(const yaw of [-.7,.3,1.2]){cell.position.set(2,0,-1);cell.rotation.y=yaw;const s=action.apply(3.2);assert(s.contacts.every(c=>c.error_m<2e-6));}cell.position.set(0,0,0);cell.quaternion.identity();
action.dispose();action.dispose();assert.throws(()=>action.apply(0));assert.deepEqual(actor.root.position.toArray(),before.p);assert.deepEqual(actor.root.quaternion.toArray(),before.q);assert.equal(JSON.stringify(template.toJSON()),original);
actor.root.traverse(n=>{if(priorJoints[n.name])assert.deepEqual({p:n.position.toArray(),q:n.quaternion.toArray()},priorJoints[n.name]);});cell.scale.setScalar(1.1);assert.throws(()=>createPackerAction(cell,actor,timeline));cell.scale.setScalar(1);const rebound=createPackerAction(cell,actor,timeline);rebound.dispose();
disposeWorkerInstance(actor);
const hashes={};for(const f of ['frontend/public/models/v3/worker-manual.glb','assets/v3/blender/worker-manual.blend','assets/v3/blender/packer-workcell-fixture.blend','frontend/public/models/v3/packer-workcell-fixture.glb','frontend/public/data/v3/packer-seam-end.json'])hashes[f]=sha(await readFile(path.join(root,f)));
await writeFile(path.join(out,'runtime-native-poses.json'),JSON.stringify({input_hashes:hashes,frames:native},null,2)+'\n');
const report={passed:true,runtime_samples:751,native_frames:native.length,arbitrary_all_node_seeks:100,maximum_contact_error_m:worstContact,actor_and_package_identity_stable:true,original_joint_limits_retained:true,source_template_unchanged:true,dispose_restores_actor_and_all_joints:true,unit_scale_rejection_is_atomic:true,rigid_world_transform_cases:3,idle_and_blocked_static_and_no_work:true,source_kind:'visual_fixture',engine_operation:false,source_hashes:sources,input_hashes:hashes};await writeFile(path.join(out,'actual-runtime-checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
