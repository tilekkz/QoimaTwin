import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';

// This checks geometry/ownership inspection, never a physical transfer or stock operation.
if(process.env.QOIMA_VISIBLE_TESTS==='1')throw Error('Muted headless localhost only.');
const out='../assets/v3/iterations/warehouse/W04.2/browser',url='http://127.0.0.1:4173/warehouse-v3.html';
await mkdir(out,{recursive:true});
const names=['warehouseAdapter.ts','warehouseTypes.ts','warehouseRouting.ts','warehouseRoutePose.ts','warehouseRoutePreview.ts','warehousePage.ts','warehouseScene.ts','warehouseCargo.ts','warehouseCargoGeometry.ts','warehouse.css','warehouseAssetBindings.json','workerRegistry.ts','workerProfiles.ts','workerRoles.ts','seatedDriver.ts'];
const files=['frontend/warehouse-v3.html','frontend/vite.config.ts',...names.map(p=>'frontend/src/adaptive-v3/'+p),'frontend/src/adaptive-v3/staffRegistry.css','frontend/public/data/v3/warehouse-fixture-v3.json','frontend/public/data/v3/route-policy-v3.json','frontend/public/data/adaptive-v3/layout-manifest.json','frontend/public/data/v3/worker-registry-v3.json','frontend/public/data/v3/worker-profiles-v3.json','frontend/tools/check-warehouse-cargo-browser-v3.mjs','docs/adaptive-v3/evidence/W04.1-checks.json'];
const bindings=JSON.parse(await readFile('src/adaptive-v3/warehouseAssetBindings.json','utf8'));
for(const [id,binding]of Object.entries(bindings))files.push(id==='seated-driver-pose'?'frontend/public/'+binding.path:'frontend/public/models/v3/'+id+'.glb');
const hash=async p=>createHash('sha256').update(await readFile('../'+p)).digest('hex');
const input_hashes=Object.fromEntries(await Promise.all(files.map(async p=>[p,await hash(p)])));
const placementProof=JSON.parse(await readFile('../docs/adaptive-v3/evidence/W04.1-checks.json','utf8'));
const fixture=JSON.parse(await readFile('public/data/v3/warehouse-fixture-v3.json','utf8'));
const layout=JSON.parse(await readFile('public/data/adaptive-v3/layout-manifest.json','utf8'));
const sourceSlots=layout.data.storage.slots.rows.map(row=>Object.fromEntries(layout.data.storage.slots.columns.map((name,i)=>[name,row[i]])));
const frames=[],checks={},fatal=[],unexpected=[],requests=[],nativeFailures=[],negativeCases=[],relocations=[];
let initialNative=[],failure,browser,server,lifecycle,maximumDimensionError=0,maximumLocalBoundError=0,maximumBottomGap=0,maximumContactGap=0;
const started=Date.now();
async function bounded(p,ms=5000){let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Bounded operation timed out')),ms);})]);}finally{clearTimeout(timer);}}
function alive(){if(!server)return false;try{process.kill(server.process().pid,0);return true;}catch(e){if(e.code==='ESRCH')return false;throw e;}}
function verifyNative(item,stage){
 const reasons=[],d=item.dimensions_xyz_m,min=item.bounds_cargo_local.min,max=item.bounds_cargo_local.max;
 const dimensionError=Math.max(...d.map((n,i)=>Math.abs(max[i]-min[i]-n)));
 const boundError=Math.max(...min.map((n,i)=>Math.abs(n-[ -d[0]/2,0,-d[2]/2 ][i])),...max.map((n,i)=>Math.abs(n-[d[0]/2,d[1],d[2]/2][i])));
 maximumDimensionError=Math.max(maximumDimensionError,dimensionError);maximumLocalBoundError=Math.max(maximumLocalBoundError,boundError);maximumBottomGap=Math.max(maximumBottomGap,Math.abs(item.actual_bottom_gap_m));maximumContactGap=Math.max(maximumContactGap,item.maximum_contact_gap_m);
 if(dimensionError>2e-6)reasons.push('Native dimensions differ by '+dimensionError+'m');
 if(boundError>2e-6)reasons.push('Native local bounds differ by '+boundError+'m');
 if(Math.abs(item.actual_bottom_gap_m)>2e-6)reasons.push('Bottom support-plane gap '+item.actual_bottom_gap_m+'m');
 if(!(item.native_contact_area_sum_m2>1e-8))reasons.push('No positive native horizontal contact area');
 if(item.maximum_contact_gap_m>2e-6)reasons.push('Native contact-plane gap '+item.maximum_contact_gap_m+'m');
 if(!item.geometric_centre_inside_support_hull)reasons.push('Footprint centre outside native support hull');
 if(item.model_scale_factor!==1||item.mesh_parts<1||item.vertices<1||item.mesh_instances.length!==item.mesh_parts)reasons.push('Missing or scaled native instance');
 if(item.source_kind!=='visual_fixture'||item.engine_operation!==false)reasons.push('Wrong operation scope');
 if(reasons.length)nativeFailures.push({stage,handling_unit_id:item.handling_unit_id,reasons});
}
try{
 server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio'],timeout:30000});
 browser=await chromium.connect(server.wsEndpoint());
 const context=await browser.newContext({viewport:{width:1440,height:1100},hasTouch:true,reducedMotion:'reduce'}),page=await context.newPage();page.setDefaultTimeout(15000);
 page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>fatal.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('CONTEXT_LOST_WEBGL'))unexpected.push(m.text());});page.on('response',r=>{if(r.status()>=400)unexpected.push({url:r.url(),status:r.status()});});
 const snapshot=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.snapshot());
 const cargoState=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.cargoBindings());
 const apply=changes=>page.evaluate(changes=>window.__QOIMA_WAREHOUSE_V3__.applyCargoBindings(changes),changes);
 const inspect=id=>page.evaluate(id=>window.__QOIMA_WAREHOUSE_V3__.inspectCargo(id),id);
 const reset=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.resetCargoBindings());
 const settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 async function capture(name){await settle();const file=name+'.png';await page.screenshot({path:out+'/'+file});const s=await snapshot();frames.push({file,state:{phase:s.phase,selection:s.selection,source_kind:s.source_kind,engine_operation:s.engine_operation,summary:s.summary,scene:s.scene?{...s.scene,stock_positions:undefined}:null},selected_card:await page.locator('#warehouse-selection').innerText()});}
 function verifyConservation(rows){assert.equal(rows.length,530);assert.equal(new Set(rows.map(r=>r.handling_unit_id)).size,530);assert.equal(rows.reduce((sum,r)=>sum+r.cargo.quantity_units,0),12256);assert(Math.abs(rows.reduce((sum,r)=>sum+r.cargo.gross_mass_kg,0)-9403.85)<1e-7);for(const r of rows){const original=fixture.inputs.initial_stock.find(h=>h.handling_unit_id===r.handling_unit_id);assert.deepEqual(r.cargo,original);assert.equal(r.model_scale_factor,1);assert.equal(r.destination.kind,'storage_slot');}}
 await page.goto(url);await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready',null,{timeout:50000});
 const initial=await cargoState(),initialText=JSON.stringify(initial),initialScene=(await snapshot()).scene;
 verifyConservation(initial);assert.equal(initialScene.workers,24);assert.equal(initialScene.modules,132);assert.equal(initialScene.cargo_binding_count,530);assert.equal(initialScene.completed_jobs,0);assert.equal(initialScene.actions_scheduled,0);
 initialNative=await bounded(page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.cargoBindings().map(item=>window.__QOIMA_WAREHOUSE_V3__.inspectCargo(item.handling_unit_id))),45000);
 assert.equal(initialNative.length,530);for(const item of initialNative)verifyNative(item,'initial');
 const nativeById=new Map(initialNative.map(item=>[item.handling_unit_id,item]));
 checks.all530_native_instances_and_immutable_HU_metadata=true;
 for(const archetype of fixture.inputs.archetypes){const item=initial.find(r=>r.cargo.archetype_id===archetype.archetype_id);await page.locator('#warehouse-cargo').selectOption(item.handling_unit_id);assert.equal((await snapshot()).scene.highlight_HU,item.handling_unit_id);await capture('initial-'+archetype.archetype_id);}
 checks.eight_actual_family_views_and_ID_cards=true;
 const at=(id,slot)=>({handling_unit_id:id,destination:{kind:'storage_slot',slot_id:slot}}),sample=initial[0],other=initial.find(r=>r.cargo.archetype_id===sample.cargo.archetype_id&&r.handling_unit_id!==sample.handling_unit_id);
 async function reject(name,changes,reason){const before=JSON.stringify(await cargoState()),scene=(await snapshot()).scene;const result=await apply(changes);assert.equal(result.ok,false,name);assert.equal(result.reason,reason,name);assert.equal(result.cost_evaluated,false);assert.equal(JSON.stringify(await cargoState()),before,name);assert.deepEqual((await snapshot()).scene.stock_positions,scene.stock_positions,name);negativeCases.push({case:name,reason,rejected:true});}
 await reject('occupied_slot',[at(sample.handling_unit_id,other.destination.slot_id)],'SLOT_OCCUPIED');
 await reject('unknown_HU',[at('invented',sample.destination.slot_id)],'UNKNOWN_HU');
 await reject('unknown_slot',[at(sample.handling_unit_id,'invented')],'UNKNOWN_SLOT');
 await reject('duplicate_HU',[at(sample.handling_unit_id,sample.destination.slot_id),at(sample.handling_unit_id,sample.destination.slot_id)],'DUPLICATE_HU');
 await reject('reserve_slot',[at(sample.handling_unit_id,sourceSlots.find(s=>s.reserve_only).slot_id)],'RESERVE_SLOT');
 await reject('wrong_family',[at(sample.handling_unit_id,sourceSlots.find(s=>s.allowed_cargo_archetype_ids.includes('IBC')).slot_id)],'CARGO_CLASS_FORBIDDEN');
 await reject('dimension_scale_override',[{...at(sample.handling_unit_id,sample.destination.slot_id),model_scale_factor:.9}],'INVALID_REQUEST');
 await reject('destination_transform_override',[{handling_unit_id:sample.handling_unit_id,destination:{...sample.destination,position:[0,0,0]}}],'INVALID_REQUEST');
 await reject('unreviewed_carrier',[{handling_unit_id:sample.handling_unit_id,destination:{kind:'vehicle',vehicle_id:'FL01',anchor_id:'forks'}}],'PHYSICAL_HOLDER_NOT_REGISTERED');
 checks.invalid_changes_are_atomic_without_mesh_or_stock_mutation=true;
 for(const target of placementProof.compatible_free_relocations){
  const id=target.handling_unit_id,before=await inspect(id),admission=await apply([at(id,target.slot_id)]);assert.equal(admission.ok,true);const moved=await inspect(id);verifyNative(moved,'relocated');
  assert.deepEqual(moved.mesh_instances,before.mesh_instances);assert.deepEqual(moved.dimensions_xyz_m,before.dimensions_xyz_m);assert.equal(moved.gross_mass_kg,before.gross_mass_kg);assert.equal(moved.quantity_units,before.quantity_units);assert.deepEqual(moved.position,target.position);assert.equal(moved.yaw_rad,target.yaw_rad);verifyConservation(await cargoState());
  await page.locator('#warehouse-cargo').selectOption(id);assert.equal((await snapshot()).scene.highlight_HU,id);assert((await page.locator('#warehouse-selection').innerText()).includes(target.slot_id),'Card must show current destination');
  if(['SMALL_CARTON','LONG_BUNDLE'].includes(target.archetype_id))await capture('relocated-'+target.archetype_id);
  if(target.archetype_id==='SMALL_CARTON'){
   // Clear only the select value; the camera stays focused. A native canvas hit must set it back.
   await page.locator('#warehouse-cargo').selectOption('');const box=await page.locator('#warehouse-viewport canvas').boundingBox(),upY=Math.sqrt(1-(1.15/Math.hypot(.9,1.15,1))**2),vertical=(moved.dimensions_xyz_m[1]/2-.4)*upY;
   await page.mouse.click(box.x+box.width/2,box.y+box.height/2-vertical*box.width/4.5);assert.equal(await page.locator('#warehouse-cargo').inputValue(),id,'Raycast must preserve moved HU identity');checks.native_canvas_raycast_tracks_rebound_instance=true;
  }
  await reset();assert.equal(JSON.stringify(await cargoState()),initialText);const restored=await inspect(id);assert.deepEqual(restored.mesh_instances,nativeById.get(id).mesh_instances);assert.deepEqual(restored.bounds_world,nativeById.get(id).bounds_world);relocations.push({archetype_id:target.archetype_id,handling_unit_id:id,slot_id:target.slot_id,native:moved});
 }
 assert.equal(relocations.length,8);checks.all_eight_families_rebind_existing_instances_without_scaling=true;checks.current_destination_card_highlight_and_original_reset=true;
 const swap=[at(sample.handling_unit_id,other.destination.slot_id),at(other.handling_unit_id,sample.destination.slot_id)];assert.equal((await apply(swap)).ok,true);verifyConservation(await cargoState());
 for(const row of [sample,other]){const actual=await inspect(row.handling_unit_id);verifyNative(actual,'atomic-swap');assert.deepEqual(actual.mesh_instances,nativeById.get(row.handling_unit_id).mesh_instances);}
 checks.atomic_two_HU_swap_preserves_instance_identity=true;
 await reset();await reset();assert.equal(JSON.stringify(await cargoState()),initialText);assert.deepEqual((await snapshot()).scene.stock_positions,initialScene.stock_positions);checks.repeated_absolute_reset_has_no_instance_drift=true;
 await page.locator('#warehouse-cargo').selectOption(sample.handling_unit_id);await capture('restored-original');
 const finalScene=(await snapshot()).scene;assert.deepEqual(finalScene.worker_ids,initialScene.worker_ids);assert.deepEqual(finalScene.vehicle_poses,initialScene.vehicle_poses);assert.equal(finalScene.actions_scheduled,0);assert.equal(finalScene.completed_jobs,0);checks.original_workers_vehicles_and_zero_completions_unchanged=true;
 assert(requests.every(p=>p.startsWith('http://127.0.0.1:4173/')));assert(!requests.some(p=>p.includes('/api/')));assert.equal(await page.locator('audio,video').count(),0);checks.local_only_muted_no_backend_or_media=true;
 assert.deepEqual(fatal,[]);assert.deepEqual(unexpected,[]);await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.dispose());assert.equal(await page.locator('#warehouse-viewport canvas').count(),0);assert.equal((await snapshot()).phase,'disposed');checks.explicit_dispose_removes_renderer=true;
 await page.close();await context.close();
 if(nativeFailures.length)throw Error('Native cargo geometry/support failures: '+nativeFailures.length+'; see native_failures in browser-checks.json');checks.all530_native_bounds_and_horizontal_support_contacts=true;
}catch(e){failure=e.stack||String(e);}
finally{
 if(browser)await bounded(browser.close()).catch(()=>{});if(server){await bounded(server.close()).catch(()=>{});for(let i=0;i<20&&alive();i++)await new Promise(r=>setTimeout(r,100));if(alive()){await bounded(server.kill()).catch(()=>{});for(let i=0;i<20&&alive();i++)await new Promise(r=>setTimeout(r,100));}}
 lifecycle={owned_pid:server?.process().pid??null,terminated:!alive(),elapsed_ms:Date.now()-started};if(!lifecycle.terminated)failure??='Owned Chrome did not terminate';
 for(const p of files)if(await hash(p)!==input_hashes[p])failure??='Input changed during cargo QA '+p;
 const report={passed:!failure,source_kind:'visual_fixture',engine_operation:false,visible:false,url,input_hashes,frames,checks,initial_native:initialNative,native_failures:nativeFailures,negative_cases:negativeCases,relocations,maximum_dimension_error_m:maximumDimensionError,maximum_local_bound_error_m:maximumLocalBoundError,maximum_bottom_gap_m:maximumBottomGap,maximum_contact_gap_m:maximumContactGap,fatal,unexpected,lifecycle,failure,scope:'Actual same-instance storage binding and native horizontal triangle-contact/footprint-centre proxy only. No physical transfer action, traffic resource grant, strength/stability certification or actual engine run.'};
 await writeFile(out+'/browser-checks.json',JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({passed:report.passed,checks:Object.keys(checks).length,captures:frames.length,initial_native:initialNative.length,native_failures:nativeFailures.length,negative_cases:negativeCases.length,relocations:relocations.length,maximum_dimension_error_m:maximumDimensionError,maximum_local_bound_error_m:maximumLocalBoundError,maximum_bottom_gap_m:maximumBottomGap,maximum_contact_gap_m:maximumContactGap,lifecycle,failure}));
}
if(failure)process.exitCode=1;
