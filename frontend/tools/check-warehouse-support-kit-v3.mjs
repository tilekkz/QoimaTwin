import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import ts from 'typescript';

const cache=path.resolve('../work/v3/warehouse-support-kit-check'),input_hashes={},cases=[];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function source(p){const bytes=await readFile('../'+p);input_hashes[p]=sha(bytes);return bytes;}
await mkdir(cache,{recursive:true});
const bindings=JSON.parse((await source('frontend/src/adaptive-v3/warehouseSupportBindings.json')).toString());
let code=ts.transpileModule((await source('frontend/src/adaptive-v3/warehouseSupportKit.ts')).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
code=code.replace("from 'three'",`from ${JSON.stringify(pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href)}`)
 .replace("from 'three/examples/jsm/loaders/GLTFLoader.js'",`from ${JSON.stringify(pathToFileURL(path.resolve('node_modules/three/examples/jsm/loaders/GLTFLoader.js')).href)}`)
 .replace("import bindings from './warehouseSupportBindings.json';",'const bindings='+JSON.stringify(bindings)+';')
 .replace('import.meta.env.BASE_URL',"'/'");
await writeFile(path.join(cache,'warehouseSupportKit.mjs'),code);
const {loadWarehouseSupportKit,applyCarryPose,validateWarehouseCarryPose}=await import(pathToFileURL(path.join(cache,'warehouseSupportKit.mjs')));
const files=new Map();for(const binding of Object.values(bindings)){const bytes=await source('frontend/public/'+binding.path);assert.equal(bytes.length,binding.bytes);assert.equal(sha(bytes),binding.sha256);files.set('/'+binding.path,bytes);}
for(const [runtime,canonical]of [['carryPose','assets/v3/iterations/warehouse/W04.3/candidate-carry-pose.json'],['vehicleSupport','docs/v3/contract-proposals/vehicle-handling-v3.json']]){assert.deepEqual(files.get('/'+bindings[runtime].path),await source(canonical));cases.push('byte_identical_'+runtime);}
const reference=JSON.parse((await source('assets/v3/iterations/warehouse/W04.3/carry-candidate-browser/review-capture.json')).toString());
assert.equal(reference.candidate_sha256,bindings.carryPose.sha256);
await source('frontend/tools/check-warehouse-support-kit-v3.mjs');
const originalFetch=globalThis.fetch,originalParse=GLTFLoader.prototype.parseAsync;
let requests=[],resources=new Map(),parsed=0,scenario='success',controller;
function observe(root){root.traverse(n=>{if(n instanceof THREE.Mesh){for(const r of [n.geometry,...(Array.isArray(n.material)?n.material:[n.material])])if(!resources.has(r)){resources.set(r,0);r.addEventListener('dispose',()=>resources.set(r,resources.get(r)+1));}}});}
GLTFLoader.prototype.parseAsync=async function(bytes,base){
 parsed++;if(scenario==='parse_failure'&&parsed===3)throw Error('INJECTED_PARSE_FAILURE');
 const gltf=await originalParse.call(this,bytes,base);observe(gltf.scene);
 if(scenario==='abort_parse'&&parsed===2)controller.abort();
 if(scenario==='missing_metadata'&&parsed===3)gltf.scene.traverse(n=>{delete n.userData.asset_id;});
 return gltf;
};
globalThis.fetch=async(url,options)=>{
 requests.push(url);assert.equal(options.cache,'no-store');assert.equal(options.signal,controller.signal);
 if(scenario==='offline')throw new TypeError('network unavailable');
 if(scenario==='abort_fetch'&&requests.length===3){controller.abort();throw new DOMException('Aborted','AbortError');}
 const bytes=files.get(url);assert(bytes,'unexpected URL '+url);
 if(scenario==='missing_file'&&url===('/'+bindings.restraint.path))return new Response('',{status:404});
 if(scenario==='stale_model'&&url===('/'+bindings.restraint.path)){const changed=Buffer.from(bytes);changed[changed.length-1]^=1;return new Response(changed);}
 if(scenario==='stale_C08'&&url===('/'+bindings.vehicleSupport.path)){const changed=Buffer.from(bytes);changed[changed.length-1]^=1;return new Response(changed);}
 return new Response(bytes);
};
function start(mode){scenario=mode;requests=[];resources=new Map();parsed=0;controller=new AbortController();}
function allDisposed(){assert([...resources.values()].every(n=>n===1),JSON.stringify([...resources.values()]));}
let maximumPosePositionError=0,maximumPoseQuaternionError=0,checkedJoints=0,uniqueResources=0;
try{
 start('success');const kit=await loadWarehouseSupportKit(controller.signal);
 assert.equal(requests.length,6);assert.equal(parsed,4);assert(Object.isFrozen(kit)&&Object.isFrozen(kit.carryPose)&&Object.isFrozen(kit.carryPose.jointEulerXYZ)&&Object.isFrozen(kit.travelProfiles)&&Object.isFrozen(kit.longCradleDesign)&&Object.isFrozen(kit.sourceRefs));
 assert.deepEqual(new Set(kit.travelProfiles.map(p=>p.archetype_id)),new Set(['HEAVY_BOX','PALLET_LOAD','IBC','LONG_BUNDLE','DRUM','FRAGILE_CRATE']));
 assert.equal(kit.travelProfiles.find(p=>p.archetype_id==='LONG_BUNDLE').total_lifted_mass_kg,240);assert.equal(kit.longCradleDesign.mass_kg,40);
 for(const [key,id]of [['manual','worker-manual'],['cart','picking-cart-tote-fixture'],['cradle','long-cradle'],['restraint','long-restraint-rig']]){let found=false;kit[key].traverse(n=>{if(n.userData.asset_id===id)found=true;});assert(found,id);}
 cases.push('four_native_templates_and_frozen_profiles');
 const root=kit.manual.getObjectByName('worker_base_root').clone(true),before=new Map();root.traverse(n=>{if(n.name.startsWith('joint__'))before.set(n.name,{p:n.position.toArray(),q:n.quaternion.toArray()});});
 const applied=applyCarryPose(root,kit.carryPose),expected=reference.frames[0].state.joints;
 for(const actual of applied.snapshot()){
  const saved=expected[actual.name];assert(saved,actual.name);checkedJoints++;
  maximumPosePositionError=Math.max(maximumPosePositionError,...actual.position.map((v,i)=>Math.abs(v-saved.position[i])));
  const q=new THREE.Quaternion().fromArray(actual.quaternion),r=new THREE.Quaternion().fromArray(saved.quaternion);maximumPoseQuaternionError=Math.max(maximumPoseQuaternionError,Math.min(q.toArray().reduce((s,v,i)=>s+(v-r.toArray()[i])**2,0),q.toArray().reduce((s,v,i)=>s+(v+r.toArray()[i])**2,0))**.5);
 }
 assert.equal(checkedJoints,27);assert(maximumPosePositionError<1e-12);assert(maximumPoseQuaternionError<1e-12);cases.push('all_27_joints_match_reviewed_browser_pose');
 applied.restore();applied.restore();for(const [name,rest]of before){const n=root.getObjectByName(name);assert.deepEqual(n.position.toArray(),rest.p);assert.deepEqual(n.quaternion.toArray(),rest.q);}cases.push('idempotent_exact_joint_restore');
 const missing=root.clone(true);missing.getObjectByName('joint__finger_thumb_R').removeFromParent();const untouched=missing.getObjectByName('joint__upper_arm_L').quaternion.toArray();assert.throws(()=>applyCarryPose(missing,kit.carryPose),/MISSING_STATIC_CARRY_JOINT/);assert.deepEqual(missing.getObjectByName('joint__upper_arm_L').quaternion.toArray(),untouched);cases.push('missing_joint_rejected_before_any_pose_mutation');
 const badAxis=root.clone(true);badAxis.getObjectByName('joint__elbow_swivel_R').userData.custom_axis_runtime=[0,0,0];const unchanged=badAxis.getObjectByName('joint__upper_arm_L').quaternion.toArray();assert.throws(()=>applyCarryPose(badAxis,kit.carryPose),/INVALID_STATIC_CARRY_AXIS/);assert.deepEqual(badAxis.getObjectByName('joint__upper_arm_L').quaternion.toArray(),unchanged);cases.push('invalid_custom_axis_atomic_rejection');
 for(const [label,mutate,reason]of [
  ['missing_thumb',p=>delete p.jointTranslations.joint__finger_thumb_R,/INVALID_STATIC_CARRY_THUMBS/],
  ['additive_thumb',p=>p.jointTranslations.joint__finger_thumb_R=[0,0,-.01],/INVALID_STATIC_CARRY_THUMBS/],
  ['wrong_HU_size',p=>p.cargo.dimensions_xyz_m=[.3,.24,.24],/INVALID_STATIC_CARRY_CARGO/],
  ['scaled_worker',p=>p.worker_root.scale=[.9,.9,.9],/INVALID_STATIC_CARRY_ROOT/],
  ['nonfinite_joint',p=>p.jointEulerXYZ.joint__hand_L=[NaN,0,0],/INVALID_STATIC_CARRY_JOINTS/],
  ['other_model',p=>p.input_hashes['frontend/public/models/v3/worker-manual.glb']='0'.repeat(64),/STATIC_CARRY_MODEL_MISMATCH/],
 ]){const changed=structuredClone(kit.carryPose);mutate(changed);assert.throws(()=>validateWarehouseCarryPose(changed),reason);cases.push('reject_'+label);}
 uniqueResources=resources.size;assert(uniqueResources>0);assert([...resources.values()].every(n=>n===0));kit.dispose();assert.equal(kit.disposed,true);allDisposed();kit.dispose();allDisposed();cases.push('owned_native_resources_disposed_exactly_once');
 for(const [mode,reason]of [['offline',/network unavailable/],['missing_file',/нет комплекта/],['stale_model',/изменился/],['stale_C08',/изменился/],['parse_failure',/INJECTED_PARSE_FAILURE/],['missing_metadata',/отсутствует интерфейс/],['abort_parse',/cancelled/],['abort_fetch',/Aborted/]]){
  start(mode);await assert.rejects(loadWarehouseSupportKit(controller.signal),reason);allDisposed();cases.push(mode+'_cleans_every_completed_asset');
 }
 start('success');controller.abort();await assert.rejects(loadWarehouseSupportKit(controller.signal),/cancelled/);assert.equal(requests.length,0);cases.push('preaborted_signal_has_no_requests');
 start('success');const retry=await loadWarehouseSupportKit(controller.signal);assert.equal(parsed,4);retry.dispose();allDisposed();cases.push('fresh_retry_after_failures');
}finally{globalThis.fetch=originalFetch;GLTFLoader.prototype.parseAsync=originalParse;}
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,cases,owned_unique_resources_on_success:uniqueResources,reviewed_native_pose_joints:checkedJoints,maximum_pose_local_position_error_m:maximumPosePositionError,maximum_pose_quaternion_component_error:maximumPoseQuaternionError,source_byte_identity:true,input_hashes,scope:'Optional SHA-bound loader and exact static pose application/resource lifecycle CPU proof using actual accepted GLBs. No renderer, physical transfer, force/stability, resource schedule, loaded route or engine acceptance.'};
await writeFile('../docs/adaptive-v3/evidence/W04.3-support-kit-checks.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,cases:cases.length,input_hashes:undefined}));
