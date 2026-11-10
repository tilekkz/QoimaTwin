import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';

// W04.3 is paused physical pose inspection. No transfer, DES or engine operation is inferred.
if(process.env.QOIMA_VISIBLE_TESTS==='1')throw Error('Muted headless localhost only.');
const smoke=process.argv.includes('--smoke'),out='../assets/v3/iterations/warehouse/W04.3/'+(smoke?'browser-preview':'browser'),url='http://127.0.0.1:4173/warehouse-v3.html';
await mkdir(out,{recursive:true});
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const sourceNames=(await readdir('src/adaptive-v3')).filter(name=>/^warehouse/.test(name)&&/\.(ts|css|json)$/.test(name));
const files=['frontend/warehouse-v3.html','frontend/vite.config.ts',...sourceNames.map(name=>'frontend/src/adaptive-v3/'+name),...['workerRegistry.ts','workerProfiles.ts','workerRoles.ts','seatedDriver.ts','staffRegistry.css'].map(name=>'frontend/src/adaptive-v3/'+name),'frontend/public/data/v3/warehouse-fixture-v3.json','frontend/public/data/v3/route-policy-v3.json','frontend/public/data/adaptive-v3/layout-manifest.json','frontend/public/data/v3/worker-registry-v3.json','frontend/public/data/v3/worker-profiles-v3.json','frontend/tools/check-warehouse-holder-browser-v3.mjs'];
for(const filename of (await readdir('public/models/v3')).filter(name=>name.endsWith('.glb')))files.push('frontend/public/models/v3/'+filename);
for(const filename of (await readdir('public/data/v3')).filter(name=>/carry|support|vehicle-handling/.test(name)&&name.endsWith('.json')))files.push('frontend/public/data/v3/'+filename);
const input_hashes=Object.fromEntries(await Promise.all(files.map(async path=>[path,sha(await readFile('../'+path))])));
const fixture=JSON.parse(await readFile('public/data/v3/warehouse-fixture-v3.json','utf8'));
const checks={},frames=[],observations=[],negativeCases=[],fatal=[],unexpected=[],expected=[],requests=[];
const cases=[['actor-small','SMALL_CARTON','actor'],['cart-small','SMALL_CARTON','cart'],['belt-small','SMALL_CARTON','belt'],['belt-standard','STANDARD_CARTON','belt'],...['HEAVY_BOX','PALLET_LOAD','IBC','LONG_BUNDLE','DRUM','FRAGILE_CRATE'].map(id=>['vehicle-'+id,id,'vehicle'])];
const started=Date.now();let browser,server,lifecycle,failure,expecting=false,release=()=>{};
async function bounded(operation,ms=8000){let timer;try{return await Promise.race([operation,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Bounded operation timed out')),ms);})]);}finally{clearTimeout(timer);}}
function alive(){if(!server)return false;try{process.kill(server.process().pid,0);return true;}catch(error){if(error.code==='ESRCH')return false;throw error;}}
function verifyConservation(rows){
 assert.equal(rows.length,530);assert.equal(new Set(rows.map(row=>row.handling_unit_id)).size,530);
 assert.equal(rows.reduce((sum,row)=>sum+row.cargo.quantity_units,0),12256);assert(Math.abs(rows.reduce((sum,row)=>sum+row.cargo.gross_mass_kg,0)-9403.85)<1e-7);
 for(const row of rows){assert.equal(row.model_scale_factor,1);assert.deepEqual(row.cargo,fixture.inputs.initial_stock.find(hu=>hu.handling_unit_id===row.handling_unit_id));}
}
function verifyNative(item,kind){
 const d=item.dimensions_xyz_m,min=item.bounds_cargo_local.min,max=item.bounds_cargo_local.max;
 const boundsError=Math.max(...min.map((n,i)=>Math.abs(n-[-d[0]/2,0,-d[2]/2][i])),...max.map((n,i)=>Math.abs(n-[d[0]/2,d[1],d[2]/2][i])));
 assert(boundsError<2e-6,'Native local bounds '+boundsError+'m');assert.equal(item.model_scale_factor,1);assert(item.mesh_parts>0);assert(item.vertices>0);assert.equal(item.mesh_instances.length,item.mesh_parts);
 assert.equal(item.source_kind,'visual_fixture');assert.equal(item.engine_operation,false);
 if(kind==='actor'){
  assert.equal(item.contact_kind,'static_two_hand_side_clamp');assert.equal(item.horizontal_support_claimed,false);assert.equal(item.contacts.length,2);assert.deepEqual(item.contacts.map(contact=>contact.side),['L','R']);
  for(const contact of item.contacts){assert(contact.native_cargo_gap_m<2e-6,'Actual glove/HU cargo surface gap');assert(contact.native_glove_gap_m<2e-6,'Actual glove/HU glove surface gap');}
  assert.equal(Object.keys(item.joints).length,12);assert.equal(Object.keys(item.thumb_positions).length,2);for(const side of ['L','R'])assert.deepEqual(item.thumb_positions['joint__finger_thumb_'+side],[0,0,-.005]);assert(item.friction_assumption.includes('Synthetic'));
 }else{
  assert(Math.abs(item.actual_bottom_gap_m)<2e-6,'Bottom support plane gap');assert(item.native_contact_area_sum_m2>1e-8,'Positive native opposed horizontal contact area');assert(item.maximum_contact_gap_m<2e-6,'Horizontal contact gap');assert.equal(item.geometric_centre_inside_support_hull,true);
 }
 return boundsError;
}
function verifyActorHeading(pose,yaw,position){
 assert(pose&&Array.isArray(pose.quaternion)&&pose.quaternion.length===4,'Actual native actor pose is exposed');assert.deepEqual(pose.position,position,'Actor floor position is preserved');
 const [x,y,z,w]=pose.quaternion,forward=[2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y)];assert(Math.hypot(forward[0]-Math.sin(yaw),forward[1],forward[2]-Math.cos(yaw))<1e-10,'Actual actor outward/rest heading');
}
try{
 server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio'],timeout:30000});browser=await chromium.connect(server.wsEndpoint());
 const context=await browser.newContext({viewport:{width:1440,height:1100},hasTouch:true,reducedMotion:'reduce'}),page=await context.newPage();page.setDefaultTimeout(15000);
 page.on('request',request=>requests.push(request.url()));page.on('pageerror',error=>fatal.push(error.message));page.on('console',message=>{if(message.type()==='error'&&!message.text().includes('CONTEXT_LOST_WEBGL'))(expecting?expected:unexpected).push(message.text());});page.on('response',response=>{if(response.status()>=400)(expecting?expected:unexpected).push({url:response.url(),status:response.status()});});
 const snapshot=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.snapshot());
 const cargoState=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.cargoBindings());
 const holderState=async()=>{const s=await snapshot();return s.holder;};
 const activate=id=>page.evaluate(id=>window.__QOIMA_WAREHOUSE_V3__.activateHolder(id),id);
 const reset=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.resetHolders());
 const inspect=id=>page.evaluate(id=>window.__QOIMA_WAREHOUSE_V3__.inspectCargo(id),id);
 const ready=()=>page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready',null,{timeout:50000});
 const holderPhase=phase=>page.waitForFunction(phase=>window.__QOIMA_WAREHOUSE_V3__.snapshot().holder?.phase===phase,phase,{timeout:15000});
 const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 async function capture(name){await settle();const file=name+'.png';await page.screenshot({path:out+'/'+file});const s=await snapshot();frames.push({file,state:{...s,scene:s.scene?{...s.scene,stock_positions:undefined}:null},selected_card:await page.locator('#warehouse-selection').innerText()});}
 async function initial(){await page.goto(url);await ready();assert.equal((await snapshot()).phase,'ready');if(!await page.locator('#warehouse-holder-panel').evaluate(details=>details.open))await page.locator('#warehouse-holder-panel summary').click();}
 await initial();
 const original=await cargoState(),originalText=JSON.stringify(original),originalScene=(await snapshot()).scene,representatives=new Map();
 verifyConservation(original);assert.equal(originalScene.workers,24);assert.equal(originalScene.stock_HUs,530);assert.equal(originalScene.modules,132);assert.equal(originalScene.cargo_binding_count,530);assert.equal(originalScene.actions_scheduled,0);assert.equal(originalScene.completed_jobs,0);
 for(const [,archetype]of cases)if(!representatives.has(archetype)){const row=original.find(row=>row.cargo.archetype_id===archetype);representatives.set(archetype,await inspect(row.handling_unit_id));}
 assert(!requests.some(path=>/worker-manual\.glb|picking-cart-tote-fixture\.glb|long-cradle\.glb/.test(path)),'Support assets must remain lazy before first holder intent');checks.optional_support_kit_is_lazy_and_base_viewer_usable=true;
 let actorRestQuaternion;
 for(const [demo,archetype,kind]of cases){
  assert.equal(await activate(demo),true,demo);await settle();const s=await snapshot(),rows=await cargoState(),attached=rows.filter(row=>row.destination.kind!=='storage_slot');verifyConservation(rows);
  assert.equal(s.phase,'ready');assert.equal(s.scene.workers,24);assert.deepEqual(s.scene.worker_ids,originalScene.worker_ids);assert.equal(s.scene.stock_HUs,530);assert.equal(s.scene.actions_scheduled,0);assert.equal(s.scene.completed_jobs,0);assert.equal(attached.length,1,demo);const held=attached[0];assert.equal(held.destination.kind,kind);assert.equal(held.cargo.archetype_id,archetype);
  const native=await inspect(held.handling_unit_id),before=representatives.get(archetype);verifyNative(native,kind);assert.deepEqual(native.mesh_instances,before.mesh_instances,'Same native GPU UUID/index for '+demo);assert.deepEqual(native.dimensions_xyz_m,before.dimensions_xyz_m);assert.equal(native.gross_mass_kg,before.gross_mass_kg);assert.equal(native.quantity_units,before.quantity_units);
  if(kind==='actor'){verifyActorHeading(s.scene.holders.actor_pose,Math.PI/2,originalScene.actor_homes.P01.world_pos);assert(Math.abs(native.yaw_rad-Math.PI/2)<1e-10,'Same HU uses the actual outward actor frame');}
  assert((await page.locator('#warehouse-selection').innerText()).includes(held.handling_unit_id),'Current HU card');await capture(demo);
  observations.push({demo,kind,handling_unit_id:held.handling_unit_id,destination:held.destination,native,holder:s.holder,scene:s.scene?{...s.scene,stock_positions:undefined}:null});
  if(kind==='vehicle'){
   const beforeRoute=JSON.stringify(await cargoState()),vehiclePose=s.scene.vehicle_poses;const routeResult=await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activateRoute('F01-heavy'));assert.equal(routeResult,false,'Empty route must reject attached cargo');assert.equal(JSON.stringify(await cargoState()),beforeRoute);assert.deepEqual((await snapshot()).scene.vehicle_poses,vehiclePose);checks.empty_vehicle_routes_refuse_attached_cargo=true;
  }
  await reset();await reset();assert.equal(JSON.stringify(await cargoState()),originalText,'Absolute original restoration '+demo);const resetScene=(await snapshot()).scene;assert.equal(resetScene.workers,24);verifyActorHeading(resetScene.holders.actor_pose,3*Math.PI/2,originalScene.actor_homes.P01.world_pos);if(!actorRestQuaternion)actorRestQuaternion=resetScene.holders.actor_pose.quaternion;else assert.deepEqual(resetScene.holders.actor_pose.quaternion,actorRestQuaternion,'Exact restored actor quaternion');const restored=await inspect(held.handling_unit_id);assert.deepEqual(restored.mesh_instances,before.mesh_instances);assert.deepEqual(restored.bounds_world,before.bounds_world);
 }
 checks.all10_carrier_poses_same_HUs_24_workers_and_metadata=true;checks.all_six_vehicle_families_have_native_support=true;checks.cart_and_two_belt_classes_have_native_support=true;checks.outward_actor_heading_and_exact_original_rest_quaternion=true;checks.repeated_reset_restores_exact_storage_instance_bounds=true;
 if(!smoke){
 // Malformed raw binding input must remain atomic after the optional holder catalogue is registered.
 const small=original.find(row=>row.cargo.archetype_id==='SMALL_CARTON');
 for(const [name,change,reason]of [['unknown_anchor',{handling_unit_id:small.handling_unit_id,destination:{kind:'actor',actor_id:'P01',anchor_id:'invented'}},'PHYSICAL_HOLDER_NOT_REGISTERED'],['cargo_scale_override',{handling_unit_id:small.handling_unit_id,destination:{kind:'cart',cart_id:'C01',anchor_id:'upper-tote'},model_scale_factor:.5},'INVALID_REQUEST'],['holder_pose_override',{handling_unit_id:small.handling_unit_id,destination:{kind:'cart',cart_id:'C01',anchor_id:'upper-tote',position:[0,0,0]}},'INVALID_REQUEST']]){
  const before=JSON.stringify(await cargoState()),result=await page.evaluate(change=>window.__QOIMA_WAREHOUSE_V3__.applyCargoBindings([change]),change);assert.equal(result.ok,false,name);assert.equal(result.reason,reason,name);assert.equal(JSON.stringify(await cargoState()),before,name);negativeCases.push({case:name,reason,rejected:true});
 }
 checks.malformed_binding_refusals_remain_atomic=true;
 // A second holder cannot borrow the one physical LONG kit; a rejected attempt restores the first.
 await activate('vehicle-LONG_BUNDLE');const heldLong=(await cargoState()).find(row=>row.destination.kind==='vehicle'),otherLong=original.find(row=>row.cargo.archetype_id==='LONG_BUNDLE'&&row.handling_unit_id!==heldLong.handling_unit_id),longBefore=JSON.stringify(await cargoState()),longProof=await inspect(heldLong.handling_unit_id);
 assert(otherLong,'Two original LONG HUs exist for shared-kit refusal');let result=await page.evaluate(change=>window.__QOIMA_WAREHOUSE_V3__.applyCargoBindings([change]),{handling_unit_id:otherLong.handling_unit_id,destination:{kind:'vehicle',vehicle_id:'FL02',anchor_id:'forks'}});assert.equal(result.ok,false);assert.equal(result.reason,'HOLDER_ATTACHMENT_UNAVAILABLE');assert.equal(JSON.stringify(await cargoState()),longBefore);assert.deepEqual(await inspect(heldLong.handling_unit_id),longProof);negativeCases.push({case:'single_LONG_kit_cannot_be_duplicated',reason:result.reason,rejected:true});checks.one_physical_LONG_kit_refuses_simultaneous_second_vehicle=true;
 // One atomic batch changes the live vehicle profile and returns the old exact HU to storage.
 const oldLong=original.find(row=>row.handling_unit_id===heldLong.handling_unit_id),ibc=original.find(row=>row.cargo.archetype_id==='IBC');result=await page.evaluate(changes=>window.__QOIMA_WAREHOUSE_V3__.applyCargoBindings(changes),[{handling_unit_id:oldLong.handling_unit_id,destination:oldLong.destination},{handling_unit_id:ibc.handling_unit_id,destination:{kind:'vehicle',vehicle_id:'FL01',anchor_id:'forks'}}]);assert.equal(result.ok,true);const switched=await inspect(ibc.handling_unit_id);verifyNative(switched,'vehicle');assert.deepEqual(switched.mesh_instances,representatives.get('IBC').mesh_instances);assert.equal((await snapshot()).scene.holders.vehicle_profiles.FL01,'IBC');verifyConservation(await cargoState());await reset();assert.equal(JSON.stringify(await cargoState()),originalText);checks.atomic_native_vehicle_profile_switch_preserves_HUs=true;
 // A direct binding may arrive while a previously admitted empty route is already playing.
 assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activateRoute('F01-heavy')),true);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.seekRoute(5)),true);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.playRoute(true)),true);await settle();assert.equal((await snapshot()).route.playing,true);
 result=await page.evaluate(change=>window.__QOIMA_WAREHOUSE_V3__.applyCargoBindings([change]),{handling_unit_id:small.handling_unit_id,destination:{kind:'actor',actor_id:'P01',anchor_id:'two-hand-small'}});assert.equal(result.ok,true);const stoppedRoute=(await snapshot()).scene.vehicle_poses,heldState=JSON.stringify(await cargoState());assert.equal((await snapshot()).route.playing,false);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.seekRoute(2)),false);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.playRoute(true)),false);await page.evaluate(()=>new Promise(resolve=>setTimeout(resolve,200)));assert.deepEqual((await snapshot()).scene.vehicle_poses,stoppedRoute);assert.equal(JSON.stringify(await cargoState()),heldState);assert.deepEqual(fatal,[]);await reset();await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activateRoute(''));checks.raw_holder_binding_pauses_existing_route_and_refuses_seek_without_pageerror=true;
 // The concrete UI must reach an actual holder view with keyboard interaction.
 if(!await page.locator('#warehouse-holder-panel').evaluate(details=>details.open))await page.locator('#warehouse-holder-panel summary').click();await page.locator('#holder-select').selectOption('actor-small');await holderPhase('ready');await page.locator('#holder-reset').focus();await page.keyboard.press('Enter');assert.equal(JSON.stringify(await cargoState()),originalText);checks.actual_keyboard_holder_activation_and_reset=true;
 await page.setViewportSize({width:390,height:950});await page.evaluate(()=>scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await activate('cart-small');await page.locator('#warehouse-viewport').scrollIntoViewIfNeeded();await capture('mobile-cart');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await reset();await page.setViewportSize({width:1440,height:1100});checks.mobile_holder_view_has_no_horizontal_overflow=true;
 // Optional support failures must not tear down the already usable base renderer.
 async function failureCase(name,fulfill){
  await initial();expecting=true;await page.route('**/models/v3/worker-manual.glb',route=>route.fulfill(fulfill),{times:1});assert.equal(await activate('actor-small'),false);await holderPhase('error');const s=await snapshot();assert.equal(s.phase,'ready');assert.equal(s.scene.workers,24);assert.equal(s.scene.stock_HUs,530);assert.equal(await page.locator('#warehouse-viewport canvas').count(),1);assert.equal(JSON.stringify(await cargoState()),originalText);await page.locator('#warehouse-view').selectOption('small-west');assert.equal((await snapshot()).scene.view,'small-west');await capture(name);expecting=false;
  await page.locator('#holder-retry').click();await holderPhase('ready');assert.equal((await cargoState()).filter(row=>row.destination.kind==='actor').length,1);await reset();
 }
 await failureCase('missing-optional-model',{status:404,body:'missing optional model'});await failureCase('modified-optional-model',{status:200,contentType:'model/gltf-binary',body:'unaccepted model bytes'});checks.optional_404_and_SHA_mismatch_leave_base_viewer_usable_and_retry=true;
 // Hold only the optional request; reset must cancel it and discard its eventual result.
 await initial();let reached,hit=new Promise(resolve=>reached=resolve),gate=new Promise(resolve=>release=resolve);await page.route('**/models/v3/worker-manual.glb',async route=>{reached();await gate;await route.continue().catch(()=>{});},{times:1});const old=activate('actor-small');await bounded(hit);await holderPhase('loading');assert.equal((await snapshot()).phase,'ready');await reset();release();await old;assert.equal(JSON.stringify(await cargoState()),originalText);assert.equal((await holderState()).phase,'idle');checks.cancelled_optional_load_cannot_attach_late=true;
 await initial();hit=new Promise(resolve=>reached=resolve);gate=new Promise(resolve=>release=resolve);await page.route('**/models/v3/worker-manual.glb',async route=>{reached();await gate;await route.continue().catch(()=>{});},{times:1});const first=activate('actor-small');await bounded(hit);const latest=activate('belt-standard');release();await Promise.all([first,latest]);await holderPhase('ready');const lateRows=await cargoState(),lateAttached=lateRows.filter(row=>row.destination.kind!=='storage_slot');assert.equal(lateAttached.length,1);assert.equal(lateAttached[0].destination.kind,'belt');assert.equal(lateAttached[0].cargo.archetype_id,'STANDARD_CARTON');assert.equal((await snapshot()).scene.workers,24);await reset();checks.latest_holder_intent_wins_without_duplicate_actor_or_HU=true;
 // A held fetch must time out, remain local and recover via the optional retry.
 await initial();hit=new Promise(resolve=>reached=resolve);gate=new Promise(resolve=>release=resolve);expecting=true;await page.route('**/models/v3/worker-manual.glb',async route=>{reached();await gate;await route.continue().catch(()=>{});},{times:1});const timeout=activate('actor-small');await bounded(hit);await holderPhase('error');assert.equal((await holderState()).error_kind,'timeout');assert.equal((await snapshot()).phase,'ready');assert.equal(JSON.stringify(await cargoState()),originalText);await capture('optional-timeout');release();await timeout;expecting=false;await page.locator('#holder-retry').click();await holderPhase('ready');await reset();checks.bounded_optional_timeout_and_retry=true;
 await context.setOffline(true);await activate('belt-small');assert.equal((await snapshot()).phase,'ready');assert.equal((await cargoState()).filter(row=>row.destination.kind==='belt').length,1);await reset();await context.setOffline(false);checks.loaded_support_kit_remains_usable_offline=true;
 }
 assert(requests.every(path=>path.startsWith('http://127.0.0.1:4173/')));assert(!requests.some(path=>path.includes('/api/')));assert.equal(await page.locator('audio,video').count(),0);checks.local_only_muted_no_backend_or_media=true;
 assert.deepEqual(fatal,[]);assert.deepEqual(unexpected,[]);await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.dispose());assert.equal(await page.locator('#warehouse-viewport canvas').count(),0);assert.equal((await snapshot()).phase,'disposed');checks.explicit_dispose_removes_renderer=true;await page.close();await context.close();
}catch(error){failure=error.stack||String(error);}
finally{
 release();if(browser)await bounded(browser.close(),5000).catch(()=>{});if(server){await bounded(server.close(),5000).catch(()=>{});for(let i=0;i<20&&alive();i++)await new Promise(resolve=>setTimeout(resolve,100));if(alive()){await bounded(server.kill(),5000).catch(()=>{});for(let i=0;i<20&&alive();i++)await new Promise(resolve=>setTimeout(resolve,100));}}
 lifecycle={owned_pid:server?.process().pid??null,terminated:!alive(),elapsed_ms:Date.now()-started};if(!lifecycle.terminated)failure??='Owned Chrome did not terminate';
 for(const path of files)if(sha(await readFile('../'+path))!==input_hashes[path])failure??='Input changed during holder QA '+path;
 const report={passed:!failure,mode:smoke?'pose_smoke_only':'full_holder_gate',source_kind:'visual_fixture',engine_operation:false,operational_admission:false,visible:false,url,input_hashes,checks,frames,observations,negative_cases:negativeCases,fatal,unexpected,expected,lifecycle,failure,scope:'Actual same-GPU-instance paused holder poses and native contact/bounds inspection only. Actor side-clamp proof is separate from horizontal support. No physical transfer, dynamic stability, transport resource admission or actual engine run.'};
 await writeFile(out+'/browser-checks.json',JSON.stringify(report,null,2)+'\n');await writeFile('../docs/adaptive-v3/evidence/W04.3-browser'+(smoke?'-preview':'')+'-checks.json',JSON.stringify({passed:report.passed,mode:report.mode,source_kind:report.source_kind,engine_operation:false,operational_admission:false,report:'assets/v3/iterations/warehouse/W04.3/'+(smoke?'browser-preview':'browser')+'/browser-checks.json',input_hashes,checks:Object.keys(checks).length,captures:frames.length,observations:observations.length,negative_cases:negativeCases.length,lifecycle,failure,scope:report.scope},null,2)+'\n');
 console.log(JSON.stringify({passed:report.passed,checks:Object.keys(checks).length,captures:frames.length,observations:observations.length,negative_cases:negativeCases.length,lifecycle,failure}));
}
if(failure)process.exitCode=1;
