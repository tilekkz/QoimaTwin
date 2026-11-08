import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';

// Existing CPU-check convention: ignored transpilation cache, never accepted artifacts.
const root=path.resolve('..'),cache=path.join(root,'work/v3/pallet-transfer-check');
const output=path.join(root,'docs/adaptive-v3/evidence/W05.4.1-checks.json');
const sha=b=>createHash('sha256').update(b).digest('hex'),input_hashes={},positive=[],negative=[];
async function source(p){const b=await readFile(path.join(root,p));input_hashes[p]=sha(b);return b;}
const json=async p=>JSON.parse((await source(p)).toString());
await mkdir(cache,{recursive:true});
for(const name of ['workerRegistry','workerProfiles','warehouseAdapter','warehouseCargoHolders','warehouseCargo','warehouseActionTimeline','warehouseActionSources','warehouseRouting','warehouseRoutePose','warehousePalletTransferPlan']){
 const p='frontend/src/adaptive-v3/'+name+'.ts';let code=ts.transpileModule((await source(p)).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 const imports=[...code.matchAll(/import (\w+) from '([^']+\.json)';/g)];
 for(const match of imports){const p=path.relative(root,path.resolve(root,'frontend/src/adaptive-v3',match[2])).replaceAll('\\','/');code=code.replace(match[0],'const '+match[1]+'='+JSON.stringify(await json(p))+';');}
 code=code.replace(/from '(\.\/\w+)'/g,"from '$1.mjs'");await writeFile(path.join(cache,name+'.mjs'),code);
}
const load=async name=>import(pathToFileURL(path.join(cache,name+'.mjs')));
const {adaptWarehouseV3}=await load('warehouseAdapter');
const {registerWarehouseActionCatalogue}=await load('warehouseActionTimeline');
const {createWarehouseActionSourceReader,ActionSourceError}=await load('warehouseActionSources');
const {validateRoutePolicy,createWarehouseRouter}=await load('warehouseRouting');
const {compileVehicleRoutePreview,sampleVehicleArc}=await load('warehouseRoutePose');
const {compileWarehousePalletTransferPlan:compile,isWarehousePalletTransferPlan:isPlan,sampleWarehousePalletTransferPlan:sample,PalletTransferError}=await load('warehousePalletTransferPlan');
const manifest=await json('frontend/src/adaptive-v3/warehouseActionSourceManifest.json'),payload=new Map();
for(const row of manifest.entries){const original=await source(row.source_path),deployed=await source('frontend/public/'+row.url);assert.equal(sha(original),row.sha256,'Canonical source drift: '+row.source_path);assert.equal(original.length,row.bytes);assert.deepEqual(deployed,original,'Public proof drift: '+row.source_path);payload.set(row.url,deployed);}
const reader=createWarehouseActionSourceReader({fetcher:async url=>{assert(payload.has(url));return new Response(payload.get(url));}});
const texts={};for(const [k,p] of Object.entries({fixture:'frontend/public/data/v3/warehouse-fixture-v3.json',layout:'frontend/public/data/adaptive-v3/layout-manifest.json',registry:'frontend/public/data/v3/worker-registry-v3.json',profiles:'frontend/public/data/v3/worker-profiles-v3.json'}))texts[k]=new TextDecoder().decode(await reader.readSource(p));
const bundle=await adaptWarehouseV3(texts),catalogue=await registerWarehouseActionCatalogue(bundle,reader.readSource);
const policyText=(await source('frontend/public/data/v3/route-policy-v3.json')).toString(),policy=await validateRoutePolicy(policyText,bundle),router=createWarehouseRouter(bundle,policy);
for(const [p,h] of Object.entries(policy.source_hashes)){assert.equal(sha(await source(p)),h,'W03 source drift: '+p);}
const c08=await json('docs/v3/contract-proposals/vehicle-handling-v3.json');assert.deepEqual(policy.loaded_arc_eligibility,c08.per_cargo_arc_eligibility);assert.deepEqual(policy.loads,c08.loads);
for(const p of ['frontend/tools/check-warehouse-pallet-transfer-plan-v3.mjs','docs/adaptive-v3/specs/W05.4.1.md','frontend/src/adaptive-v3/forkliftPickup.ts','frontend/src/adaptive-v3/warehouseHolderScene.ts','frontend/src/adaptive-v3/seatedDriver.ts','docs/adaptive-v3/specs/M14.8.md','docs/adaptive-v3/specs/P07.md','docs/adaptive-v3/evidence/M14.8.json'])await source(p);
positive.push('actual_adapter_issued_catalogue_integrity_reader_and_hash_validated_W03_policy');
const request={handling_unit_id:'v3:HU:initial:DEMO_172:01',destination_slot_id:'v3:slot:HEAVY_E:009:L1:B1',actor_id:'F02',vehicle_id:'FL02'};
const before=JSON.stringify(bundle),result=compile(bundle,catalogue,policy,request);assert(result.ok,result.reason);const plan=result.plan;assert(isPlan(plan,bundle,catalogue,policy));
request.actor_id='changed';assert.equal(plan.request.actor_id,'F02');request.actor_id='F02';assert(!Object.isFrozen(request));
const near=(a,b,eps=1e-8)=>assert(Math.abs(a-b)<=eps,`${a} != ${b}`),vec=(a,b,eps=1e-8)=>a.forEach((v,i)=>near(v,b[i],eps)),angle=(a,b,eps=1e-8)=>near(Math.atan2(Math.sin(a-b),Math.cos(a-b)),0,eps);
const stock=JSON.parse(texts.fixture).inputs.initial_stock,hu=stock.find(h=>h.handling_unit_id===request.handling_unit_id);
assert.equal(hu.quantity_units,24);assert.equal(hu.gross_mass_kg,455);assert.deepEqual(hu.dimensions_xyz_m,[1.2,1.35,1]);assert.equal(hu.model_scale_factor,1);
assert.equal(stock.length,530);assert.equal(stock.reduce((s,h)=>s+h.quantity_units,0),12256);near(stock.reduce((s,h)=>s+h.gross_mass_kg,0),9403.85);
assert.equal(bundle.registry.workers.length,24);assert.equal(bundle.registry.vehicles.length,2);assert.equal(catalogue.clips.find(c=>c.clip_id==='driver_pickup').duration_s,30);assert(catalogue.clips.every(c=>!c.warehouse_joined));
positive.push('exact_existing_HU_units_mass_dimensions_scale_original_population_and_unsplit_clip');
// Independent table decode and placement from raw canonical fixture/layout, without plan pose helpers.
const raw=JSON.parse(texts.layout),decode=t=>t.rows.map(r=>Object.fromEntries(t.columns.map((k,i)=>[k,r[i]]))),slots=decode(raw.data.storage.slots),modules=decode(raw.data.storage.modules),nodes=decode(raw.data.graphs.vehicle.nodes),arcs=decode(raw.data.graphs.vehicle.arcs),arcById=new Map(arcs.map(a=>[a.arc_id,a]));
const sourceSlot=slots.find(s=>s.slot_id===hu.location.slot_id),targetSlot=slots.find(s=>s.slot_id===request.destination_slot_id);
assert(!stock.some(h=>h.location.slot_id===targetSlot.slot_id));assert(!targetSlot.reserve_only&&!targetSlot.retrieval_blocked);assert(targetSlot.allowed_cargo_archetype_ids.includes(hu.archetype_id));assert(targetSlot.max_payload_kg>=hu.gross_mass_kg);assert(hu.dimensions_xyz_m.every((d,i)=>d+2*targetSlot.clearance_each_side_m<=targetSlot.usable_dimensions_xyz_m[i]+1e-9));
function storagePose(slot){const module=modules[slot.module_index],shift=slot.usable_dimensions_xyz_m[2]/2-slot.clearance_each_side_m-hu.dimensions_xyz_m[2]/2;return {position:[slot.bin_anchor[0]+Math.sin(module.yaw_rad)*shift,slot.bin_anchor[1],slot.bin_anchor[2]+Math.cos(module.yaw_rad)*shift],yaw_rad:module.yaw_rad};}
const sourcePose=storagePose(sourceSlot),targetPose=storagePose(targetSlot);vec(sourcePose.position,[125.6,.18,29.5]);vec(targetPose.position,[125.6,.18,21.5]);vec(plan.source_pose.position,sourcePose.position);vec(plan.target_pose.position,targetPose.position);angle(sourcePose.yaw_rad,3*Math.PI/2);
positive.push('independent_raw_storage_placement_free_compatible_destination_before_cost');
const base={source_kind:'visual_fixture',engine_operation:false,mode:'forklift',actor_id:'F02',vehicle_id:'FL02',service_port_id:null,closed_arc_ids:[]};
const routeQueries={empty:{...base,from_node_id:'v3:service:OUT_E_B2B',to_node_id:nodes[sourceSlot.vehicle_node_index].node_id,cargo_archetype_id:null},loaded:{...base,from_node_id:nodes[sourceSlot.vehicle_node_index].node_id,to_node_id:nodes[targetSlot.vehicle_node_index].node_id,cargo_archetype_id:hu.archetype_id}};
const routeReports={};
// Independent O(V^2) Dijkstra on original source rows with the actual C08 eligibility filters.
function shortest(q){const allowed=new Set(q.cargo_archetype_id===null?policy.bare_geometry_subset_groups.flatMap(g=>g.arc_ids):c08.per_cargo_arc_eligibility.find(g=>g.archetype_id===q.cargo_archetype_id).allowed_arc_ids),pair=policy.equipment_pairs.find(p=>p.actor_id===q.actor_id&&p.vehicle_id===q.vehicle_id),dist=nodes.map(()=>Infinity),seen=new Set(),start=nodes.findIndex(n=>n.node_id===q.from_node_id),end=nodes.findIndex(n=>n.node_id===q.to_node_id);dist[start]=0;
 for(let i=0;i<nodes.length;i++){let at=-1;for(let j=0;j<nodes.length;j++)if(!seen.has(j)&&(at<0||dist[j]<dist[at]||dist[j]===dist[at]&&nodes[j].node_id<nodes[at].node_id))at=j;if(at<0||!Number.isFinite(dist[at])||at===end)break;seen.add(at);for(const a of arcs)if(a.from_node_index===at&&allowed.has(a.arc_id)&&a.equipment_pair_refs.includes(pair.pair_id)&&(q.cargo_archetype_id===null||a.cargo_transport_supported!==false))dist[a.to_node_index]=Math.min(dist[a.to_node_index],dist[at]+a.length_m);}
 return dist[end];}
for(const kind of ['empty','loaded']){const actual=router.route(routeQueries[kind]);assert.deepEqual(plan.routes[kind],actual);near(actual.length_m,shortest(routeQueries[kind]));let node=nodes.findIndex(n=>n.node_id===actual.from_node_id),length=0,turns=0;for(const id of actual.arc_ids){const a=arcById.get(id);assert.equal(a.from_node_index,node);node=a.to_node_index;length+=a.length_m;if(a.geometry.kind==='rear_steer_arc')turns++;const first=sampleVehicleArc(bundle.layout.vehicle.arcs.find(a=>a.arc_id===id),0),last=sampleVehicleArc(bundle.layout.vehicle.arcs.find(a=>a.arc_id===id),1);vec(first.position,nodes[a.from_node_index].world_pos);vec(last.position,nodes[a.to_node_index].world_pos);}
 assert.equal(nodes[node].node_id,actual.to_node_id);near(length,actual.length_m);const preview=compileVehicleRoutePreview(bundle,actual),phase=plan.phases.find(p=>p.phase_id===(kind==='empty'?'empty_approach':'loaded_route'));near(phase.end_s-phase.start_s,preview.duration_s);routeReports[kind]={length_m:length,arcs:actual.arc_ids,turns,duration_s:preview.duration_s};}
near(routeReports.empty.length_m,47.316748097475156);assert.equal(routeReports.empty.arcs.length,10);near(routeReports.loaded.length_m,22.60008367187212);assert.equal(routeReports.loaded.arcs.length,6);assert.equal(routeReports.loaded.turns,2);
positive.push('real_router_and_independent_shortest_chains_endpoints_lengths_turns_and_W03_timings');
// Read only GLB JSON for bind-matrix evidence, with no loader/renderer/native clearance claim.
const glb=await source('frontend/public/models/v3/forklift.glb');assert.equal(glb.readUInt32LE(0),0x46546c67);const gltf=JSON.parse(glb.subarray(20,20+glb.readUInt32LE(12)).toString());
const carriage=gltf.nodes.find(n=>n.name==='joint__carriage'),reach=gltf.nodes.find(n=>n.name==='joint__reach'),bind=carriage.translation[2]+reach.translation[2];
const engage=plan.phases.find(p=>p.phase_id==='source_lift_attached'),expectedRelative=[0,0,sourcePose.position[0]-engage.from.position[0]-bind-engage.from.extension_m];vec(plan.reference_relative.translation,expectedRelative);near(expectedRelative[2],.5999999865889551);assert.deepEqual(plan.reference_relative.quaternion,[0,1,0,0]);near(plan.reference_relative.yaw_rad,Math.PI);assert.equal(plan.reference_relative.native_capture_required,true);
for(const prefix of ['source','target']){const connector=plan.phases.find(p=>p.phase_id===prefix+'_connector_high_retracted');near(connector.from.position[0],123.2);near(connector.to.position[0],123.15);near(connector.from.fork_top_m,.7);near(connector.to.fork_top_m,.7);near(connector.from.extension_m,0);near(connector.to.extension_m,0);const controlled=plan.phases.find(p=>p.phase_id===prefix+(prefix==='source'?'_controlled_insert':'_controlled_withdraw'));near(prefix==='source'?controlled.to.position[0]:controlled.from.position[0],124.2);near(controlled.from.fork_top_m,.18);near(controlled.to.fork_top_m,.18);near(controlled.from.extension_m,.4);near(controlled.to.extension_m,.4);}
positive.push('actual_GLB_bind_reference_relative_pi_preserves_worldyaw_explicit_5cm_connectors_and_engagement');
let boundaryChecks=0,maxBoundaryError=0;
function numericPose(s){return [...s.body.position,s.body.yaw_rad,s.joints.fork_top_m,s.joints.extension_m,s.joints.virtual_steer_rad,s.joints.rear_steer_rad.L,s.joints.rear_steer_rad.R,...Object.values(s.wheel_angles_rad),...s.cargo.position];}
const boundaries=new Set([0,plan.duration_s,...plan.phases.flatMap(p=>[p.start_s,p.end_s])]);
for(const phase of plan.phases)if(phase.kind==='route'){const preview=compileVehicleRoutePreview(bundle,plan.routes[phase.phase_id==='empty_approach'?'empty':'loaded']);for(const p of preview.phases){boundaries.add(phase.start_s+p.start_s);boundaries.add(phase.start_s+p.end_s);}}
for(const t of boundaries){const centre=sample(plan,t);for(const dt of [-1e-7,1e-7]){const edge=sample(plan,t+dt),a=numericPose(centre),b=numericPose(edge);a.forEach((v,i)=>{const e=Math.abs(v-b[i]);maxBoundaryError=Math.max(maxBoundaryError,e);assert(e<1e-5,`Boundary ${t} component ${i}: ${e}`);});angle(centre.cargo.yaw_rad,edge.cargo.yaw_rad,1e-5);boundaryChecks++;}}
const attach=plan.phases.find(p=>p.phase_id==='source_lift_attached').start_s,release=plan.phases.find(p=>p.phase_id==='target_controlled_withdraw').start_s;
vec(sample(plan,attach).cargo.position,sourcePose.position);vec(sample(plan,release).cargo.position,targetPose.position);angle(sample(plan,attach).cargo.yaw_rad,sourcePose.yaw_rad);angle(sample(plan,release).cargo.yaw_rad,targetPose.yaw_rad);
const frames=[];let seed=172;for(let i=0;i<180;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;frames.push(seed/2**32*plan.duration_s);}frames.push(...boundaries,-10,plan.duration_s+10,attach,release);
const snapshots=new Map(frames.map(t=>[t,JSON.stringify(sample(plan,t))]));
for(const t of [...frames].reverse().concat(frames)){const s=sample(plan,t);assert.equal(JSON.stringify(s),snapshots.get(t));assert.equal(s.cargo.handling_unit_id,hu.handling_unit_id);assert.equal(s.cargo.quantity_units,24);assert.equal(s.cargo.gross_mass_kg,455);assert.equal(s.cargo.scale,1);assert.equal(s.population.handling_units,530);assert.equal(s.population.units,12256);near(s.population.gross_mass_kg,9403.85);assert.equal(s.population.workers,24);assert.equal(s.population.vehicles,2);assert.equal(s.cargo.logical_owner,t<attach?'slot:'+sourceSlot.slot_id:t<release?'vehicle:FL02':'slot:'+targetSlot.slot_id);assert.equal(s.engine_operation,false);assert.equal(s.physical_join,false);assert.equal(s.native_orientation_and_clearance_admission_required,true);assert.equal(s.native_admission_requires,true);assert.equal(s.completed_jobs,0);assert.deepEqual(s.actual_events,[]);}
assert.deepEqual(sample(plan,-1),sample(plan,0));assert.deepEqual(sample(plan,plan.duration_s+1),sample(plan,plan.duration_s));vec(sample(plan,plan.duration_s).body.position,nodes[targetSlot.vehicle_node_index].world_pos);
positive.push('all_plan_and_internal_route_boundaries_body_joints_wheels_cargo_continuous','attach_release_worldpose_conservation_one_logical_owner','random_reverse_roundtrip_repeat_endpoint_hold_and_explicit_reset_seeks');
// A full turn has the same endpoint orientation: inspect raw headings and interior motion too.
const yawQuaternion=yaw=>[0,Math.sin(yaw/2),0,Math.cos(yaw/2)],quaternionNear=(a,b)=>near(Math.abs(a.reduce((sum,v,i)=>sum+v*b[i],0)),1,1e-10);
let handlingHeadingChecks=0,routeHeadingChecks=0,angularVelocityChecks=0,maxHandlingAngularVelocity=0,previousPhase=null;
for(const phase of plan.phases){
 if(previousPhase)near(phase.from.yaw_rad,previousPhase.to.yaw_rad);
 const preview=phase.kind==='route'?compileVehicleRoutePreview(bundle,plan.routes[phase.phase_id==='empty_approach'?'empty':'loaded']):null;
 const first=preview?.sample(0),turnOffset=first?Math.round((phase.from.yaw_rad-first.yaw_rad)/(2*Math.PI))*2*Math.PI:0;
 if(first){near(phase.from.yaw_rad,first.yaw_rad+turnOffset);near(phase.to.yaw_rad,preview.sample(preview.duration_s).yaw_rad+turnOffset);}
 else near(phase.to.yaw_rad,phase.from.yaw_rad);
 let previous=null,travelledAngle=0;
 for(let i=0;i<=256;i++){
  const t=phase.start_s+(phase.end_s-phase.start_s)*i/256,s=sample(plan,t),q=yawQuaternion(s.body.yaw_rad);
  if(preview){near(s.body.yaw_rad,preview.sample(t-phase.start_s).yaw_rad+turnOffset);routeHeadingChecks++;}
  else {
   near(s.body.yaw_rad,phase.from.yaw_rad);near(s.joints.virtual_steer_rad,0);near(s.joints.rear_steer_rad.L,0);near(s.joints.rear_steer_rad.R,0);
   quaternionNear(yawQuaternion(s.cargo.yaw_rad),yawQuaternion((phase.phase_id.startsWith('source')?sourcePose:targetPose).yaw_rad));
   if(previous){const dt=t-previous.at_s,rawVelocity=Math.abs(s.body.yaw_rad-previous.body.yaw_rad)/dt,pq=yawQuaternion(previous.body.yaw_rad),physicalVelocity=2*Math.atan2(Math.abs(pq[3]*q[1]-pq[1]*q[3]),Math.abs(pq[3]*q[3]+pq[1]*q[1]))/dt;near(rawVelocity,0);near(physicalVelocity,0);maxHandlingAngularVelocity=Math.max(maxHandlingAngularVelocity,rawVelocity,physicalVelocity);travelledAngle+=Math.abs(s.body.yaw_rad-previous.body.yaw_rad);angularVelocityChecks++;}
   handlingHeadingChecks++;
  }
  if(t>=attach&&t<release){const relative=plan.reference_relative.quaternion,world=[0,q[3]*relative[1]+q[1]*relative[3],0,q[3]*relative[3]-q[1]*relative[1]];quaternionNear(yawQuaternion(s.cargo.yaw_rad),world);near(s.cargo.yaw_rad-s.body.yaw_rad,Math.PI);}
  previous=s;
 }
 if(!preview)near(travelledAngle,0);
 previousPhase=phase;
}
near(plan.phases.find(p=>p.phase_id==='source_connector_high_retracted').from.yaw_rad,-3*Math.PI/2);
positive.push('dense_raw_handling_headings_zero_angular_motion_and_source_target_world_quaternions','unwrapped_route_offsets_and_relative_pi_preserved_across_all_phase_joins');
// Independently reconstruct rolling offsets and carried transforms at interior samples.
let rolling={front_L:0,front_R:0,rear_L:0,rear_R:0},interiorChecks=0;
for(const phase of plan.phases){
 const preview=phase.kind==='route'?compileVehicleRoutePreview(bundle,plan.routes[phase.phase_id==='empty_approach'?'empty':'loaded']):null;
 const signed=(phase.to.position[0]-phase.from.position[0])*Math.sin(phase.from.yaw_rad)+(phase.to.position[2]-phase.from.position[2])*Math.cos(phase.from.yaw_rad);
 for(const u of [0,.13,.5,.87,1]){const t=phase.start_s+(phase.end_s-phase.start_s)*u,s=sample(plan,t),smooth=u*u*(3-2*u);
  if(preview){const p=preview.sample(t-phase.start_s),offset=phase.from.yaw_rad-preview.sample(0).yaw_rad;vec(s.body.position,p.position);near(s.body.yaw_rad,p.yaw_rad+offset);for(const key of Object.keys(rolling))near(s.wheel_angles_rad[key],rolling[key]+p.wheel_angles_rad[key]);}
  else for(const key of Object.keys(rolling))near(s.wheel_angles_rad[key],rolling[key]+signed*smooth/(key.startsWith('front')?.3:.225));
  if(t>=attach&&t<release){const local=plan.reference_relative.translation,localZ=bind+s.joints.extension_m+local[2],yaw=s.body.yaw_rad;vec(s.cargo.position,[s.body.position[0]+Math.cos(yaw)*local[0]+Math.sin(yaw)*localZ,s.joints.fork_top_m+local[1],s.body.position[2]-Math.sin(yaw)*local[0]+Math.cos(yaw)*localZ]);angle(s.cargo.yaw_rad,yaw+Math.PI);assert(Math.abs(Math.atan2(Math.sin(s.cargo.yaw_rad-yaw),Math.cos(s.cargo.yaw_rad-yaw)))>3);}
  interiorChecks++;
 }
 const end=preview?.sample(preview.duration_s);for(const key of Object.keys(rolling))rolling[key]+=end?end.wheel_angles_rad[key]:signed/(key.startsWith('front')?.3:.225);
}
positive.push('independent_route_and_straight_signed_wheel_offsets_and_carried_world_transforms');
const required=['actor:F02','vehicle:FL02','HU:'+hu.handling_unit_id,'slot:'+targetSlot.slot_id,'handling-space:'+sourceSlot.slot_id,'handling-space:'+targetSlot.slot_id];
const groups=[...new Set(Object.values(routeReports).flatMap(r=>r.arcs.flatMap(id=>arcById.get(id).source_reservation_group_ids)))];assert(groups.length>0);required.push(...groups);
assert.equal(new Set(plan.intervals.map(r=>r.resource_id)).size,plan.intervals.length);for(const id of required)assert(plan.intervals.some(r=>r.resource_id===id));
for(const r of plan.intervals){assert.equal(typeof r.start_s,'number');assert.equal(typeof r.end_s,'number');assert(Number.isFinite(r.start_s)&&Number.isFinite(r.end_s)&&r.start_s>=0&&r.end_s>r.start_s&&r.end_s<=plan.duration_s);assert.equal(r.capacity,1);assert.equal(r.quantity,1);assert.equal(r.exclusive,true);assert.equal(r.semantics,'planned_only_half_open');}
assert.equal(plan.resource_validation_before_route_cost,true);assert.equal(plan.actual_reservations,0);assert.equal(plan.cost_evaluated,false);assert.deepEqual(plan.actual_events,[]);
positive.push('finite_exclusive_half_open_planned_resources_real_graph_groups_no_actual_acquisition');
function frozen(v,seen=new Set()){if(!v||typeof v!=='object'||seen.has(v))return;seen.add(v);assert(Object.isFrozen(v));for(const child of Object.values(v))frozen(child,seen);}frozen(plan);frozen(sample(plan,attach));assert.throws(()=>{plan.reference_relative.yaw_rad=0;},TypeError);assert.throws(()=>{plan.physical_join=true;},TypeError);assert.throws(()=>{plan.completed_jobs=1;},TypeError);assert.throws(()=>{sample(plan,attach).cargo.position[0]=0;},TypeError);assert.equal(JSON.stringify(bundle),before);
positive.push('deeply_immutable_owned_results_request_copy_and_unchanged_canonical_bundle');
function rejects(label,value,reason,...bindings){const b=bindings.length>0?bindings[0]:bundle,c=bindings.length>1?bindings[1]:catalogue,p=bindings.length>2?bindings[2]:policy;const r=compile(b,c,p,value);assert.equal(r.ok,false,label);if(reason)assert.equal(r.reason,reason,label);assert.equal(r.plan,null);assert.equal(r.cost_evaluated,false);negative.push({case_id:label,reason:r.reason});}
for(const value of [null,true,false,0,1,'request',[],NaN,Infinity])rejects('wrong_request_primitive_'+String(value),value,'INVALID_REQUEST');
for(const key of Object.keys(request))for(const value of [null,true,false,0,NaN,Infinity,[],{}])rejects('strict_'+key+'_'+String(value),{...request,[key]:value},'INVALID_REQUEST');
for(const key of ['cargo','route','arc_ids','transform','speed','duration_s','scale','quantity_units','gross_mass_kg','relative_yaw_rad','reference_relative','source_hashes','proof','physical_join','engine_operation','completed_jobs','at_s'])rejects('forbidden_override_'+key,{...request,[key]:key==='relative_yaw_rad'?0:true},'INVALID_REQUEST');
rejects('unknown_HU',{...request,handling_unit_id:'fake'},'UNKNOWN_HU');rejects('wrong_pair',{...request,vehicle_id:'FL01'},'WRONG_PAIR');rejects('other_original_pair',{...request,actor_id:'F01',vehicle_id:'FL01'},'WRONG_PAIR');rejects('unknown_actor',{...request,actor_id:'fake'},'WRONG_PAIR');rejects('unknown_target',{...request,destination_slot_id:'fake'},'UNKNOWN_SLOT');
rejects('frozen_structural_bundle',request,'INVALID_SOURCE',Object.freeze({...bundle}));rejects('frozen_structural_catalogue',request,'INVALID_SOURCE',bundle,Object.freeze({...catalogue}));rejects('frozen_structural_policy',request,'INVALID_POLICY',bundle,catalogue,Object.freeze({...policy}));
for(const primitive of [null,undefined,true,false,1,'bundle',NaN])rejects('invalid_bundle_'+String(primitive),request,'INVALID_SOURCE',primitive);
for(const primitive of [null,undefined,true,false,1,'catalogue'])rejects('invalid_catalogue_'+String(primitive),request,'INVALID_SOURCE',bundle,primitive);
for(const primitive of [null,undefined,true,false,1,'policy'])rejects('invalid_policy_'+String(primitive),request,'INVALID_POLICY',bundle,catalogue,primitive);
const occupied=stock.find(h=>h.handling_unit_id!==hu.handling_unit_id&&slots.find(s=>s.slot_id===h.location.slot_id).allowed_cargo_archetype_ids.includes(hu.archetype_id));assert(occupied);rejects('occupied_target',{...request,destination_slot_id:occupied.location.slot_id},'SLOT_OCCUPIED');
const reserve=slots.find(s=>s.reserve_only),blocked=slots.find(s=>s.retrieval_blocked),incompatible=slots.find(s=>!s.reserve_only&&!s.retrieval_blocked&&!s.allowed_cargo_archetype_ids.includes(hu.archetype_id));assert(reserve&&incompatible);rejects('reserve_target',{...request,destination_slot_id:reserve.slot_id},'RESERVE_SLOT');rejects('incompatible_target',{...request,destination_slot_id:incompatible.slot_id},'CARGO_CLASS_FORBIDDEN');
if(blocked)rejects('blocked_target',{...request,destination_slot_id:blocked.slot_id},blocked.reserve_only?'RESERVE_SLOT':'RETRIEVAL_BLOCKED');
else {const forged=structuredClone(bundle);forged.layout.slots.find(s=>s.slot_id===request.destination_slot_id).retrieval_blocked=true;const deepFreeze=v=>{if(v&&typeof v==='object'){Object.values(v).forEach(deepFreeze);Object.freeze(v);}return v;};rejects('blocked_target_unissued_source',request,'INVALID_SOURCE',deepFreeze(forged));}
rejects('wrong_pair_before_occupied_target',{...request,vehicle_id:'FL01',destination_slot_id:occupied.location.slot_id},'WRONG_PAIR');
for(const value of [true,false,null,'0',NaN,Infinity,-Infinity,{},[]]){assert.throws(()=>sample(plan,value),e=>e instanceof PalletTransferError&&e.reason==='INVALID_TIME');assert.throws(()=>plan.sample(value),e=>e instanceof PalletTransferError&&e.reason==='INVALID_TIME');negative.push({case_id:'invalid_sample_time_'+String(value),reason:'INVALID_TIME'});}
for(const forged of [Object.freeze({...plan}),Object.freeze({...plan,reference_relative:{...plan.reference_relative,yaw_rad:0}}),Object.freeze({...plan,physical_join:true}),Object.freeze({...plan,engine_operation:true,completed_jobs:1})]){assert(!isPlan(forged));assert.throws(()=>sample(forged,0),e=>e.reason==='INVALID_PLAN');negative.push({case_id:'forged_plan_'+negative.length,reason:'INVALID_PLAN'});}
assert(!isPlan(plan,Object.freeze({...bundle})));assert(!isPlan(plan,bundle,Object.freeze({...catalogue})));assert(!isPlan(plan,bundle,catalogue,Object.freeze({...policy})));
await assert.rejects(()=>validateRoutePolicy(policyText+' ',bundle),/POLICY_HASH_MISMATCH/);negative.push({case_id:'stale_policy_bytes',reason:'POLICY_HASH_MISMATCH'});
for(const [label,mutate] of [['bool_units',f=>{f.inputs.initial_stock[0].quantity_units=true;}],['bool_mass',f=>{f.inputs.initial_stock[0].gross_mass_kg=true;}],['bool_pose',f=>{f.inputs.initial_stock[0].location.placement.bottom_y_m=true;}],['unregistered_fixture',f=>{f.fixture_id='fake';}],['stale_fixture',f=>{f.inputs.initial_stock[0].quantity_units++;}]]){const f=JSON.parse(texts.fixture);mutate(f);await assert.rejects(()=>adaptWarehouseV3({...texts,fixture:JSON.stringify(f)}));negative.push({case_id:label,reason:'canonical_adapter_rejection'});}
await assert.rejects(()=>registerWarehouseActionCatalogue(bundle,async p=>{const b=await reader.readSource(p);if(p.endsWith('pallet-pickup-cycle.json'))b[0]^=1;return b;}),e=>e.reason==='SOURCE_HASH_MISMATCH');negative.push({case_id:'stale_registered_pickup_proof',reason:'SOURCE_HASH_MISMATCH'});
await assert.rejects(()=>reader.readSource('unregistered-proof'),e=>e instanceof ActionSourceError&&e.reason==='UNKNOWN_SOURCE');negative.push({case_id:'unregistered_proof',reason:'UNKNOWN_SOURCE'});
reader.dispose();
// Source drift during this run is a failure, never silently rewritten into the source pack.
for(const [p,h] of Object.entries(input_hashes))assert.equal(sha(await readFile(path.join(root,p))),h,'Concurrent source drift: '+p);
const report={task_id:'W05.4.1',cpu_gate_passed:true,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,physical_join:false,native_orientation_and_clearance_admission_required:true,native_admission_requires:true,completed_jobs:0,actual_reservations:0,actual_events:0,graph_access:'Verify graph generation 2026-11-08T05:55:56Z; new module/checker not tracked; exact source fallback',positive_cases:positive,negative_cases:negative,routes:routeReports,source_pose:sourcePose,target_pose:targetPose,reference_relative:plan.reference_relative,phases:plan.phases,planned_intervals:plan.intervals,graph_reservation_groups:groups,boundary_checks:boundaryChecks,interior_pose_and_wheel_checks:interiorChecks,handling_raw_heading_checks:handlingHeadingChecks,route_raw_heading_checks:routeHeadingChecks,handling_angular_velocity_checks:angularVelocityChecks,maximum_handling_angular_velocity_rad_s:maxHandlingAngularVelocity,maximum_boundary_numeric_error:maxBoundaryError,random_seek_times:frames.length,blocked_target_source_count:slots.filter(s=>s.retrieval_blocked).length,blocked_target_limit:blocked?null:'Canonical source has no blocked slot; forged blocked source rejected by issued-bundle guard, no fabricated admitted fixture.',population:sample(plan,0).population,duration_s:plan.duration_s,input_hashes:Object.fromEntries(Object.entries(input_hashes).sort(([a],[b])=>a.localeCompare(b))),limits:'Pure immutable absolute reference only. No native orientation/contact/obstacle/driver/fork/pallet/C08 clearance or Scene acceptance. No actual engine/action scheduling/resource acquisition/job completion. Root accepts child; parent W05.4 remains open.'};
const bytes=JSON.stringify(report,null,2)+'\n';assert(!bytes.includes('\r'));
if(process.argv.includes('--check-only')){const a=await stat(output),original=await readFile(output);assert.equal(original.toString('utf8'),bytes,'Stale evidence; check-only writes nothing');const b=await stat(output);assert.equal(a.mtimeMs,b.mtimeMs);assert.deepEqual(await readFile(output),original);}
else await writeFile(output,bytes,'utf8');
console.log(JSON.stringify({cpu_gate_passed:true,check_only:process.argv.includes('--check-only'),positive_cases:positive.length,negative_cases:negative.length,boundary_checks:boundaryChecks,resources:plan.intervals.length,routes:routeReports,duration_s:plan.duration_s,evidence_bytes:Buffer.byteLength(bytes),evidence_sha256:sha(bytes),native_admission_required:true}));
