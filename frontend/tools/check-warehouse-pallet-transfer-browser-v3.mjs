import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';

// Default is renderer-free preflight. The owner must separately release the GPU slot for --run.
const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),root=path.dirname(frontend);
const running=process.argv.includes('--run'),sha=b=>createHash('sha256').update(b).digest('hex');
if(process.env.QOIMA_VISIBLE_TESTS==='1')throw Error('Only one owned, muted, headless localhost Chrome is permitted.');
const base=new URL(process.env.QOIMA_BROWSER_BASE_URL??'http://127.0.0.1:4173/');
assert(base.protocol==='http:'&&base.hostname==='127.0.0.1'&&base.pathname==='/'&&!base.username&&!base.password&&!base.search&&!base.hash,'Localhost root URL required');
const url=new URL('warehouse-v3.html',base).href,runId=new Date().toISOString().replaceAll(':','-');
const out=path.join(root,'work/v3/pallet-transfer-browser',runId),HU='v3:HU:initial:DEMO_172:01',TARGET='v3:slot:HEAVY_E:009:L1:B1',EPS=2e-6;
await mkdir(out,{recursive:true});
const manifest=JSON.parse(await readFile(path.join(frontend,'src/adaptive-v3/warehouseActionSourceManifest.json'),'utf8'));
const fixture=JSON.parse(await readFile(path.join(frontend,'public/data/v3/warehouse-fixture-v3.json'),'utf8'));
const originalCargo=new Map(fixture.inputs.initial_stock.map(h=>[h.handling_unit_id,h]));
const files=new Set(['frontend/warehouse-v3.html','frontend/vite.config.ts','frontend/package-lock.json','frontend/tools/check-warehouse-pallet-transfer-browser-v3.mjs']);
const productionFiles=[];
if(running){const html=await readFile(path.join(frontend,'dist/warehouse-v3.html'),'utf8');assert(!html.includes('/@vite/client')&&html.includes('/assets/'),'Actual production build required');for(const rel of ['warehouse-v3.html',...new Set([...html.matchAll(/(?:src|href)="\/(assets\/[^"?]+)"/g)].map(m=>m[1]))]){productionFiles.push(rel);files.add('frontend/dist/'+rel);}}
async function includeTree(folder,relative){for(const entry of await readdir(folder,{withFileTypes:true})){const rel=relative+'/'+entry.name;if(rel==='frontend/src/adaptive-v3/twin')continue;if(entry.isDirectory())await includeTree(path.join(folder,entry.name),rel);else if(/\.(ts|css|json|glb)$/.test(entry.name))files.add(rel);}}
await includeTree(path.join(frontend,'src/adaptive-v3'),'frontend/src/adaptive-v3');
await includeTree(path.join(frontend,'public/data/v3'),'frontend/public/data/v3');
await includeTree(path.join(frontend,'public/models/v3'),'frontend/public/models/v3');
files.add('frontend/public/data/adaptive-v3/layout-manifest.json');
for(const entry of manifest.entries){files.add(entry.source_path);files.add('frontend/public/'+entry.url);}
const input_hashes={};for(const file of [...files].sort())input_hashes[file]=sha(await readFile(path.join(root,file)));
const preflightProblems=[],publicSources=[];
assert.equal(manifest.entries.length,30,'The real bootstrap must bind exactly 30 accepted sources');
assert.equal(new Set(manifest.entries.map(e=>e.source_path)).size,30);
assert.equal(new Set(manifest.entries.map(e=>e.url)).size,30);
for(const entry of manifest.entries){
 assert(/^[a-f0-9]{64}$/.test(entry.sha256)&&Number.isSafeInteger(entry.bytes)&&entry.bytes>0);
 assert(/^(data|models)\//.test(entry.url)&&!entry.url.includes('..'));
 const source=await readFile(path.join(root,entry.source_path)),served=await readFile(path.join(frontend,'public',entry.url));
 const row={source_path:entry.source_path,url:entry.url,expected_sha256:entry.sha256,source_sha256:sha(source),served_sha256:sha(served),source_bytes:source.length,served_bytes:served.length,expected_bytes:entry.bytes};
 publicSources.push(row);if(row.source_sha256!==entry.sha256||row.served_sha256!==entry.sha256||source.length!==entry.bytes||served.length!==entry.bytes)preflightProblems.push(row);
}
const checks={},captures=[],observations=[],negativeCases=[],fatal=[],unexpected=[],expected=[],requests=[],responses=[],responseTasks=[],failedRequests=[],httpPreflight=[],compiledHTTP=[];
const started=Date.now();let server,browser,context,page,failure,failureState,baseState,baseNative,baseBindings,originalInspect,expectingFault=false;
const heldReleases=new Set(),faultRequests=new WeakSet();let deadlineTimer;
function check(name){checks[name]=true;}
function near(a,b,eps=EPS,label='native value'){assert(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=eps,`${label}: ${a} != ${b}`);}
function finiteArray(values,count){assert(Array.isArray(values)&&values.length===count&&values.every(Number.isFinite));}
function conserved(rows){
 assert.equal(rows.length,530);assert.equal(new Set(rows.map(h=>h.handling_unit_id)).size,530);
 assert.equal(rows.reduce((n,h)=>n+h.cargo.quantity_units,0),12256);near(rows.reduce((n,h)=>n+h.cargo.gross_mass_kg,0),9403.85,1e-7,'conserved gross mass');
 for(const row of rows){assert.deepEqual(row.cargo,originalCargo.get(row.handling_unit_id));assert.equal(row.model_scale_factor,1);}
}
function honest(s){
 assert.equal(s.phase,'ready');assert.equal(s.source_kind,'visual_fixture');assert.equal(s.engine_operation,false);
 assert.equal(s.scene.workers,24);assert.equal(s.scene.stock_HUs,530);assert.equal(s.scene.cargo_binding_count,530);assert.equal(s.scene.completed_jobs,0);assert.equal(s.scene.actions_scheduled,0);
 assert.deepEqual(s.scene.worker_ids,baseState.scene.worker_ids);assert.deepEqual(s.scene.vehicle_ids,baseState.scene.vehicle_ids);
 assert.equal(s.pallet.source_kind,'visual_fixture');assert.equal(s.pallet.engine_operation,false);assert.equal(s.pallet.physical_join,false);assert.equal(s.pallet.completed_jobs,0);
 if(s.pallet.frame){assert.equal(s.pallet.frame.physical_join,false);assert.equal(s.pallet.frame.native_geometry_admission_required,true);assert.equal(s.pallet.frame.completed_jobs,0);assert.deepEqual(s.pallet.frame.actual_events,[]);}
}
function identities(n){return{actors:n.actors.map(a=>[a.actor_id,a.uuid,a.parent_uuid]),vehicles:n.vehicles.map(v=>[v.vehicle_id,v.uuid,v.parent_uuid,v.nodes.map(x=>[x.name,x.uuid,x.parent_uuid])]),cargo:n.cargo.map(h=>[h.handling_unit_id,h.parts.map(p=>[p.uuid,p.index])])};}
function validateNative(n){
 assert(n&&n.actors?.length===24&&n.vehicles?.length===2&&n.cargo?.length===530,'MISSING_NATIVE_INTEGRITY_API');
 assert.equal(new Set(n.actors.map(a=>a.actor_id)).size,24);assert.equal(new Set(n.cargo.map(h=>h.handling_unit_id)).size,530);
 for(const row of n.cargo){assert(row.parts.length>0);for(const p of row.parts){assert(typeof p.uuid==='string'&&Number.isInteger(p.index)&&p.index>=0);finiteArray(p.instance_matrix,16);finiteArray(p.mesh_position,3);finiteArray(p.mesh_quaternion,4);finiteArray(p.mesh_scale,3);}}
 assert(n.vehicles.find(v=>v.vehicle_id==='FL02').nodes.some(n=>n.name==='joint__fork_L'));
}
function unchangedOthers(n){
 validateNative(n);assert.deepEqual(identities(n),identities(baseNative),'Actual worker/vehicle/HU object identities');
 assert.deepEqual(n.actors,baseNative.actors,'All 24 actor local TRS, F02 parent and UUID remain unchanged');
 assert.deepEqual(n.vehicles.find(v=>v.vehicle_id==='FL01'),baseNative.vehicles.find(v=>v.vehicle_id==='FL01'));
 const old=new Map(baseNative.cargo.map(h=>[h.handling_unit_id,h]));
 for(const h of n.cargo)if(h.handling_unit_id!==HU)assert.deepEqual(h,old.get(h.handling_unit_id),'Other 529 actual Float32 buffers/shared origins: '+h.handling_unit_id);
 const chosen=n.cargo.find(h=>h.handling_unit_id===HU),before=old.get(HU);
 for(let i=0;i<chosen.parts.length;i++)for(const key of ['uuid','index','mesh_position','mesh_quaternion','mesh_scale'])assert.deepEqual(chosen.parts[i][key],before.parts[i][key],'Selected HU preserves shared mesh frame');
 const moving=new Set(['vehicle__FL02','joint__carriage','joint__reach','joint__fork_L','joint__fork_R','joint__rear_steer_L','joint__rear_steer_R','joint__wheel_front_L','joint__wheel_front_R','joint__wheel_rear_L','joint__wheel_rear_R']);
 const oldNodes=new Map(baseNative.vehicles.find(v=>v.vehicle_id==='FL02').nodes.map(n=>[n.uuid,n]));
 for(const node of n.vehicles.find(v=>v.vehicle_id==='FL02').nodes)if(!moving.has(node.name))assert.deepEqual(node,oldNodes.get(node.uuid),'Actual immutable native child '+node.name);
}
function nativeSupport(proof){
 assert(proof.mesh_parts>0&&proof.vertices>0);assert.equal(proof.model_scale_factor,1);assert.equal(proof.source_kind,'visual_fixture');assert.equal(proof.engine_operation,false);
 assert(proof.native_contact_area_sum_m2>1e-8,'Native horizontal face contact must be positive');assert(proof.geometric_centre_inside_support_hull,'Actual centre lies inside native support hull');
 assert(proof.maximum_contact_gap_m<=EPS);assert(Math.abs(proof.actual_bottom_gap_m)<=EPS);assert(proof.support_parts.length>0);
 const d=proof.dimensions_xyz_m;proof.bounds_cargo_local.min.forEach((v,i)=>near(v,[-d[0]/2,0,-d[2]/2][i],EPS,'actual local lower bounds'));proof.bounds_cargo_local.max.forEach((v,i)=>near(v,[d[0]/2,d[1],d[2]/2][i],EPS,'actual local upper bounds'));
}
function driverContacts(d){assert.equal(d.actorId,'F02');assert.equal(d.assignment,'seated_existing_actor');assert.equal(d.disposed,false);assert.equal(d.warehouse_headcount_delta,0);for(const error of [d.seat_error_m,...Object.values(d.grip_error_m),...Object.values(d.sole_error_m)])assert(Number.isFinite(error)&&error<=EPS,'Existing native F02 contact budget');}
const snapshot=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.snapshot());
const bindings=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.cargoBindings());
const integrity=()=>page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.nativeIntegrity?.());
const inspect=()=>page.evaluate(id=>window.__QOIMA_WAREHOUSE_V3__.inspectCargo(id),HU);
const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
async function capture(name){await page.evaluate(id=>window.__QOIMA_WAREHOUSE_V3__.selectCargo(id),HU);await page.locator('#warehouse-viewport').scrollIntoViewIfNeeded();await settle();const file=name+'.png';await page.screenshot({path:path.join(out,file)});captures.push({file,sha256:sha(await readFile(path.join(out,file))),snapshot:await snapshot(),selected_card:await page.locator('#warehouse-selection').innerText()});}
async function restored(label){
 const s=await snapshot(),rows=await bindings(),proof=await inspect();honest(s);conserved(rows);assert.deepEqual(await integrity(),baseNative,label+' actual Float32/F02/FL02/fork exact restore');assert.deepEqual(s.scene.vehicle_poses,baseState.scene.vehicle_poses);assert.deepEqual(s.scene.driver_contacts,baseState.scene.driver_contacts);
 if(s.pallet.frame){
  // apply(0) publishes the captured Float32 native root. Closing removes that overlay and
  // restores the original decimal ledger exactly; these are separately checked contracts.
  assert.equal(s.pallet.at_s,0);assert.deepEqual(rows.find(h=>h.handling_unit_id===HU),s.pallet.frame.bound);
  for(const row of rows)if(row.handling_unit_id!==HU)assert.deepEqual(row,baseBindings.find(h=>h.handling_unit_id===row.handling_unit_id));
  const row=rows.find(h=>h.handling_unit_id===HU),before=baseBindings.find(h=>h.handling_unit_id===HU);assert.deepEqual(row.destination,before.destination);assert.deepEqual(row.cargo,before.cargo);row.position.forEach((v,i)=>near(v,before.position[i]));
  assert.deepEqual(proof.mesh_instances,originalInspect.mesh_instances);assert.deepEqual(proof.bounds_world,originalInspect.bounds_world);
  for(const [id,position]of Object.entries(s.scene.stock_positions))if(id===HU)assert.deepEqual(position,row.position);else assert.deepEqual(position,baseState.scene.stock_positions[id]);
 }else{assert.deepEqual(rows,baseBindings,label+' original ledger exact restore');assert.deepEqual(s.scene.stock_positions,baseState.scene.stock_positions);assert.deepEqual(proof,originalInspect,label+' actual geometry exact restore');}
}
async function observe(label,owner){
 const s=await snapshot(),rows=await bindings(),n=await integrity(),proof=await inspect(),frame=s.pallet.frame;honest(s);conserved(rows);unchangedOthers(n);assert(frame,'Actual private controller frame required');
 assert.deepEqual(frame,s.scene.pallet_transfer);assert.equal(frame.bound.handling_unit_id,HU);assert.deepEqual(frame.bound,rows.find(h=>h.handling_unit_id===HU));assert.equal(frame.logical_owner,owner);
 const from=baseBindings.find(h=>h.handling_unit_id===HU);for(const row of rows)if(row.handling_unit_id!==HU)assert.deepEqual(row,baseBindings.find(h=>h.handling_unit_id===row.handling_unit_id));
 assert.deepEqual(frame.mesh_instances,originalInspect.mesh_instances);assert.deepEqual(proof.mesh_instances,originalInspect.mesh_instances);assert.deepEqual(frame.bound.cargo,from.cargo);assert.equal(frame.bound.model_scale_factor,1);
 const matrix=frame.native_root_matrix;finiteArray(matrix,16);frame.bound.position.forEach((v,i)=>near(v,matrix[12+i],1e-10));near(Math.atan2(matrix[8],matrix[10]),frame.bound.yaw_rad,1e-10,'Actual native yaw');
 assert.deepEqual(s.scene.stock_positions[HU],frame.bound.position);assert.deepEqual(proof.position,frame.bound.position);assert.deepEqual(proof.destination,frame.bound.destination);near(proof.yaw_rad,frame.bound.yaw_rad,1e-10);nativeSupport(proof);driverContacts(frame.driver);
 if(owner==='vehicle:FL02'){
  assert.equal(frame.bound.destination.kind,'vehicle');assert.equal(frame.bound.destination.vehicle_id,'FL02');
  const nodes=n.vehicles.find(v=>v.vehicle_id==='FL02').nodes,byId=new Map(nodes.map(x=>[x.uuid,x])),forks=new Set(nodes.filter(x=>/^joint__fork_[LR]$/.test(x.name)).map(x=>x.uuid));
  const forkNames=new Set(nodes.filter(x=>{for(let p=x;p;p=byId.get(p.parent_uuid))if(forks.has(p.uuid))return true;return false;}).map(x=>x.name));
  assert(proof.support_parts.every(name=>forkNames.has(name)),'Support metadata must name actual native fork descendants');
 }else assert.equal(frame.bound.destination.slot_id,owner.slice(5));
 observations.push({label,at_s:s.pallet.at_s,phase_id:frame.phase_id,logical_owner:owner,native:proof,driver:frame.driver,part_root_spread_m:frame.native_part_root_spread_m,native_integrity_sha256:sha(JSON.stringify(n))});return{s,n,proof,frame};
}
async function waitPhase(phase){await page.waitForFunction(p=>{const actual=window.__QOIMA_WAREHOUSE_V3__.snapshot().pallet?.phase;return actual===p||p==='ready'&&actual==='error';},phase,{timeout:35000});const s=await snapshot();assert.equal(s.pallet.phase,phase,'Pallet phase '+JSON.stringify(s.pallet));}
async function prepareByUI(){await page.locator('#pallet-start').click();await waitPhase('ready');const s=await snapshot();assert.equal(s.pallet.playing,false);assert.equal(s.pallet.at_s,0);return s;}
async function stage(label){await page.locator('#pallet-stages').getByRole('button',{name:label,exact:true}).click();assert.equal((await snapshot()).pallet.playing,false);}
async function stopByUI(){await page.locator('#pallet-stop').click();await waitPhase('idle');await restored('close');}
async function verifyHTTP30(since){
 await Promise.all(responseTasks);const seen=responses.slice(since).filter(r=>!r.injected),byURL=new Map();for(const row of seen)if(!byURL.has(row.url))byURL.set(row.url,[]);for(const row of seen)byURL.get(row.url).push(row);
 for(const entry of manifest.entries){const rows=byURL.get(new URL(entry.url,base).href)??[];assert(rows.some(r=>r.status===200&&r.bytes===entry.bytes&&r.sha256===entry.sha256),'Actual byte-verified HTTP bootstrap missing '+entry.source_path);}
 check('real_all_30_HTTP_source_bytes_before_private_factory_issued_controller');
}
let deadline;
async function bounded(operation,ms=40000){let timer;try{return await Promise.race([operation,...(deadline?[deadline]:[]),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Bounded browser operation timed out')),ms);})]);}finally{clearTimeout(timer);}}
function alive(){if(!server)return false;try{process.kill(server.process().pid,0);return true;}catch(e){if(e.code==='ESRCH')return false;throw e;}}
async function holdProof(){
 let release,reached;const hit=new Promise(resolve=>reached=resolve),gate=new Promise(resolve=>release=resolve),entry=manifest.entries.find(e=>e.kind==='exact_public_proof_copy');heldReleases.add(release);
 await page.route(new URL(entry.url,base).href,async route=>{faultRequests.add(route.request());reached();await gate;await route.continue().catch(()=>{});},{times:1});
 return{hit,release:()=>{heldReleases.delete(release);release();}};
}
try{
 if(preflightProblems.length)throw Error('STALE_ACTION_SOURCE_PACKAGE: '+preflightProblems.map(p=>p.source_path).join(', '));
 check('local_30_source_originals_and_served_copies_match_manifest');
 if(running){
  // A Vite instance started before hash-named public copies were created can return
  // its SPA HTML for a locally present .bin. Check the actual server before owning a GPU.
  for(let i=0;i<manifest.entries.length;i+=4)await Promise.all(manifest.entries.slice(i,i+4).map(async entry=>{
   const response=await fetch(new URL(entry.url,base),{signal:AbortSignal.timeout(5000),cache:'no-store'}),bytes=Buffer.from(await response.arrayBuffer());
   httpPreflight.push({source_path:entry.source_path,url:response.url,status:response.status,content_type:response.headers.get('content-type'),bytes:bytes.length,sha256:sha(bytes),expected_bytes:entry.bytes,expected_sha256:entry.sha256});
  }));
  const staleHTTP=httpPreflight.filter(row=>row.status!==200||row.bytes!==row.expected_bytes||row.sha256!==row.expected_sha256);assert.deepEqual(staleHTTP,[],'STALE_HTTP_ACTION_SOURCE_PACKAGE');check('dedicated_QA_HTTP_30_source_preflight_before_Chrome');
  for(const rel of productionFiles){const response=await fetch(new URL(rel,base),{signal:AbortSignal.timeout(5000),cache:'no-store'}),bytes=Buffer.from(await response.arrayBuffer());assert.equal(response.status,200);assert.equal(sha(bytes),input_hashes['frontend/dist/'+rel],'Actual production HTML/compiled asset '+rel);compiledHTTP.push({url:response.url,bytes:bytes.length,sha256:sha(bytes)});}check('actual_production_HTML_and_all_declared_compiled_assets_match_dist');
  deadline=new Promise((_,reject)=>{deadlineTimer=setTimeout(()=>{failure??='Overall 240s browser budget exceeded';reject(Error(failure));if(server)void server.kill().catch(()=>{});},240000);});void deadline.catch(()=>{});
  server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio'],timeout:30000});browser=await chromium.connect(server.wsEndpoint());
  context=await browser.newContext({viewport:{width:1440,height:1100},hasTouch:true,reducedMotion:'reduce'});
  await context.route('**/*',route=>{if(route.request().url().startsWith(base.href))return route.continue();unexpected.push({blocked_nonlocal_request:route.request().url()});return route.abort('blockedbyclient');});
  page=await context.newPage();page.setDefaultTimeout(15000);
  page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>fatal.push(e.message));
  page.on('requestfailed',r=>failedRequests.push({url:r.url(),error:r.failure()?.errorText,injected:faultRequests.has(r)}));
  page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('CONTEXT_LOST_WEBGL'))(expectingFault&&/^Failed to load resource:/.test(m.text())?expected:unexpected).push(m.text());});
  page.on('response',r=>{const injected=faultRequests.has(r.request());if(r.status()>=400)(injected?expected:unexpected).push({url:r.url(),status:r.status()});if(manifest.entries.some(e=>new URL(e.url,base).href===r.url())){const task=(async()=>{try{const b=await r.body();responses.push({url:r.url(),status:r.status(),bytes:b.length,sha256:sha(b),injected});}catch(e){responses.push({url:r.url(),status:r.status(),injected,body_error:String(e)});}})();responseTasks.push(task);}});
  await bounded(page.goto(url));await bounded(page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready',null,{timeout:50000}),55000);
  assert.equal(await page.evaluate(()=>typeof window.__QOIMA_WAREHOUSE_V3__.nativeIntegrity),'function');
  assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activateHolder('cart-small')),true);await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.resetHolders());
  baseState=await snapshot();baseBindings=await bindings();baseNative=await integrity();originalInspect=await inspect();validateNative(baseNative);conserved(baseBindings);honest(baseState);nativeSupport(originalInspect);assert.equal(baseBindings.find(h=>h.handling_unit_id===HU).destination.kind,'storage_slot');
  if(!await page.locator('#warehouse-pallet-panel').evaluate(e=>e.open))await page.locator('#warehouse-pallet-panel summary').click();
  const httpStart=responses.length;await prepareByUI();await verifyHTTP30(httpStart);await restored('paused activation');await capture('01-paused-source');check('actual_prepare_button_starts_paused_and_restores_original_native_start');
  const sourceOwner='slot:'+baseBindings.find(h=>h.handling_unit_id===HU).destination.slot_id;await observe('source',sourceOwner);
  await page.evaluate(id=>window.__QOIMA_WAREHOUSE_V3__.selectCargo(id),HU);
  const times={};for(const [label,owner,phase]of [['Захват','vehicle:FL02','source_lift_attached'],['В пути','vehicle:FL02','loaded_route'],['Установка','slot:'+TARGET,'target_controlled_withdraw'],['Финиш','slot:'+TARGET,'final_depart']]){
   await stage(label);const s=await snapshot();times[label]=s.pallet.at_s;if(label!=='Финиш')assert.equal(s.pallet.frame.phase_id,phase);await observe(label,owner);assert((await page.locator('#warehouse-selection').innerText()).includes(HU));await capture('stage-'+(label==='Захват'?'attach':label==='В пути'?'loaded':label==='Установка'?'release':'end'));
  }
  assert((await page.locator('#pallet-status').innerText()).includes('заказ не выполнен'));check('actual_stage_buttons_native_attach_loaded_setdown_end_overlay_and_support');
  const fingerprints=new Map();for(const t of [0,times['Захват']-1e-7,times['Захват'],times['Захват']+1e-7,times['В пути'],times['Установка']-1e-7,times['Установка'],times['Установка']+1e-7,times['Финиш']]){assert.equal(await page.evaluate(t=>window.__QOIMA_WAREHOUSE_V3__.seekPallet(t),t),true);const s=await snapshot(),owner=t<times['Захват']?sourceOwner:t<times['Установка']?'vehicle:FL02':'slot:'+TARGET;await observe('absolute-'+t,owner);fingerprints.set(t,sha(JSON.stringify(await integrity())));}
  for(const t of [...fingerprints.keys()].reverse()){assert.equal(await page.evaluate(t=>window.__QOIMA_WAREHOUSE_V3__.seekPallet(t),t),true);assert.equal(sha(JSON.stringify(await integrity())),fingerprints.get(t),'Absolute reverse seek exact native buffers');}
  // Native-root continuity is checked around joins independently of the displayed logical owner.
  for(const t of [times['Захват'],times['Установка']]){await page.evaluate(t=>window.__QOIMA_WAREHOUSE_V3__.seekPallet(t),t-1e-7);const a=(await snapshot()).pallet.frame.native_root_matrix;await page.evaluate(t=>window.__QOIMA_WAREHOUSE_V3__.seekPallet(t),t+1e-7);const b=(await snapshot()).pallet.frame.native_root_matrix;a.forEach((v,i)=>near(v,b[i],EPS,'Attach/release native matrix continuity'));}
  check('absolute_reverse_boundary_seeks_same_530_buffers_and_two_micrometre_join_continuity');
  await page.locator('#pallet-reset').focus();await page.keyboard.press('Enter');assert.equal((await snapshot()).pallet.at_s,0);await restored('actual keyboard reset');check('keyboard_reset_exact_original_cargo_F02_FL02_fork_and_seated_state');
  await stage('В пути');const busyBefore=await integrity(),busyBindings=await bindings();
  for(const method of ['applyCargoBindings','resetCargoBindings']){const result=await page.evaluate(method=>{try{window.__QOIMA_WAREHOUSE_V3__[method](method==='applyCargoBindings'?[]:undefined);return{refused:false};}catch(e){return{refused:true,message:e.message};}},method);assert.equal(result.refused,true);assert.equal(result.message,'CARGO_ACTION_BUSY');assert.deepEqual(await integrity(),busyBefore);assert.deepEqual(await bindings(),busyBindings);negativeCases.push({case_id:'raw_'+method+'_during_transfer',...result});}
  assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.seekRoute(1)),false);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.playRoute(true)),false);assert.deepEqual(await integrity(),busyBefore);check('busy_raw_legacy_bind_reset_and_empty_route_seek_play_refuse_atomically');
  // Reduced motion is live, and manual stages remain operable under it.
  assert.equal(await page.locator('#pallet-play').isDisabled(),true);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.playPallet(true)),false);
  await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForFunction(()=>!document.querySelector('#pallet-play').disabled);await page.locator('#pallet-reset').click();await page.locator('#pallet-play').click();await page.waitForFunction(()=>window.__QOIMA_WAREHOUSE_V3__.snapshot().pallet.at_s>0);await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>!window.__QOIMA_WAREHOUSE_V3__.snapshot().pallet.playing);const paused=(await snapshot()).pallet.at_s;await page.waitForTimeout(180);assert.equal((await snapshot()).pallet.at_s,paused);await stage('В пути');await observe('live-reduced-manual','vehicle:FL02');await capture('06-live-reduced-manual');check('live_reduced_motion_pauses_no_stale_RAF_and_manual_stages_work');
  await page.setViewportSize({width:390,height:950});await page.locator('#warehouse-pallet-panel').scrollIntoViewIfNeeded();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await stage('Установка');await observe('mobile-setdown','slot:'+TARGET);await page.locator('#warehouse-viewport').scrollIntoViewIfNeeded();await capture('07-mobile-setdown');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1440,height:1100});check('mobile_manual_transfer_without_horizontal_overflow');
  await stopByUI();await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.stopPallet());await restored('repeated close');check('close_and_repeated_close_exact_native_restore_without_job_commit');
  // Actual route/holder selection intentionally switches out of this preview; raw mutation is blocked above.
  await prepareByUI();await stage('В пути');if(!await page.locator('#warehouse-route-panel').evaluate(e=>e.open))await page.locator('#warehouse-route-panel summary').click();await page.locator('#route-select').selectOption('F01-heavy');await page.waitForFunction(()=>window.__QOIMA_WAREHOUSE_V3__.snapshot().route?.phase==='ready');assert.equal((await snapshot()).pallet.phase,'idle');assert.deepEqual(await bindings(),baseBindings);await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activateRoute(''));await restored('legacy route switch');
  await prepareByUI();await stage('В пути');if(!await page.locator('#warehouse-holder-panel').evaluate(e=>e.open))await page.locator('#warehouse-holder-panel summary').click();await page.locator('#holder-select').selectOption('cart-small');await page.waitForFunction(()=>window.__QOIMA_WAREHOUSE_V3__.snapshot().holder?.phase==='ready');assert.equal((await snapshot()).pallet.phase,'idle');assert.equal((await bindings()).filter(h=>h.destination.kind==='cart').length,1);await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.resetHolders());await restored('holder switch');check('actual_route_holder_switches_close_transfer_before_legacy_activation');
  const proofEntry=manifest.entries.find(e=>e.kind==='exact_public_proof_copy');
  for(const fault of ['missing','tampered']){
   expectingFault=true;await page.route(new URL(proofEntry.url,base).href,async route=>{faultRequests.add(route.request());await route.fulfill({status:fault==='missing'?404:200,body:fault==='missing'?'missing source':'altered source bytes',contentType:'application/octet-stream'});},{times:1});
   await page.locator('#pallet-start').click();await waitPhase('error');const s=await snapshot();assert(s.pallet.error);assert.equal(s.phase,'ready');assert.equal(await page.locator('#warehouse-viewport canvas').count(),1);await restored(fault+' bootstrap refusal');await capture('error-'+fault);negativeCases.push({case_id:fault+'_source_bootstrap',error:s.pallet.error});expectingFault=false;
   await prepareByUI();await stopByUI();
  }
  check('actual_missing_tampered_byte_bootstrap_refuses_no_native_mutation_and_retries');
  expectingFault=true;let hold=await holdProof(),old=page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activatePallet());await bounded(hold.hit,8000);await waitPhase('loading');await page.locator('#pallet-stop').click();hold.release();assert.equal(await bounded(old),false);await restored('cancelled bootstrap');assert.equal((await snapshot()).pallet.phase,'idle');check('cancelled_async_bootstrap_cannot_attach_late');
  hold=await holdProof();old=page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activatePallet());await bounded(hold.hit,8000);const latest=page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activatePallet());hold.release();const results=await bounded(Promise.all([old,latest]));assert.deepEqual(results,[false,true]);await waitPhase('ready');assert.equal((await snapshot()).pallet.at_s,0);await restored('latest bootstrap');await stopByUI();check('latest_async_bootstrap_wins_one_private_controller_no_duplicate_HU');
  // Disposal while a real source fetch is held must invalidate that exact old scene lifetime.
  hold=await holdProof();old=page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activatePallet());await bounded(hold.hit,8000);await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.dispose());hold.release();assert.equal(await bounded(old),false);assert.equal((await snapshot()).phase,'disposed');assert.equal(await page.locator('#warehouse-viewport canvas').count(),0);assert.equal(await page.evaluate(()=>window.__QOIMA_WAREHOUSE_V3__.activatePallet()),undefined);await page.waitForTimeout(180);assert.equal(await page.locator('#warehouse-viewport canvas').count(),0);check('dispose_held_bootstrap_no_late_native_reacquisition_or_renderer');
  expectingFault=false;assert(requests.every(r=>r.startsWith(base.href)),'Only exact localhost origin is allowed');assert(!requests.some(r=>new URL(r).pathname.startsWith('/api/')));assert(!requests.some(r=>new URL(r).pathname==='/@vite/client'));assert(requests.some(r=>/^\/assets\/.+\.js$/.test(new URL(r).pathname)));assert.equal(await page.locator('audio,video').count(),0);check('local_only_muted_production_no_HMR_backend_media_or_actual_engine');assert.deepEqual(fatal,[]);assert.deepEqual(unexpected,[]);
 }
}catch(e){failure=e.stack??String(e);if(page&&!page.isClosed()){try{failureState={snapshot:await bounded(snapshot(),3000),status:await page.locator('#pallet-status').innerText({timeout:2000})};const file='failure.png';await page.screenshot({path:path.join(out,file),timeout:3000});failureState.capture=file;}catch(error){failureState??={};failureState.diagnostic_error=String(error);}}}
finally{
 clearTimeout(deadlineTimer);deadline=undefined;for(const release of heldReleases)release();
 if(browser)await bounded(browser.close(),5000).catch(()=>{});if(server){await bounded(server.close(),5000).catch(()=>{});if(alive())await bounded(server.kill(),5000).catch(()=>{});for(let i=0;i<20&&alive();i++)await new Promise(r=>setTimeout(r,100));}
 const lifecycle={owned_pid:server?.process().pid??null,terminated:!alive(),elapsed_ms:Date.now()-started};if(!lifecycle.terminated)failure??='Owned Chrome process remains alive';
 for(const [file,hash]of Object.entries(input_hashes))if(sha(await readFile(path.join(root,file)))!==hash)failure??='Input changed during QA: '+file;
 const report={task_id:'W05.4.4',mode:running?'actual_browser_integration':'preflight_only',served_mode:running?'production_vite_preview':null,passed:running?!failure:null,runtime_status:server?(failure?'failed':'passed'):'not_run',preflight_current:preflightProblems.length===0,source_kind:'visual_fixture',engine_operation:false,physical_join:false,completed_jobs:0,operational_admission:false,visible:false,url,input_hashes,public_sources:publicSources,preflight_problems:preflightProblems,http_preflight:httpPreflight,compiled_HTTP:compiledHTTP,checks,captures,observations,negative_cases:negativeCases,responses,requests,failed_requests:failedRequests,fatal,unexpected,expected,lifecycle,failure,failure_state:failureState,scope:'Actual production warehouse page, 30 byte-verified static sources, existing private-issued native transfer controller and actual same-HU instanced buffers/24 workers/2 vehicles. Reversible visual integration only; no completed job, actual engine, full physical join, collision/stability certificate or visual acceptance claim. Faults alter network responses only for explicit negative cases. Root separately owns full native and visual review.'};
 await writeFile(path.join(out,'browser-checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({mode:report.mode,passed:report.passed,runtime_status:report.runtime_status,preflight_current:report.preflight_current,checks:Object.keys(checks).length,captures:captures.length,observations:observations.length,negative_cases:negativeCases.length,lifecycle,report:path.join(out,'browser-checks.json'),failure}));
}
if(failure)process.exitCode=1;
