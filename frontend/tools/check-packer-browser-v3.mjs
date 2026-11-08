import assert from'node:assert/strict';
import{chromium}from'@playwright/test';
import{mkdir,writeFile,readFile}from'node:fs/promises';
import{execFile}from'node:child_process';
const out='../assets/v3/iterations/packer/P04.3/browser',base=process.env.QOIMA_STAND_BASE_URL||'http://127.0.0.1:4173',url=base+'/stand-v3.html?asset=packer-workcell-fixture&fixture=packer';await mkdir(out,{recursive:true});
const started=Date.now(),server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio'],timeout:30000});
const errors=[],resources=[],expected=[],frames=[],checks={};let browser,failure;
async function bounded(promise,ms){let timer;try{return await Promise.race([promise.then(()=>true,()=>false),new Promise(r=>{timer=setTimeout(()=>r(false),ms);})]);}finally{clearTimeout(timer);}}
const alive=()=>{try{process.kill(server.process().pid,0);return true;}catch(e){return e.code!=='ESRCH';}};
try{
 browser=await chromium.connect(server.wsEndpoint(),{timeout:15000});const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1}),page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('response',r=>{if(r.status()>=400)resources.push({url:r.url(),status:r.status()});});
 const ready=()=>page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
 const settle=()=>page.evaluate(async()=>{for(let i=0;i<5;i++)await new Promise(r=>requestAnimationFrame(r));});
 const snapshot=()=>page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());
 const seek=t=>page.evaluate(t=>window.__QOIMA_STAND_V3__.cycle.seek(t),t);
 const verify=s=>{assert.equal(s.fixture,'packer-seam-end-visual-QA');assert.equal(s.action.actorId,'PK01');assert.equal(s.action.source_kind,'visual_fixture');assert.equal(s.action.engine_operation,false);assert.equal(s.action.inventory_mutated,false);assert.equal(s.nodes.filter(n=>n==='actor__PK01').length,1);assert.equal(s.nodes.filter(n=>n==='packer_existing_parcel').length,1);assert(s.action.contacts.filter(c=>c.active).every(c=>c.error_m<2e-6));};
 await page.goto(url);await ready();await settle();await page.waitForFunction(()=>document.querySelector('#reference')?.naturalWidth>0);const initial=await snapshot();verify(initial);await page.waitForTimeout(100);assert.equal((await snapshot()).action.time,0);checks.no_autoplay=true;
 for(const [time,view]of[[0,'quarter'],[.7,'side'],[1.5,'front'],[2.1,'side'],[3.2,'quarter'],[3.2,'side'],[3.2,'front'],[3.2,'rear'],[4.9,'quarter'],[7.5,'quarter']]){
  await seek(time);await page.evaluate(v=>window.__QOIMA_STAND_V3__.view(v),view);await settle();const s=await snapshot();verify(s);assert.equal(s.action.actor_uuid,initial.action.actor_uuid);assert.equal(s.action.package_uuid,initial.action.package_uuid);const file=`${out}/${String(time).replace('.','-')}-${view}.png`;await page.screenshot({path:file});frames.push({time,view,screenshot:file,state:s});
 }
 for(const side of ['R','L']){
  await seek(3.2);await page.evaluate(side=>window.__QOIMA_STAND_V3__.focus('joint__hand_'+side,'side'),side);const box=await page.locator('#canvas-host').boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.wheel(0,1000);await settle();const file=`${out}/contact-${side}.png`;await page.screenshot({path:file});frames.push({time:3.2,view:'side',focus:'joint__hand_'+side,zoom_out_wheel_delta:1000,screenshot:file,state:await snapshot()});
 }
 await page.evaluate(()=>window.__QOIMA_STAND_V3__.view('quarter'));await seek(7.5);await page.locator('#cycle-play').click();await page.waitForFunction(()=>window.__QOIMA_STAND_V3__.cycle.snapshot().time>.1);await page.locator('#cycle-play').click();const paused=(await snapshot()).action;assert(!paused.playing&&paused.time<2);await page.waitForTimeout(120);assert.equal((await snapshot()).action.time,paused.time);checks.play_pause_repeat=true;
 for(const mode of ['idle','blocked']){
  await page.locator(`[data-packer-mode="${mode}"]`).click();await settle();const s=await snapshot();verify(s);assert.equal(s.action.mode,mode);assert.equal(s.action.time,0);assert.equal(s.action.final_inspection_complete,false);assert.equal(s.action.actor_uuid,initial.action.actor_uuid);assert(await page.locator('#cycle-play').isDisabled());assert(await page.locator('#cycle-time').isDisabled());assert.equal(await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.play()),false);
  for(const c of s.action.contacts)assert(c.side==='L'?c.palm_direction_workcell[0]<-.98:c.palm_direction_workcell[0]>.98);
  await seek(6);assert.equal((await snapshot()).action.time,0);const file=`${out}/${mode}-quarter.png`;await page.screenshot({path:file});frames.push({mode,view:'quarter',screenshot:file,state:s});
 }
 checks.distinct_idle_blocked_no_work_and_inward_palms=true;
 await page.locator('[data-packer-mode="pack"]').click();await seek(0);await page.locator('#cycle-play').click();await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>document.querySelector('#cycle-play').disabled);assert.equal((await snapshot()).action.playing,false);await seek(3.2);verify(await snapshot());assert.equal((await snapshot()).presentation.camera_inertia,false);checks.live_reduced_motion=true;
 await page.locator('#cycle-time').focus();await page.keyboard.press('End');assert.equal((await snapshot()).action.time,7.5);checks.keyboard_seek=true;
 const cold=await context.newPage();await cold.emulateMedia({reducedMotion:'reduce'});await cold.goto(url);await cold.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');const cs=await cold.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());verify(cs);assert.equal(cs.action.time,0);assert(await cold.locator('#cycle-play').isDisabled());await cold.close();checks.cold_reduced_motion=true;
 await page.emulateMedia({reducedMotion:'no-preference'});const memories=[];
 for(let i=0;i<3;i++){await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('packer-workcell-fixture'));await ready();await settle();const s=await snapshot();verify(s);memories.push(s.renderer.memory);}
 assert.equal(new Set(memories.map(m=>JSON.stringify(m))).size,1);checks.replacement_memory=memories;
 const e0=errors.length,r0=resources.length;await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('zz-missing-packer-model'));assert.equal((await snapshot()).phase,'error');assert(await page.locator('#cycle-controls').isHidden());assert(await page.locator('#packer-modes').isHidden());expected.push({errors:errors.splice(e0),resources:resources.splice(r0)});
 await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('packer-workcell-fixture'));await ready();await settle();verify(await snapshot());assert.deepEqual((await snapshot()).renderer.memory,memories[0]);checks.error_cleanup_recovery=true;
 const invalid=JSON.parse(await readFile('public/data/v3/packer-seam-end.json','utf8'));invalid.engine_operation=true;
 await page.route('**/data/v3/packer-seam-end.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(invalid)}));await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('packer-workcell-fixture'));assert.equal((await snapshot()).phase,'error');assert(await page.locator('#cycle-controls').isHidden());await page.unroute('**/data/v3/packer-seam-end.json');await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('packer-workcell-fixture'));await ready();await settle();assert.deepEqual((await snapshot()).renderer.memory,memories[0]);checks.invalid_timeline_cleanup_recovery=true;
 let entered;const routed=new Promise(r=>entered=r);await page.route('**/data/v3/packer-seam-end.json',async route=>{entered();await new Promise(r=>setTimeout(r,200));await route.continue();});
 const old=page.evaluate(()=>window.__QOIMA_STAND_V3__.load('packer-workcell-fixture'));await routed;await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('packing-station'));await old;await page.unroute('**/data/v3/packer-seam-end.json');const stale=await snapshot();assert.equal(stale.modelId,'packing-station');assert.equal(stale.action,null);assert(!stale.nodes.includes('actor__PK01'));assert(await page.locator('#packer-modes').isHidden());checks.stale_request_does_not_resurrect_actor=true;
 await page.goto(base+'/stand-v3.html?asset=picking-cart-tote-fixture&fixture=walk');await ready();assert.equal(await page.locator('#cycle-time').getAttribute('max'),'9');assert(!await page.locator('#cycle-time').isDisabled());await seek(3.5);assert.equal((await snapshot()).fixture,'picker-cart-walk-visual-QA');checks.walk_cycle_controls_regression=true;
 assert.deepEqual(errors,[]);assert.deepEqual(resources,[]);
}catch(e){failure=e;}
let cleanup='graceful';if(!await bounded(server.close(),5000)){cleanup='forced_after_5s';await bounded(server.kill(),3000);if(alive()&&process.platform==='win32')await bounded(new Promise(r=>execFile('taskkill.exe',['/PID',String(server.process().pid),'/T','/F'],{windowsHide:true},()=>r())),3000);}
if(browser)await bounded(browser.close(),1000);const lifecycle={owned_pid:server.process().pid,cleanup,terminated:!alive(),elapsed_ms:Date.now()-started};if(!lifecycle.terminated&&!failure)failure=Error('Owned browser did not terminate');
await writeFile(`${out}/browser-checks.json`,JSON.stringify({at:new Date().toISOString(),url,visible:false,viewport:{width:1440,height:1000},errors,failed_resources:resources,expected_failures:expected,frames,checks,lifecycle,failure:failure?String(failure):null},null,2)+'\n');console.log(JSON.stringify({passed:!failure,captures:frames.length,checks,lifecycle,error:failure?String(failure):null}));process.exit(failure?1:0);
