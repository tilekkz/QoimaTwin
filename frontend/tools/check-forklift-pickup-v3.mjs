import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {chromium} from '@playwright/test';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {validatePickupTimeline,pickupAt,createPickupFixture} from '../src/adaptive-v3/forkliftPickup.ts';

const out='../assets/v3/qa-browser/forklift-pickup-cycle';await mkdir(out,{recursive:true});
const raw=await readFile('public/data/v3/pallet-pickup-cycle.json','utf8'),timeline=validatePickupTimeline(JSON.parse(raw));
const sha=b=>createHash('sha256').update(b).digest('hex');
const proof=JSON.parse(await readFile('../assets/v3/iterations/forklift/M14.8/actual-pickup-continuous-checks.json','utf8'));
assert.equal(proof.timeline_sha256,sha(raw));assert.equal(proof.native_fixture_source_sha256,sha(await readFile('../assets/v3/blender/forklift-pallet-low-fixture.blend')));
const bytes=await readFile('public/models/v3/forklift-pallet-low-fixture.glb');
const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
const fixture=createPickupFixture(gltf.scene,timeline),uuid=fixture.snapshot().cargoUuid;
const near=(actual,expected,tol=2e-6)=>{assert.equal(actual.length,expected.length);assert(actual.every((v,i)=>Math.abs(v-expected[i])<tol),JSON.stringify({actual,expected}));};
near(pickupAt(timeline,0).HU_world,[0,.18,1.4]);near(pickupAt(timeline,14).HU_world,[0,.7,-.05]);
for(const t of [8,22])near(pickupAt(timeline,t-1e-8).HU_world,pickupAt(timeline,t+1e-8).HU_world);
const bad=JSON.parse(raw);bad.keys[2].reach=0;assert.throws(()=>validatePickupTimeline(bad));
assert.throws(()=>pickupAt(timeline,NaN));
function digest(){gltf.scene.updateMatrixWorld(true);const rows=[];gltf.scene.traverse(n=>rows.push([n.uuid,...n.matrixWorld.toArray().map(v=>Math.round(v*1e8)/1e8)]));return sha(JSON.stringify(rows.sort((a,b)=>String(a[0]).localeCompare(String(b[0])))));}
const times=[0,2,4,6,8,9,10,12,14,16,18,20,21,22,24,26,28,30,7.999999,22.000001];const expected=new Map();
for(const t of times){fixture.apply(t);expected.set(t,digest());}
for(let j=0;j<5;j++)for(const t of [...times].sort((a,b)=>Math.sin(a*31+j)-Math.sin(b*31+j))){
 const s=fixture.apply(t);assert.equal(s.cargoUuid,uuid);near(s.actualHUWorld,s.HU_world);assert.equal(digest(),expected.get(t));let hu=0;gltf.scene.traverse(n=>{if(n.name==='pallet-load__HU')hu++;});assert.equal(hu,1);
}
fixture.apply(30);assert.equal(fixture.snapshot().complete,true);assert.deepEqual(fixture.snapshot().exclusive_resources,[]);
const report={at:new Date().toISOString(),source_kind:'visual_fixture',timeline_sha256:sha(raw),native_proof_bound:true,deterministic_node_seeks:100,single_HU_identity:true,attach_release_world_continuity:true,invalid_low_retracted_rejected:true,browser_frames:[],browser_checks:{},errors:[]};
async function bounded(p,ms){let timer;try{return await Promise.race([p.then(()=>true,()=>false),new Promise(r=>{timer=setTimeout(()=>r(false),ms);})]);}finally{clearTimeout(timer);}}
const started=Date.now(),server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio'],timeout:30000});let browser,failure;
const alive=()=>{try{process.kill(server.process().pid,0);return true;}catch(e){return e.code!=='ESRCH';}};
try{
 browser=await chromium.connect(server.wsEndpoint());const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1,reducedMotion:'no-preference'});
 const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
 const url='http://127.0.0.1:4173/stand-v3.html?asset=forklift-pallet-low-fixture&fixture=pickup';
 await page.goto(url);await page.waitForFunction(()=>window.__QOIMA_STAND_V3__?.snapshot().phase==='ready'&&window.__QOIMA_STAND_V3__.cycle.snapshot());
 const state=()=>page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.snapshot());const initial=await state();assert.equal(initial.time,0);assert.equal(initial.playing,false);
 await page.waitForTimeout(200);assert.equal((await state()).time,0);report.browser_checks.no_autoplay=true;
 const served=await (await context.request.get('http://127.0.0.1:4173/data/v3/pallet-pickup-cycle.json')).text();assert.equal(sha(served),sha(raw));
 for(const t of [0,4,6,8,9,12,14,20,21,22,24,26,30]){
  await page.evaluate(t=>{window.__QOIMA_STAND_V3__.cycle.seek(t);window.__QOIMA_STAND_V3__.view('quarter');},t);
  await page.evaluate(async()=>{for(let i=0;i<5;i++)await new Promise(r=>requestAnimationFrame(r));});
  const s=await state();assert.equal(s.cargoUuid,initial.cargoUuid);near(s.actualHUWorld,pickupAt(timeline,t).HU_world);assert.equal(s.HU_count,1);
  const paired=await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot().driver);
  assert.equal(paired.actorId,'F01');assert.equal(paired.role,'forklift_driver');assert.equal(paired.warehouse_headcount_delta,0);near(paired.root_local,[0,.29,-.615]);near(paired.scale,[1,1,1]);
  assert(paired.seat_error_m<2e-5&&Object.values(paired.grip_error_m).every(v=>v<2e-5)&&Object.values(paired.sole_error_m).every(v=>v<2e-5));
  await page.screenshot({path:`${out}/t${String(t).padStart(2,'0')}-quarter.png`});report.browser_frames.push({time_s:t,state:s,driver:paired});
 }
 await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.seek(8));await page.locator('#cycle-play').click();await page.waitForTimeout(250);assert((await state()).time>8);
 await page.locator('#cycle-play').click();const paused=await state();await page.waitForTimeout(200);assert.equal((await state()).time,paused.time);report.browser_checks.play_pause=true;
 await page.locator('#cycle-play').click();await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(100);
 const reduced=await state();assert.equal(reduced.playing,false);assert.equal(await page.locator('#cycle-play').isDisabled(),true);
 assert.equal((await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot())).presentation.camera_inertia,false);
 await page.locator('[data-cycle-time="30"]').click();assert.equal((await state()).complete,true);
 await page.locator('[data-cycle-time="8"]').click();await page.waitForTimeout(150);assert.equal((await state()).time,8);
 await page.screenshot({path:`${out}/reduced-static-pickup.png`});report.browser_checks.live_reduce_pauses_and_static_phases_work=true;
 await page.locator('#cycle-time').focus();await page.keyboard.press('End');assert.equal((await state()).time,30);await page.keyboard.press('Home');assert.equal((await state()).time,0);await page.keyboard.press('ArrowRight');assert.equal((await state()).time,.01);report.browser_checks.reduced_keyboard_seek=true;
 await page.reload();await page.waitForFunction(()=>window.__QOIMA_STAND_V3__?.cycle.snapshot());assert.equal((await state()).time,0);assert.equal((await state()).playing,false);report.browser_checks.cold_reduce_static=true;
 await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForTimeout(50);assert.equal((await state()).playing,false);
 await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.seek(30));await page.locator('#cycle-play').click();await page.waitForTimeout(100);assert((await state()).time>0&&(await state()).time<1);await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.pause());report.browser_checks.explicit_replay=true;
 await page.route('**/data/v3/pallet-pickup-cycle.json',route=>route.fulfill({status:200,contentType:'application/json',body:'{}'}));
 await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('forklift-pallet-low-fixture'));assert.equal((await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot())).phase,'error');assert.equal(await page.locator('#cycle-controls').isHidden(),true);report.browser_checks.invalid_timeline_error_cleanup=true;
 await page.unroute('**/data/v3/pallet-pickup-cycle.json');
 let release,arrived;const pending=new Promise(r=>{arrived=r;});const gate=new Promise(r=>{release=r;});
 await page.route('**/data/v3/pallet-pickup-cycle.json',async route=>{arrived();await gate;await route.fulfill({status:200,contentType:'application/json',body:raw});});
 await page.evaluate(()=>{void window.__QOIMA_STAND_V3__.load('forklift-pallet-low-fixture');});await pending;
 await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('calibration'));release();await page.waitForTimeout(100);
 const switched=await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());assert.equal(switched.modelId,'calibration');assert.equal(switched.phase,'ready');assert.equal(switched.action,null);assert.equal(switched.driver,null);assert.equal(await page.locator('#cycle-controls').isHidden(),true);report.browser_checks.stale_async_load_does_not_replace_new_model=true;
 await page.unroute('**/data/v3/pallet-pickup-cycle.json');
 const memories=[];
 for(let i=0;i<3;i++){
  await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('forklift-pallet-low-fixture'));await page.evaluate(()=>window.__QOIMA_STAND_V3__.cycle.seek(14));
  await page.evaluate(()=>window.__QOIMA_STAND_V3__.load('calibration'));await page.waitForTimeout(50);
  memories.push((await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot())).renderer.memory);
 }
 assert.equal(memories[0].geometries,memories.at(-1).geometries);assert.equal(memories[0].textures,memories.at(-1).textures);report.browser_checks.repeated_load_resources_stable=memories;
 assert.deepEqual(report.errors,[]);await writeFile(`${out}/browser-action-checks.json`,JSON.stringify(report,null,2)+'\n');
 await page.close();
}catch(e){failure=e;await writeFile(`${out}/failure.json`,JSON.stringify({error:String(e),stack:e.stack,report},null,2)+'\n');}
let cleanup='graceful';if(!await bounded(server.close(),5000)){cleanup='forced_after_5s';await bounded(server.kill(),3000);if(alive()&&process.platform==='win32')await bounded(new Promise(r=>execFile('taskkill.exe',['/PID',String(server.process().pid),'/T','/F'],{windowsHide:true},()=>r())),3000);}
if(browser)await bounded(browser.close(),1000);
// Give only this owned process a bounded exit window before probing its PID.
if(alive())await bounded(new Promise(r=>server.process().once('exit',r)),1000);
const lifecycle={owned_pid:server.process().pid,cleanup,terminated:!alive(),elapsed_ms:Date.now()-started};await writeFile(`${out}/browser-lifecycle.json`,JSON.stringify(lifecycle,null,2)+'\n');
if(!lifecycle.terminated&&!failure)failure=Error('Owned QA browser did not terminate');if(failure)console.error(failure);
console.log(JSON.stringify({passed:!failure,node_seeks:100,browser_frames:report.browser_frames.length,browser_checks:Object.keys(report.browser_checks),browser_lifecycle:lifecycle}));process.exit(failure?1:0);
