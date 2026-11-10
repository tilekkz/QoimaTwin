import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const root=path.resolve('..'),work=path.join(root,'work/P03-grip-qa');await mkdir(work,{recursive:true});
const sha=b=>createHash('sha256').update(b).digest('hex');const sourceHashes={};
for(const [name,relative] of [['workerRoles','workerRoles'],['workerRolesFixture','workerRolesFixture'],['grip','motion/grip']]){
 const source=await readFile('src/adaptive-v3/'+relative+'.ts','utf8');sourceHashes[relative]=sha(source);
 let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/build/three.module.js')).href}'`)
  .replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`)
  .replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");
 await writeFile(path.join(work,name+'.mjs'),code);
}
const {createWorkerInstance,disposeWorkerInstance,applyWorkerRole}=await import(pathToFileURL(path.join(work,'workerRoles.mjs')));
const {bindPickerGrip,validatePickerPushPose}=await import(pathToFileURL(path.join(work,'grip.mjs')));
const pose=validatePickerPushPose(JSON.parse(await readFile('public/data/v3/picker-push-pose.json','utf8')));
const native=JSON.parse(await readFile('../assets/v3/iterations/picking-cart/P03.3/actual-native-grip-checks.json','utf8'));
for(const [file,expected] of Object.entries(native.source_hashes))assert.equal(sha(await readFile(path.join(root,file))),expected);
const loader=new GLTFLoader();const parse=async file=>{const b=await readFile(file);return (await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;};
const worker=await parse('public/models/v3/worker-base.glb'),template=await parse('public/models/v3/picking-cart-tote-fixture.glb');
const source=worker.getObjectByName('worker_base_root'),sourceBefore=JSON.stringify(source.toJSON());
const scene=new T.Group(),registry=new T.Group();scene.add(registry);const a=createWorkerInstance(worker,'P01','picker'),b=createWorkerInstance(worker,'P02','picker'),other=createWorkerInstance(worker,'K01','packer');registry.add(a.root,b.root,other.root);
const cart=template.getObjectByName('picking-cart'),cartB=cart.clone(true);scene.add(template,cartB);
a.root.position.set(4,0,-2);a.root.rotation.y=.4;a.root.getObjectByName('joint__head').rotation.x=.1;
a.root.userData.assignment='queued';a.root.userData.cartAnchor='previous';
const prior={parent:a.root.parent,position:a.root.position.toArray(),quaternion:a.root.quaternion.toArray(),head:a.root.getObjectByName('joint__head').quaternion.toArray()};
assert.throws(()=>bindPickerGrip(cart,other,pose));assert.equal(other.root.parent,registry);
for(const bad of [{...pose,worker_scale:1.1},{...pose,grip_centres_cart_m:[[0,0,0],[0,0,0]]},{...pose,jointEulerXYZ:{...pose.jointEulerXYZ,joint__hand_L:[NaN,0,0]}}])assert.throws(()=>validatePickerPushPose(bad));
b.root.scale.setScalar(1.01);assert.throws(()=>bindPickerGrip(cartB,b,pose),/1:1/);b.root.scale.setScalar(1);
registry.scale.setScalar(2);assert.throws(()=>bindPickerGrip(cartB,b,pose),/1:1/);registry.scale.setScalar(1);
cartB.scale.setScalar(1.01);assert.throws(()=>bindPickerGrip(cartB,b,pose),/1:1/);cartB.scale.setScalar(1);
// A syntactically valid but physically wrong pose must roll back completely.
const badPose=structuredClone(pose);badPose.jointEulerXYZ.joint__forearm_L[0]=0;
assert.throws(()=>bindPickerGrip(cart,a,badPose),/Кисти/);assert.equal(a.root.parent,prior.parent);assert.deepEqual(a.root.position.toArray(),prior.position);assert.equal(a.root.userData.assignment,'queued');
const binding=bindPickerGrip(cart,a,pose);assert.equal(a.root.parent,cart);assert.equal(a.actorId,'P01');
assert.throws(()=>bindPickerGrip(cartB,a,pose));assert.throws(()=>bindPickerGrip(cart,b,pose));
const initial=binding.snapshot();assert(initial.hands.every(h=>h.error_m<2e-5&&h.axis_error<2e-5));
// The P02 closed extruded badge replaces old source ink; include its actual
// runtime vertices in this paired geometry check rather than ignoring it.
scene.updateMatrixWorld(true);const badge=a.root.getObjectByName('role_badge__P01'),badgeBounds=new T.Box3(),attribute=badge.geometry.getAttribute('position');
for(let i=0;i<attribute.count;i++)badgeBounds.expandByPoint(cart.worldToLocal(new T.Vector3().fromBufferAttribute(attribute,i).applyMatrix4(badge.matrixWorld)));
for(const id of ['picking-cart','order-tote']){
 const parts=JSON.parse(await readFile('../assets/v3/blender/'+id+'.stats.json','utf8')).components;
 for(const part of parts){const lo=[...part.bounds_runtime.min],hi=[...part.bounds_runtime.max];if(id==='order-tote'){lo[1]+=.62;hi[1]+=.62;}assert(badgeBounds.min.toArray().some((v,i)=>v>=hi[i]-2e-6||badgeBounds.max.toArray()[i]<=lo[i]+2e-6),'Role badge overlaps '+part.name);}
}
const canonical=JSON.stringify(initial);a.root.position.y=.1;binding.reset();assert.equal(JSON.stringify(binding.snapshot()),canonical);
let maximumError=0;
for(let i=0;i<100;i++){
 scene.position.set(Math.sin(i)*10,0,Math.cos(i)*7);scene.rotation.y=i*.023;cart.position.set(i*.003,0,Math.sin(i)*.2);cart.rotation.y=i*.014;
 const state=binding.snapshot();for(const h of state.hands){maximumError=Math.max(maximumError,h.error_m,h.axis_error);assert(h.error_m<2e-5&&h.axis_error<2e-5);}
 assert.equal(cart.children.filter(n=>n===a.root).length,1);
}
applyWorkerRole(a,'receiver');assert.throws(()=>binding.reset());applyWorkerRole(a,'picker');binding.reset();
binding.release();binding.release();assert.equal(a.root.parent,prior.parent);assert.deepEqual(a.root.position.toArray(),prior.position);assert.deepEqual(a.root.quaternion.toArray(),prior.quaternion);assert.deepEqual(a.root.getObjectByName('joint__head').quaternion.toArray(),prior.head);assert.equal(a.root.userData.assignment,'queued');assert.equal(a.root.userData.cartAnchor,'previous');assert(!a.disposed);assert.throws(()=>binding.reset());
const next=bindPickerGrip(cartB,a,pose);next.release();assert.equal(a.root.parent,registry);
assert.equal(JSON.stringify(source.toJSON()),sourceBefore);
let sharedDisposals=0,ownedDisposals=0;const shared=new Set(),owned=new Set();source.traverse(n=>{if(n.isMesh){shared.add(n.geometry);for(const m of Array.isArray(n.material)?n.material:[n.material])shared.add(m);}});
a.root.traverse(n=>{if(!n.isMesh)return;if(n.userData.roleBadge)owned.add(n.geometry);for(const m of Array.isArray(n.material)?n.material:[n.material])if(/^V3_Worker_Role/.test(m.name))owned.add(m);});
for(const r of shared)r.addEventListener('dispose',()=>sharedDisposals++);for(const r of owned)r.addEventListener('dispose',()=>ownedDisposals++);
disposeWorkerInstance(a);disposeWorkerInstance(a);disposeWorkerInstance(b);disposeWorkerInstance(other);assert.equal(sharedDisposals,0);assert.equal(ownedDisposals,3);
const report={task_id:'P03.3',source_hashes:sourceHashes,actual_contact_snapshot:initial,arbitrary_world_transforms:100,maximum_contact_or_axis_error:maximumError,new_role_badge_clear_of_cart_and_tote:true,existing_actor_and_cart_preserved:true,no_clone_or_registry_write:true,wrong_role_scale_and_pose_rejected:true,duplicate_and_occupied_rejected:true,physical_pose_failure_rolls_back:true,reset_exact:true,release_restores_parent_root_joint_pose_and_metadata:true,rebind:true,source_template_unchanged:true,owned_disposals:ownedDisposals,shared_disposals:sharedDisposals};
await writeFile('../assets/v3/iterations/picking-cart/P03.3/actual-runtime-grip-checks.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({task_id:'P03.3',passed:true,contact_errors:initial.hands.map(h=>h.error_m),world_transforms:100,maximum_error:maximumError,owned_disposals:ownedDisposals,shared_disposals:sharedDisposals}));
