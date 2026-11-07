import {chromium} from '@playwright/test';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
const assets=process.argv.slice(2);if(!assets.length)assets.push('calibration');
if(assets.some(a=>!/^[a-z0-9][a-z0-9-]{0,63}$/.test(a)))throw Error('Invalid asset ID');
const views=(process.env.QOIMA_STAND_VIEWS||'front,side,rear,quarter').split(',');
if(views.some(v=>!['front','side','rear','quarter','top'].includes(v)))throw Error('Invalid view');
const base=process.env.QOIMA_STAND_BASE_URL||'http://127.0.0.1:4173';
const visible=process.env.QOIMA_VISIBLE_TESTS==='1',viewport=visible?{width:1280,height:720}:{width:1440,height:1000};
const variant=process.env.QOIMA_STAND_FIXTURE,focus=process.env.QOIMA_STAND_FOCUS;
const poseFile=process.env.QOIMA_STAND_POSE;
const pose=poseFile?JSON.parse(await readFile(poseFile,'utf8')):null;
if(pose&&Object.entries(pose).some(([name,angles])=>!/^joint__[a-zA-Z_]+$/.test(name)||!Array.isArray(angles)||angles.length!==3||!angles.every(Number.isFinite)))throw Error('Invalid inspection pose');
if(variant&&!['roles','pickup','driver','grip'].includes(variant))throw Error('Invalid fixture variant');
async function bounded(promise,ms){let timer;try{return await Promise.race([promise.then(()=>true,()=>false),new Promise(r=>{timer=setTimeout(()=>r(false),ms);})]);}finally{clearTimeout(timer);}}
const started=Date.now();
const server=await chromium.launchServer({channel:'chrome',headless:!visible,args:['--mute-audio'],timeout:30000});
const outputs=[];let browser,failure;
const ownedAlive=()=>{try{process.kill(server.process().pid,0);return true;}catch(error){if(error.code==='ESRCH')return false;return true;}};
async function settleExit(ms){if(!ownedAlive())return;const child=server.process();let listener;try{await bounded(new Promise(r=>{listener=()=>r();child.once('exit',listener);}),ms);}finally{if(listener)child.off('exit',listener);}}
try{
 browser=await chromium.connect(server.wsEndpoint(),{timeout:15000});
 const context=await browser.newContext({viewport,deviceScaleFactor:1});
 const launchMs=Date.now()-started;
 for(const asset of assets){
  const at=Date.now(),override=process.env.QOIMA_STAND_OUTPUT;
  const out=override?(assets.length===1?override:`${override}/${asset}`):`../assets/v3/qa-browser/${asset}`;
  await mkdir(out,{recursive:true});outputs.push(out);
  const page=await context.newPage(),errors=[],frames=[],failedResources=[];let fixtureChecks;
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('response',r=>{if(r.status()>=400)failedResources.push({url:r.url(),status:r.status()});});
  try{
   await page.goto(`${base}/stand-v3.html?asset=${asset}${variant?'&fixture='+variant:''}`);await page.waitForFunction(()=>document.querySelector('main')?.dataset.phase==='ready');
   if(pose)await page.evaluate(p=>{for(const [name,rotation] of Object.entries(p))window.__QOIMA_STAND_V3__.setNode(name,{rotation});},pose);
   for(const view of views){
    await page.evaluate(({view,focus})=>focus?window.__QOIMA_STAND_V3__.focus(focus,view):window.__QOIMA_STAND_V3__.view(view),{view,focus});
    await page.evaluate(async()=>{for(let i=0;i<5;i++)await new Promise(r=>requestAnimationFrame(r));});
    await page.screenshot({path:`${out}/${view}.png`});
    frames.push({view,screenshot:`${out}/${view}.png`,state:await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot())});
   }
   if(variant==='grip'){
    const verify=state=>{if(state.grip?.actorId!=='P01'||state.nodes.filter(n=>n==='actor__P01').length!==1||state.nodes.filter(n=>n==='order-tote').length!==1||state.grip.hands.some(h=>h.error_m>2e-5||h.axis_error>2e-5))throw Error('Picker/cart instance or contact invariant failed');};
    frames.forEach(f=>verify(f.state));
    if(new Set(frames.map(f=>f.state.grip.actor_uuid)).size!==1||new Set(frames.map(f=>f.state.grip.cart_uuid)).size!==1)throw Error('Actor/cart identity changed across views');
    fixtureChecks={same_actor_uuid_across_views:true,replacements:[],world_transform_checks:[]};
    // GPU counters after whole-asset replacement reveal leaked worker templates
    // or role-owned badge geometry. Only this stand owns the sample instance.
    for(let i=0;i<3;i++){
     await page.evaluate(async asset=>{await window.__QOIMA_STAND_V3__.load(asset);for(let n=0;n<5;n++)await new Promise(r=>requestAnimationFrame(r));},asset);
     const state=await page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());verify(state);fixtureChecks.replacements.push(state.renderer.memory);
    }
    if(new Set(fixtureChecks.replacements.map(s=>JSON.stringify(s))).size!==1)throw Error('Picker fixture GPU resource count grew on replacement');
    for(const yaw of [-.7,.3,1.2]){
     const state=await page.evaluate(yaw=>{const api=window.__QOIMA_STAND_V3__;api.setNode('picking-cart-tote-fixture',{position:[2,0,-1],rotation:[0,yaw,0]});return api.snapshot();},yaw);verify(state);fixtureChecks.world_transform_checks.push(state.grip);
    }
   }
   await writeFile(`${out}/browser-capture.json`,JSON.stringify({at:new Date().toISOString(),browser:browser.version(),url:page.url(),visible,viewport,errors,failedResources,frames,fixture_checks:fixtureChecks,timing_ms:{shared_browser_launch:launchMs,asset_capture:Date.now()-at}},null,2));
   if(errors.length||failedResources.length)throw Error(JSON.stringify({errors,failedResources}));
   console.log(JSON.stringify({asset,captures:frames.length,errors:0,failedResources:0,capture_ms:Date.now()-at,out}));
  }catch(error){await writeFile(`${out}/failure.json`,JSON.stringify({error:String(error),errors,failedResources},null,2));throw error;}
  finally{if(!await bounded(page.close(),3000))throw Error('Owned QA page shutdown exceeded3seconds');}
 }
}catch(error){failure=error;}
let cleanup='graceful';
if(!await bounded(server.close(),5000)){
 cleanup='forced_after_5s';
 await bounded(server.kill(),3000);await settleExit(1000);
 if(ownedAlive()&&process.platform==='win32'){
  // The PID belongs to this launchServer call, never an enumerated user browser.
  await bounded(new Promise(r=>execFile('taskkill.exe',['/PID',String(server.process().pid),'/T','/F'],{windowsHide:true},()=>r())),3000);
  await settleExit(1000);
 }
}
if(browser)await bounded(browser.close(),1000);
const lifecycle={owned_pid:server.process().pid,cleanup,terminated:!ownedAlive(),termination_check:'owned PID OS probe after bounded exit wait',elapsed_ms:Date.now()-started};
for(const out of outputs)await writeFile(`${out}/browser-lifecycle.json`,JSON.stringify(lifecycle,null,2));
if(!lifecycle.terminated&&!failure)failure=Error('Owned QA browser did not terminate');
if(failure)console.error(String(failure));
await new Promise(r=>process.stdout.write(JSON.stringify({browser_lifecycle:lifecycle})+'\n',r));
// Artifacts are flushed; stale WS handles must not keep this CLI alive.
process.exit(failure?1:0);
