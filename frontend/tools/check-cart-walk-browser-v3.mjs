import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
const manual=process.env.QOIMA_WALK_WORKER==='worker-manual',visible=process.env.QOIMA_VISIBLE_TESTS==='1';
const out=manual?'../assets/v3/qa-browser/manual-cart-walk':'../assets/v3/qa-browser/picker-cart-walk',base=process.env.QOIMA_STAND_BASE_URL||'http://127.0.0.1:4173',url=base+'/stand-v3.html?asset=picking-cart-tote-fixture&fixture=walk'+(manual?'&worker=manual':'');await mkdir(out,{recursive:true});
const started=Date.now(),server=await chromium.launchServer({channel:'chrome',headless:!visible,args:['--mute-audio'],timeout:30000});
const errors=[],resources=[],expectedFailures=[],frames=[],checks={};let browser,failure;
async function bounded(promise,ms){let timer;try{return await Promise.race([promise.then(()=>true,()=>false),new Promise(r=>{timer=setTimeout(()=>r(false),ms);})]);}finally{clearTimeout(timer);}}
const ownedAlive=()=>{try{process.kill(server.process().pid,0);return true;}catch(e){return e.code!=='ESRCH';}};
try{
 browser=await chromium.connect(server.wsEndpoint(),{timeout:15000});const context=await browser.newContext({viewport:visible?{width:1280,height:720}:{width:1440,height:1000},deviceScaleFactor:1}),page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('response',r=>{if(r.status()>=400)resources.push({url:r.url(),status:r.status()});});
 const ready=()=>page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
 const settle=()=>page.evaluate(async()=>{for(let i=0;i<5;i++)await new Promise(r=>requestAnimationFrame(r));});
 const snapshot=()=>page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());
 const seek=t=>page.evaluate(t=>window.__QOIMA_STAND_V3__.cycle.seek(t),t);
 const verify=s=>{assert.equal(s.fixture,'picker-cart-walk-visual-QA');assert.equal(s.action.actorId,'P01');assert.equal(s.nodes.filter(n=>n==='actor__P01').length,1);assert.equal(s.nodes.filter(n=>n==='order-tote').length,1);assert(s.action.grip.hands.every(h=>h.error_m<2e-5&&h.axis_error<2e-5));assert(s.action.actualFeet.some(f=>f.target.stance));assert(s.action.actualFeet.every(f=>Math.abs(f.world[1]-f.target.lift)<1e-6));};
 await page.goto(url);await ready();await settle();const initial=await snapshot();verify(initial);await page.waitForTimeout(150);assert.equal((await snapshot()).action.time,0);checks.no_autoplay=true;
 assert.equal(await page.locator('#cycle-time').getAttribute('max'),'9');
 for(const [time,view] of [[0,'quarter'],[1.5,'side'],[2.5,'side'],[3.5,'quarter'],[4.5,'front'],[6.5,'side'],[7.5,'side'],[8,'side'],[9,'quarter']]){
  await seek(time);await page.evaluate(v=>window.__QOIMA_STAND_V3__.view(v),view);await settle();const state=await snapshot();verify(state);assert.equal(state.action.actor_uuid,initial.action.actor_uuid);assert.equal(state.action.cart_uuid,initial.action.cart_uuid);const file=`${out}/${String(time).replace('.','-')}-${view}.png`;await page.screenshot({path:file});frames.push({time,view,screenshot:file,state});
 }
 checks.same_actor_and_cart_across_seeks=true;
 await page.locator('#cycle-play').click();await page.waitForFunction(()=>window.__QOIMA_STAND_V3__.cycle.snapshot().time>.15);await page.locator('#cycle-play').click();const paused=await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.snapshot());assert(!paused.playing&&paused.time<2);await page.waitForTimeout(150);assert.equal((await snapshot()).action.time,paused.time);checks.play_pause_repeat=true;
 await page.locator('#cycle-play').click();await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>document.querySelector('#cycle-play').disabled);assert.equal(await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.play()),false);await seek(3.5);const reduced=await snapshot();verify(reduced);assert.equal(reduced.action.time,3.5);assert.equal(reduced.action.playing,false);assert.equal(reduced.presentation.camera_inertia,false);checks.live_reduced_motion=true;
 await page.locator('#cycle-time').focus();await page.keyboard.press('End');assert.equal((await snapshot()).action.time,9);checks.keyboard_seek=true;
 const cold=await context.newPage();await cold.emulateMedia({reducedMotion:'reduce'});await cold.goto(url);await cold.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');const coldState=await cold.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());verify(coldState);assert.equal(coldState.action.time,0);assert.equal(coldState.presentation.camera_inertia,false);assert(await cold.locator('#cycle-play').isDisabled());await cold.close();checks.cold_reduced_motion=true;
 await page.emulateMedia({reducedMotion:'no-preference'});const memories=[];
 for(let i=0;i<3;i++){await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('picking-cart-tote-fixture'));await ready();await settle();const s=await snapshot();verify(s);memories.push(s.renderer.memory);}
 assert.equal(new Set(memories.map(m=>JSON.stringify(m))).size,1);checks.replacement_memory=memories;
 const e0=errors.length,r0=resources.length;await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('zz-intentionally-missing-walk-model'));assert.equal((await snapshot()).phase,'error');assert(await page.locator('#cycle-controls').isHidden());expectedFailures.push({errors:errors.splice(e0),resources:resources.splice(r0)});await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('picking-cart-tote-fixture'));await ready();await settle();verify(await snapshot());assert.deepEqual((await snapshot()).renderer.memory,memories[0]);checks.error_cleanup_recovery=true;
 let entered;const routed=new Promise(r=>entered=r);await page.route('**/data/v3/picker-cart-walk.json',async route=>{entered();await new Promise(r=>setTimeout(r,200));await route.continue();});
 const old=page.evaluate(()=>window.__QOIMA_STAND_V3__.load('picking-cart-tote-fixture'));await routed;await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('picking-cart'));await old;await page.unroute('**/data/v3/picker-cart-walk.json');const stale=await snapshot();assert.equal(stale.modelId,'picking-cart');assert.equal(stale.action,null);assert.equal(stale.grip,null);assert(!stale.nodes.some(n=>n==='actor__P01'));checks.stale_timeline_request_does_not_resurrect_actor=true;
 await page.goto(base+'/stand-v3.html?asset=forklift-pallet-low-fixture&fixture=pickup');await ready();assert.equal(await page.locator('#cycle-time').getAttribute('max'),'30');await seek(14);const pallet=await snapshot();assert.equal(pallet.fixture,'pallet-pickup-visual-QA');assert.equal(pallet.action.time,14);assert(pallet.action.attached);await seek(30);assert((await snapshot()).action.complete);checks.pallet_cycle_controls_regression=true;
 assert.deepEqual(errors,[]);assert.deepEqual(resources,[]);
}catch(e){failure=e;}
let cleanup='graceful';if(!await bounded(server.close(),5000)){cleanup='forced_after_5s';await bounded(server.kill(),3000);if(ownedAlive()&&process.platform==='win32')await bounded(new Promise(r=>execFile('taskkill.exe',['/PID',String(server.process().pid),'/T','/F'],{windowsHide:true},()=>r())),3000);}
if(browser)await bounded(browser.close(),1000);
const lifecycle={owned_pid:server.process().pid,cleanup,terminated:!ownedAlive(),elapsed_ms:Date.now()-started};if(!lifecycle.terminated&&!failure)failure=Error('Owned browser did not terminate');
await writeFile(`${out}/browser-checks.json`,JSON.stringify({at:new Date().toISOString(),url,errors,failed_resources:resources,expected_failures:expectedFailures,frames,checks,lifecycle,failure:failure?String(failure):null},null,2)+'\n');
console.log(JSON.stringify({passed:!failure,captures:frames.length,checks,lifecycle,error:failure?String(failure):null}));process.exit(failure?1:0);
