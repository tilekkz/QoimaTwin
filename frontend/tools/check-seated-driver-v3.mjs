import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const root=path.resolve('..'),work=path.join(root,'work/P07-driver-qa');await mkdir(work,{recursive:true});
const sha=b=>createHash('sha256').update(b).digest('hex');const sourceHashes={};
for(const name of ['workerRoles','workerRolesFixture','seatedDriver']){
 const file=path.join(root,'frontend/src/adaptive-v3/'+name+'.ts'),source=await readFile(file,'utf8');sourceHashes[name]=sha(source);
 let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/build/three.module.js')).href}'`)
  .replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`)
  .replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");
 await writeFile(path.join(work,name+'.mjs'),code);
}
const {createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(work,'workerRoles.mjs')));
const {bindSeatedDriver,validateSeatedDriverPose}=await import(pathToFileURL(path.join(work,'seatedDriver.mjs')));
const pose=validateSeatedDriverPose(JSON.parse(await readFile('public/data/v3/seated-driver-pose.json','utf8')));
const native=JSON.parse(await readFile('../assets/v3/iterations/worker-base/P07/actual-native-driver-checks.json','utf8'));
for(const [file,expected] of Object.entries(native.source_hashes))assert.equal(sha(await readFile(path.join(root,file))),expected);
const workerBytes=await readFile('public/models/v3/worker-base.glb');assert.equal(sha(workerBytes),pose.worker_glb_sha256);
const loader=new GLTFLoader();const parse=bytes=>loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
const worker=(await parse(workerBytes)).scene,template=(await parse(await readFile('public/models/v3/forklift.glb'))).scene;
const sourceRoot=worker.getObjectByName('worker_base_root'),sourceBefore=JSON.stringify(sourceRoot.toJSON());
let sharedDisposals=0;const sharedGeo=new Set(),sharedMat=new Set();
sourceRoot.traverse(n=>{if(n.isMesh){sharedGeo.add(n.geometry);for(const mat of Array.isArray(n.material)?n.material:[n.material])sharedMat.add(mat);}});
for(const resource of [...sharedGeo,...sharedMat])resource.addEventListener('dispose',()=>sharedDisposals++);
const registry=new T.Group(),a=createWorkerInstance(worker,'F01','forklift_driver'),b=createWorkerInstance(worker,'F02','forklift_driver'),packer=createWorkerInstance(worker,'K01','packer');
registry.add(a.root,b.root,packer.root);a.root.position.set(5,0,2);
const original={parent:a.root.parent,position:a.root.position.toArray(),quaternion:a.root.quaternion.toArray()};
const carA=template.clone(true),carB=template.clone(true),vehicle=carA.getObjectByName('forklift_root'),vehicleB=carB.getObjectByName('forklift_root');
assert.throws(()=>bindSeatedDriver(vehicle,packer,pose));assert.equal(packer.root.parent,registry);
b.root.scale.setScalar(1.01);assert.throws(()=>bindSeatedDriver(vehicleB,b,pose),/1:1/);b.root.scale.setScalar(1);
const binding=bindSeatedDriver(vehicle,a,pose);
assert.throws(()=>bindSeatedDriver(vehicleB,a,pose));assert.throws(()=>bindSeatedDriver(vehicle,b,pose));
assert.equal(a.root.parent,vehicle);assert.equal(a.actorId,'F01');assert.equal(a.role,'forklift_driver');assert.equal(a.root.scale.toArray().join(','),'1,1,1');
const snapshot=binding.snapshot();assert(snapshot.seat_error_m<2e-5);assert(Object.values(snapshot.grip_error_m).every(v=>v<2e-5));assert(Object.values(snapshot.sole_error_m).every(v=>v<2e-5));
const tint=new Set();let sharedBody=0;const glyph=a.root.getObjectByName('role_badge__F01');assert(glyph&&glyph.userData.roleCode==='05'&&glyph.userData.icon==='forklift');
a.root.traverse(n=>{if(!n.isMesh)return;if(n!==glyph){assert(sharedGeo.has(n.geometry));sharedBody++;}for(const m of Array.isArray(n.material)?n.material:[n.material])if(/^V3_Worker_Role/.test(m.name)){assert.equal(m.color.getHexString(),'f4c542');assert(!sharedMat.has(m));tint.add(m);}});assert.equal(tint.size,2);
let ownedDisposals=0;for(const resource of [...tint,glyph.geometry])resource.addEventListener('dispose',()=>ownedDisposals++);
carA.updateMatrixWorld(true);const bounds=new T.Box3();const badgeBounds=new T.Box3();
a.root.traverseVisible(n=>{if(!n.isMesh)return;const p=n.geometry.getAttribute('position');for(let i=0;i<p.count;i++){const v=vehicle.worldToLocal(new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld));bounds.expandByPoint(v);if(n===glyph)badgeBounds.expandByPoint(v);}});
assert(bounds.min.x>=-.6&&bounds.max.x<=.6&&bounds.min.y>=0&&bounds.max.y<=2.1&&bounds.min.z>=-1.5&&bounds.max.z<=1.5);
const parts=JSON.parse(await readFile('../assets/v3/blender/forklift.stats.json','utf8')).components;
for(const part of parts){const lo=part.bounds_runtime.min,hi=part.bounds_runtime.max;assert(badgeBounds.min.toArray().some((v,i)=>v>=hi[i]-2e-6||badgeBounds.max.toArray()[i]<=lo[i]+2e-6),'New driver badge overlaps vehicle component '+part.name);}
const beforeReset=JSON.stringify(binding.snapshot());a.root.position.set(2,3,4);a.root.getObjectByName('joint__head').rotation.x=.4;binding.reset();assert.equal(JSON.stringify(binding.snapshot()),beforeReset);
vehicle.position.set(2,0,-1);vehicle.rotation.y=.7;const moved=binding.snapshot();assert(moved.seat_error_m<2e-5&&Object.values(moved.grip_error_m).every(v=>v<2e-5));
binding.release();binding.release();assert.equal(a.root.parent,original.parent);assert.deepEqual(a.root.position.toArray(),original.position);assert.deepEqual(a.root.quaternion.toArray(),original.quaternion);assert.equal(a.disposed,false);assert.throws(()=>binding.reset());
const next=bindSeatedDriver(vehicleB,a,pose);next.release();assert.equal(a.root.parent,registry);
assert.equal(JSON.stringify(sourceRoot.toJSON()),sourceBefore);assert.equal(sharedDisposals,0);
disposeWorkerInstance(a);disposeWorkerInstance(a);assert.equal(ownedDisposals,3);disposeWorkerInstance(b);disposeWorkerInstance(packer);assert.equal(sharedDisposals,0);
const report={task_id:'P07',source_hashes:sourceHashes,worker_glb_sha256:sha(workerBytes),actual_contact_snapshot:snapshot,actual_visible_bounds_vehicle_m:{min:bounds.min.toArray(),max:bounds.max.toArray()},new_driver_badge_clear_of_all_actual_vehicle_component_bounds:true,
 shared_body_meshes:sharedBody,exactly_two_yellow_tint_clones:true,existing_instance_reparented_not_cloned:true,actor_identity_preserved:true,non_driver_rejected:true,non_unit_scale_rejected:true,double_actor_binding_rejected:true,occupied_vehicle_rejected:true,reset_exact:true,release_restores_original_parent_and_pose:true,release_does_not_dispose_employee:true,rebind_after_release:true,shared_template_unchanged:true,shared_resource_disposals:sharedDisposals,owned_resource_disposals:ownedDisposals};
await writeFile('../assets/v3/iterations/worker-base/P07/actual-runtime-driver-checks.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({task_id:'P07',passed:true,shared_body_meshes:sharedBody,seat_error_m:snapshot.seat_error_m,grip_error_m:snapshot.grip_error_m,sole_error_m:snapshot.sole_error_m,owned_disposals:ownedDisposals,shared_disposals:sharedDisposals}));
