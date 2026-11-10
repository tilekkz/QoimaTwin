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
const output=requested?path.resolve(requested):await fs.mkdtemp(path.join(tmpdir(),'qoima-twin-fleet-'));
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
const {bindSeatedDriver,validateSeatedDriverPose}=await load('seatedDriver');
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
const forkBytes=await read('public/models/v3/forklift.glb');
assert.equal(sha(forkBytes),'937816125a8c1522148e4928b34257096bc22dcb4a359201a08b80d78b1ee156');
const forkTemplate=(await new GLTFLoader().parseAsync(forkBytes.buffer.slice(forkBytes.byteOffset,forkBytes.byteOffset+forkBytes.byteLength),'')).scene;
const driverPose=validateSeatedDriverPose(JSON.parse((await read('public/data/v3/seated-driver-pose.json')).toString()));
const seats=[];
for(const [id,home]of [['FL01','IN_W_BULK'],['FL02','OUT_E_B2B']]){
 const sourceNode=bundle.layout.vehicle.nodes.find(n=>n.node_id==='v3:service:'+home),vehicle=forkTemplate.clone(true);
 vehicle.name='vehicle__'+id;vehicle.position.fromArray(sourceNode.world_pos);vehicle.rotation.y=sourceNode.yaw_rad;scene.add(vehicle);
 const driver=bundle.registry.workers.find(w=>w.assigned_vehicle_id===id);seats.push(bindSeatedDriver(vehicle,instances.find(a=>a.actorId===driver.actor_id),driverPose));
}
scene.updateMatrixWorld(true);
const roots=new Map(instances.map(instance=>[instance.actorId,instance.root]));
const capture=()=>instances.map(instance=>{const rows=[];instance.root.traverse(node=>rows.push([node.name,node.position.toArray(),node.quaternion.toArray(),node.scale.toArray(),node.matrixAutoUpdate,node.matrixWorldAutoUpdate]));return{actor_id:instance.actorId,parent:instance.root.parent?.uuid,rows};});
const original=capture(),fixtureBefore=JSON.stringify(bundle),geometries=new Set(),materials=new Set();
scene.traverse(node=>{if(node.isMesh){geometries.add(node.geometry);for(const material of Array.isArray(node.material)?node.material:[node.material])materials.add(material);}});
let borrowedDisposals=0;for(const resource of [...geometries,...materials])resource.addEventListener('dispose',()=>borrowedDisposals++);
assert.equal(instances.length,24);console.log(JSON.stringify({source_fixture_ready:true,actual_native_actor_count:instances.length,source_worker_sha256:sha(bytes)}));

const layoutPlan=JSON.parse(await fs.readFile(path.join(front,'../docs/adaptive-v3/fixtures/layout-plans/dense-manual-b-164-v1.json'),'utf8'));
console.log(JSON.stringify({source_forklift_count:seats.length,source_worker_count:instances.length,actual_seated_contacts:seats.map(s=>s.snapshot())}));
await assert.doesNotReject(()=>fs.access(path.join(front,'src/adaptive-v3/twin/twinFleetTraffic.ts')),'Five added native forklifts and six green visual-extra people must animate in both comparisons');
const {createTwinStaffResponse}=await load('twin/twinStaffResponse');
const staff=await createTwinStaffResponse(scene,bundle,policy);
const {createTwinFleetTraffic}=await load('twin/twinFleetTraffic');
const sourceColors=[...materials].filter(m=>m.color).map(m=>[m,m.color.toArray()]);
const blocked=structuredClone(layoutPlan);blocked.modules[0].outer_bounds_world={min:[3,0,40],max:[9,3,50]};
assert.throws(()=>createTwinFleetTraffic(scene,bundle,blocked),/ROUTE_OBSTRUCTED/);assert.deepEqual(capture(),original);assert.equal(borrowedDisposals,0);
const fleet=createTwinFleetTraffic(scene,bundle,layoutPlan);
const cases=['late_obstructed_B_failure_is_atomic_and_releases_scene_owner'];
try{
 assert.equal(fleet.dynamicRoots.length,6);
 assert.equal(fleet.summary().original_vehicles,2);assert.equal(fleet.summary().extra_vehicles,5);assert.equal(fleet.summary().vehicles,7);
 assert.equal(fleet.summary().original_people,24);assert.equal(fleet.summary().extra_people,6);assert.equal(fleet.summary().people,30);
 assert.equal(fleet.summary().engine_operation,false);assert.equal(fleet.summary().completed_jobs,0);cases.push('five_extra_native_forklifts_and_six_green_people_both_variants');
 const extras=[];scene.traverse(n=>{if(n.userData.visual_extra&&['demo-actor','demo-vehicle'].includes(n.userData.semanticKind))extras.push(n);});
 assert.equal(extras.filter(n=>n.userData.semanticKind==='demo-actor').length,6);assert.equal(extras.filter(n=>n.userData.semanticKind==='demo-vehicle').length,5);
 assert.equal(new Set(extras.map(n=>n.userData.semanticId)).size,11);assert(extras.every(n=>n.scale.distanceTo(new T.Vector3(1,1,1))<1e-9));
 const sourceActors=[];scene.traverse(n=>{if(n.userData.semanticKind==='actor')sourceActors.push(n.userData.semanticId);});assert.equal(sourceActors.length,24);assert.equal(new Set(sourceActors).size,24);cases.push('same_source24_distinct_DEMO_IDs_and_native_scale');
 const vehicles=extras.filter(n=>n.userData.semanticKind==='demo-vehicle'),walker=extras.find(n=>n.userData.semanticId==='DEMO_WALKER_01');
 for(const vehicle of vehicles){const found=[];vehicle.traverse(n=>{if(n.userData.semanticKind==='demo-actor')found.push(n);});assert.equal(found.length,1);assert.equal(found[0].parent,vehicle);assert(found[0].position.distanceTo(new T.Vector3(0,.29,-.615))<1e-7);}
 const green=[];for(const root of [...vehicles,walker])root.traverse(n=>{if(n.isMesh)for(const m of Array.isArray(n.material)?n.material:[n.material])if(['V3_Worker_RoleVest','V3_Worker_RoleHeadwear'].includes(m.name))green.push(m);});assert(green.length>=12);assert(green.every(m=>m.color.getHexString()==='2aa56a'));cases.push('green_native_operator_hierarchy_and_seated_pose_preserved');
 const ownedGreen=new Set(green);let ownDisposals=0;for(const material of ownedGreen)material.addEventListener('dispose',()=>ownDisposals++);
 for(const vehicle of vehicles){const operator=vehicle.children.find(n=>n.userData.semanticKind==='demo-actor');for(const [body,anchor]of [['anchor_seat_contact','anchor_driver_seat'],['anchor_hand_grip_L','anchor_steering_grip_L'],['anchor_hand_grip_R','anchor_steering_grip_R'],['anchor_foot_floor_L','anchor_footrest_L'],['anchor_foot_floor_R','anchor_footrest_R']])assert(operator.getObjectByName(body).getWorldPosition(new T.Vector3()).distanceTo(vehicle.getObjectByName(anchor).getWorldPosition(new T.Vector3()))<1e-6);}
 cases.push('all_five_native_seat_hand_and_sole_contacts_preserved');
 fleet.apply('A',0);const first=fleet.snapshot();fleet.apply('A',7);const moved=fleet.snapshot();
 assert(vehicles.every((v,i)=>Math.hypot(...moved.vehicles[i].position.map((n,k)=>n-first.vehicles[i].position[k]))>.05));
 assert.notDeepEqual(moved.walker.joint_rotations,first.walker.joint_rotations);cases.push('actual_wheel_root_and_native_walker_motion');
 const boxesA=bundle.layout.modules.map(m=>m.outer_bounds_world),boxesB=layoutPlan.modules.map(m=>m.outer_bounds_world),fixed=layoutPlan.fixed_obstacles.map(o=>o.bounds);
 let minimumSpacing=Infinity,maximumSpeed=0,stopped=0;
 for(const variant of ['A','B']){
  let previous=null;
  for(let index=0;index<=1440;index++){
   const t=index/4;fleet.apply(variant,t);const state=fleet.snapshot();
   for(const v of state.vehicles){
    maximumSpeed=Math.max(maximumSpeed,Math.abs(v.speed_m_s));if(v.phase==='stopped')stopped++;
    assert(v.speed_m_s<=.8000001);const root=vehicles.find(r=>r.userData.semanticId===v.id),actual=new T.Box3().setFromObject(root);
    assert(actual.min.x>=0&&actual.min.z>=0&&actual.max.x<=144&&actual.max.z<=72);
    for(const box of [...boxesA,...boxesB,...fixed])assert(!(actual.max.x>box.min[0]+1e-7&&actual.min.x<box.max[0]-1e-7&&actual.max.z>box.min[2]+1e-7&&actual.min.z<box.max[2]-1e-7),'Fleet intersects fixed source/B obstacle '+v.id);
    for(const [name,key]of [['front_L','front_L'],['front_R','front_R'],['rear_L','rear_L'],['rear_R','rear_R']]){const baseline=scene.getObjectByName('vehicle__FL02').getObjectByName('joint__wheel_'+name).quaternion;const expected=baseline.clone().multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),v.wheel_angles_rad[key]));assert(expected.angleTo(root.getObjectByName('joint__wheel_'+name).quaternion)<1e-7,'Native wheel roll differs from source arc');}
   }
   const all=[...state.vehicles.map(v=>v.position),state.walker.position];for(let a=0;a<all.length;a++)for(let b=a+1;b<all.length;b++)minimumSpacing=Math.min(minimumSpacing,Math.hypot(all[a][0]-all[b][0],all[a][2]-all[b][2]));
   if(previous)for(const v of state.vehicles){const old=previous.vehicles.find(o=>o.id===v.id);assert(Math.hypot(...v.position.map((n,k)=>n-old.position[k]))<=.2000001);assert.equal(v.yaw_rad,old.yaw_rad);}
   previous=state;
   const walkerBox=new T.Box3().setFromObject(walker);assert(walkerBox.min.y>=-1e-5&&walkerBox.min.x>=0&&walkerBox.max.x<=144&&walkerBox.min.z>=0&&walkerBox.max.z<=72);
   for(const box of [...boxesA,...boxesB,...fixed])assert(!(walkerBox.max.x>box.min[0]+1e-7&&walkerBox.min.x<box.max[0]-1e-7&&walkerBox.max.z>box.min[2]+1e-7&&walkerBox.min.z<box.max[2]-1e-7),'Native walker intersects source/B obstacle');
   for(const id of fleet.summary().extra_actor_ids){const head=fleet.actorPosition(variant,t,id),root=extras.find(n=>n.userData.semanticId===id),actualHead=root.getObjectByName('joint__head').getWorldPosition(new T.Vector3()).add(new T.Vector3(0,.55,0));assert(actualHead.distanceTo(new T.Vector3(...head))<2e-6);}
  }
 }
 assert(minimumSpacing>5);assert(stopped>0);cases.push('source_B_swept_clearance_spacing_braked_stops_and_no_point_turn');
 cases.push('native_walker_floor_and_obstacle_clearance_with_exact_head_queries');
 const period=fleet.summary().walker_period_s;fleet.apply('A',period-1e-7);const beforeLoop=walker.quaternion.clone(),beforePosition=walker.position.clone();fleet.apply('A',period);assert(beforeLoop.angleTo(walker.quaternion)<1e-6&&beforePosition.distanceTo(walker.position)<1e-6);cases.push('native_walker_closed_loop_has_no_heading_or_root_snap');
 const heavy=JSON.parse((await read('public/data/v3/heavy-inbound-fixture.json')).toString()),arcMap=new Map(bundle.layout.vehicle.arcs.map(a=>[a.arc_id,a]));
 const {sampleVehicleArc}=await load('warehouseRoutePose');
 const envelope=new T.Box3(new T.Vector3(-2,0,-2),new T.Vector3(2,3,2)),fleetSweeps=[];
 for(const vehicle of vehicles){const id=vehicle.userData.semanticId,box=new T.Box3();for(let t=0;t<=100;t+=.25){fleet.apply('A',t);box.union(new T.Box3().setFromObject(vehicle));}fleetSweeps.push([id,box]);}
 for(const phase of heavy.phases){const positions=[];if(phase.path.kind==='source_route')for(const id of phase.path.route.arc_ids)for(let k=0;k<=32;k++)positions.push(sampleVehicleArc(arcMap.get(id),k/32).position);else for(let k=0;k<=32;k++)positions.push(phase.from.position.map((n,i)=>n+(phase.to.position[i]-n)*k/32));for(const position of positions){const sourceEnvelope=envelope.clone().translate(new T.Vector3(...position));for(const [id,box]of fleetSweeps)assert(!box.intersectsBox(sourceEnvelope),'Canonical FL01 path crosses '+id);}}
 cases.push('canonical_FL01_actual_source_route_and_staging_envelope_disjoint');
 for(const t of [0,20,60,104,180,240,360]){fleet.apply('A',t);const a=fleet.snapshot();fleet.apply('B',t);const b=fleet.snapshot();assert.deepEqual(b.vehicles,a.vehicles);assert.deepEqual(b.walker,a.walker);}cases.push('common_A_B_extra_traffic_independent_of_packing_jobs');
 fleet.apply('B',70);const pose=fleet.snapshot();fleet.actorPosition('A',40,'DEMO_WALKER_01');assert.deepEqual(fleet.snapshot(),pose);fleet.apply('A',1);fleet.apply('B',70);assert.deepEqual(fleet.snapshot(),pose);for(const t of [NaN,Infinity,-1,true])assert.throws(()=>fleet.apply('A',t));assert.throws(()=>fleet.apply('FOREIGN',1));assert.deepEqual(fleet.snapshot(),pose);cases.push('pure_query_absolute_seek_and_invalid_input_inert');
 assert.deepEqual(capture(),original);staff.sample('B',180,['PK05']);assert.equal(JSON.stringify(bundle),fixtureBefore);for(const [material,color]of sourceColors)assert.deepEqual(material.color.toArray(),color);cases.push('source_originals_registry_and_staff_controller_untouched');
 assert.throws(()=>createTwinFleetTraffic(scene,bundle,layoutPlan),/BUSY/);cases.push('duplicate_scene_owner_rejected');
 fleet.dispose();fleet.dispose();assert.equal(borrowedDisposals,0);assert.equal(ownDisposals,ownedGreen.size);assert.deepEqual(capture(),original);assert(extras.every(n=>!n.parent||n.userData.semanticKind==='demo-actor'&&n.parent.userData.visual_extra));cases.push('cleanup_detaches_extra_roots_and_disposes_only_owned_materials');
 for(const [relative,digest]of Object.entries(pins))assert.equal(sha(await fs.readFile(path.join(front,relative))),digest);
 const report={passed:true,cases,case_count:cases.length,summary:fleet.summary(),minimum_sampled_extra_spacing_m:minimumSpacing,maximum_vehicle_speed_m_s:maximumSpeed,source_pins:pins,scope:'Native-geometry common visual extras only. No backend engines, browser, jobs, operational or material/force admission.'};
 await fs.writeFile(path.join(output,'checks.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(report));
}finally{fleet.dispose();staff.dispose();for(const seat of seats)seat.release();for(const instance of instances)disposeWorkerInstance(instance);}
