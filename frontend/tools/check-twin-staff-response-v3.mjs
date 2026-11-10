import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {tmpdir} from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const requested=process.argv[2]==='--out'?process.argv[3]:null;
assert(process.argv.length===(requested?4:2),'Use optional --out NEW_EXTERNAL_DIRECTORY');
const output=requested?path.resolve(requested):await fs.mkdtemp(path.join(tmpdir(),'qoima-twin-staff-'));
if(requested){await assert.rejects(()=>fs.access(output),{code:'ENOENT'});await fs.mkdir(output,{recursive:true});}
const pending=new Map(),pins={};
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
async function read(relative){const bytes=await fs.readFile(path.join(front,relative));pins[relative]=sha(bytes);return bytes;}
async function compile(relative){
 if(pending.has(relative))return pending.get(relative);
 const file=path.join(output,'runtime',relative+'.mjs');
 pending.set(relative,file);
  let code=ts.transpileModule((await read(relative)).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
  for(const hit of [...code.matchAll(/import\s+(\w+)\s+from\s+['"]([^'"]+\.json)['"];?/g)]){
   const name=path.posix.normalize(path.posix.join(path.posix.dirname(relative),hit[2]));code=code.replace(hit[0],'const '+hit[1]+'='+await read(name)+';');
  }
  for(const hit of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]){
   let target;
   if(hit[1].startsWith('.'))target=await compile(path.posix.normalize(path.posix.join(path.posix.dirname(relative),hit[1]+'.ts')));
   else if(hit[1].startsWith('three'))target=path.join(front,'node_modules',hit[1]==='three'?'three/build/three.module.js':hit[1]);
   else continue;
   code=code.replace(hit[0],'from '+JSON.stringify(pathToFileURL(target).href));
  }
 code=code.replaceAll('import.meta.env.BASE_URL',"'/'");await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,code,{flag:'wx'});return file;
}
const load=async name=>import(pathToFileURL(await compile('src/adaptive-v3/'+name+'.ts')));
const {adaptWarehouseV3}=await load('warehouseAdapter');
const {validateRoutePolicy}=await load('warehouseRouting');
const {createWorkerInstance,disposeWorkerInstance}=await load('workerRoles');
const {staffingHomeNodes}=await load('workerRoleAssignment');
const texts={};
for(const [key,name]of Object.entries({fixture:'v3/warehouse-fixture-v3.json',layout:'adaptive-v3/layout-manifest.json',registry:'v3/worker-registry-v3.json',profiles:'v3/worker-profiles-v3.json'}))texts[key]=(await read('public/data/'+name)).toString();
const bundle=await adaptWarehouseV3(texts),policy=await validateRoutePolicy((await read('public/data/v3/route-policy-v3.json')).toString(),bundle);
const bytes=await read('public/models/v3/worker-base.glb');
assert.equal(sha(bytes),'542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163');
const template=(await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;
const homes=staffingHomeNodes(bundle),nodes=new Map([...bundle.layout.walk.nodes,...bundle.layout.vehicle.nodes].map(node=>[node.node_id,node]));
const scene=new T.Scene(),instances=[];
for(const worker of bundle.registry.workers){
 const instance=createWorkerInstance(template,worker.actor_id,worker.baseline_role);instances.push(instance);
 const root=instance.root;root.userData.semanticKind='actor';root.userData.semanticId=worker.actor_id;root.position.fromArray(nodes.get(homes.get(worker.actor_id)).world_pos);root.rotation.y=worker.baseline_role==='packer'?Math.PI:0;scene.add(root);
}
scene.updateMatrixWorld(true);
const roots=new Map(instances.map(instance=>[instance.actorId,instance.root]));
const capture=()=>instances.map(instance=>{const rows=[];instance.root.traverse(node=>rows.push([node.name,node.position.toArray(),node.quaternion.toArray(),node.scale.toArray(),node.matrixAutoUpdate,node.matrixWorldAutoUpdate]));return{actor_id:instance.actorId,parent:instance.root.parent?.uuid,rows};});
const original=capture(),fixtureBefore=JSON.stringify(bundle),geometries=new Set(),materials=new Set();
scene.traverse(node=>{if(node.isMesh){geometries.add(node.geometry);for(const material of Array.isArray(node.material)?node.material:[node.material])materials.add(material);}});
let borrowedDisposals=0;for(const resource of [...geometries,...materials])resource.addEventListener('dispose',()=>borrowedDisposals++);
assert.equal(instances.length,24);console.log(JSON.stringify({source_fixture_ready:true,actual_native_actor_count:instances.length,source_worker_sha256:sha(bytes)}));
await assert.doesNotReject(()=>fs.access(path.join(front,'src/adaptive-v3/twin/twinStaffResponse.ts')),'Four original packers must visibly respond to the finite source congestion episode');
const {createTwinStaffResponse}=await load('twin/twinStaffResponse');
roots.get('K06').position.x+=.01;scene.updateMatrixWorld(true);const wrongHome=capture();
await assert.rejects(()=>createTwinStaffResponse(scene,bundle,policy),/ORIGINAL_POST/);assert.deepEqual(capture(),wrongHome);
roots.get('K06').position.x-=.01;scene.updateMatrixWorld(true);assert.deepEqual(capture(),original);
const response=await createTwinStaffResponse(scene,bundle,policy);
const cases=['late_constructor_refusal_preserves_roots_and_releases_owner'];
try{
 assert.equal(response.dynamicRoots.length,5);assert.equal(new Set(response.dynamicRoots).size,5);
 for(const id of ['K01','K02','K03','K05','K06'])assert(response.dynamicRoots.includes(roots.get(id)));
 cases.push('five_same_original_roots_and_24_total_staff');
 assert(response.stationReady_s.PK05>46+51.8/1.2);assert(response.stationReady_s.PK06>46+51.8/1.2);
 assert(response.breakClear_s.PK05<response.stationReady_s.PK05);assert(response.breakClear_s.PK06<response.stationReady_s.PK06);
 for(const station of ['PK05','PK06']){
  const id=station==='PK05'?'K01':'K02',ready=response.stationReady_s[station];
  const before=response.sample('B',ready-1e-6,[station]).workers.find(worker=>worker.actor_id===id);
  const at=response.sample('B',ready,[station]).workers.find(worker=>worker.actor_id===id);
  assert.notEqual(before.phase,'working');assert.equal(at.phase,'working');assert(at.available);
 }
 cases.push('source_speed_native_arrival_and_vacancy_gate');
 const times=[0,29.999999,30,46,48,100,104,response.stationReady_s.PK05,response.stationReady_s.PK06,180,240,259.9,260,320,response.duration_s,response.duration_s+1];
 const untouched=instances.filter(instance=>!['K01','K02','K03','K05','K06'].includes(instance.actorId));
 const staticState=()=>untouched.map(instance=>[instance.actorId,instance.root.position.toArray(),instance.root.quaternion.toArray(),instance.root.scale.toArray()]);
 const staticBefore=staticState();let minimumSpacing=Infinity;
 for(const variant of ['A','B'])for(const at of times){
  response.apply(variant,at,['PK03','PK05','PK06']);const snapshot=response.snapshot();
  assert.equal(snapshot.source_worker_count,24);assert.equal(snapshot.engine_operation,false);assert.equal(snapshot.operational_admission,false);
  assert.deepEqual(staticState(),staticBefore);
  for(const worker of snapshot.workers){
   assert.equal(worker.role,'packer');assert.equal(scene.getObjectByProperty('name',roots.get(worker.actor_id).name),roots.get(worker.actor_id));
   const head=response.actorPosition(variant,worker.actor_id,at);assert(head.every(Number.isFinite));
   const actualHead=roots.get(worker.actor_id).getObjectByName('joint__head').getWorldPosition(new T.Vector3()).add(new T.Vector3(0,.55,0));
   assert(actualHead.distanceTo(new T.Vector3(...head))<2e-6);
   if(variant==='A'&&['K01','K02'].includes(worker.actor_id))assert(new T.Vector3(...worker.position).distanceTo(new T.Vector3(...nodes.get(homes.get(worker.actor_id)).world_pos))<2e-6);
  }
  const actualActors=[];scene.traverse(node=>{if(node.userData.semanticKind==='actor')actualActors.push(node.userData.semanticId);});assert.equal(actualActors.length,24);assert.equal(new Set(actualActors).size,24);
 }
 cases.push('A_B_real_motion_same_IDs_static19_and_false_admission');
 for(const variant of ['A','B'])for(let index=0;index<=400;index++){
  const snapshot=response.sample(variant,response.duration_s*index/400);
  const all=instances.map(instance=>snapshot.workers.find(row=>row.actor_id===instance.actorId)?.position??nodes.get(homes.get(instance.actorId)).world_pos);
  for(let a=0;a<all.length;a++)for(let b=a+1;b<all.length;b++)minimumSpacing=Math.min(minimumSpacing,Math.hypot(all[a][0]-all[b][0],all[a][2]-all[b][2]));
 }
 assert(minimumSpacing>=.88-1e-7,'Staff path/hold overlap '+minimumSpacing);cases.push('401_samples_all24_staff_spacing_both_variants');
 response.apply('B',180,['PK05','PK06']);const inert=JSON.stringify(response.snapshot()),posed=capture();
 response.actorPosition('A','K01',90);response.sample('B',77);response.actorActivity('A',90,'K02');assert.equal(JSON.stringify(response.snapshot()),inert);assert.deepEqual(capture(),posed);
 for(const time of [NaN,Infinity,-1,true])assert.throws(()=>response.apply('B',time));assert.throws(()=>response.apply('FOREIGN',10));assert.deepEqual(capture(),posed);
 cases.push('pure_queries_and_invalid_apply_are_inert');
 assert.equal(response.actorActivity('B',180,'K01',['PK05']).phase,'working');
 assert.equal(response.actorActivity('B',180,'K01').phase,'waiting');
 assert.equal(JSON.stringify(response.snapshot()),inert);cases.push('activity_queries_use_explicit_flow_mask_across_variants');
 const k03Hand=roots.get('K03').getObjectByName('joint__hand_L');
 response.apply('A',180,[]);const k03Idle=k03Hand.quaternion.toArray();
 response.apply('A',180,['PK03']);assert.notDeepEqual(k03Hand.quaternion.toArray(),k03Idle,'Original K03 must visibly work only when actual PK03 flow is processing');
 assert.equal(response.actorActivity('A',180,'K03',['PK03']).phase,'working');
 response.apply('B',180,[]);assert.deepEqual(k03Hand.quaternion.toArray(),k03Idle);
 assert.equal(response.actorActivity('B',180,'K03').phase,'waiting');
 cases.push('original_K03_work_pose_requires_explicit_PK03_flow_mask');
 const hand=roots.get('K01').getObjectByName('joint__hand_L');response.apply('B',180,[]);const waitingHand=hand.quaternion.toArray();
 response.apply('B',180,['PK05']);assert.notDeepEqual(hand.quaternion.toArray(),waitingHand);
 const workHand=hand.quaternion.toArray();response.apply('B',181,['PK05']);assert.notDeepEqual(hand.quaternion.toArray(),workHand);
 for(let at=110;at<=240;at+=5){response.apply('B',at,['PK03','PK05','PK06']);for(const id of ['K01','K02','K03'])roots.get(id).traverse(node=>{
  if(!node.name.startsWith('joint__'))return;
  if(node.name.includes('palm_roll')){assert(Math.abs(node.quaternion.x)<1e-10&&Math.abs(node.quaternion.z)<1e-10);return;}
  const limits=JSON.parse(node.userData.limits_xyz_json??'null');if(!limits)return;
  [node.rotation.x,node.rotation.y,node.rotation.z].forEach((value,index)=>assert(value>=limits[index][0]-1e-7&&value<=limits[index][1]+1e-7,node.name));
 });}
 cases.push('visible_work_arm_animation_with_source_limits_and_neutral_pronation');
 response.apply('B',180,['PK05','PK06']);const first=capture();response.apply('A',50);response.apply('B',180,['PK05','PK06']);assert.deepEqual(capture(),first);cases.push('absolute_reverse_seek_repeatable');
 await assert.rejects(()=>createTwinStaffResponse(scene,bundle,policy),/BUSY/);assert.deepEqual(capture(),first);cases.push('duplicate_owner_refused_without_mutation');
 response.apply('B',response.duration_s+1);assert.deepEqual(capture(),original);cases.push('all_four_return_home_and_K03_original_pose_then_hold');
 response.dispose();response.dispose();assert.deepEqual(capture(),original);assert.equal(borrowedDisposals,0);assert.equal(JSON.stringify(bundle),fixtureBefore);cases.push('dispose_restores_all_source_poses_without_borrowed_disposal');
 for(const [relative,digest]of Object.entries(pins))assert.equal(sha(await fs.readFile(path.join(front,relative))),digest);
 const report={passed:true,cases,case_count:cases.length,stationReady_s:response.stationReady_s,breakClear_s:response.breakClear_s,duration_s:response.duration_s,timings:response.timings,minimum_sampled_actor_spacing_m:minimumSpacing,source_pins:pins,scope:'Real source worker geometry and finite visual staff tracks. No browser, backend engine, force/material or operational certificate.'};
 await fs.writeFile(path.join(output,'checks.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(report));
}finally{response.dispose();for(const instance of instances)disposeWorkerInstance(instance);}
