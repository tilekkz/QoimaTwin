/** Current selected GLBs: actual browser four-view capture and source binding. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {chromium} from '@playwright/test';
const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),out=path.join(repo,'work/v3/full-tz-closeout-20261109/current-model-fourviews',new Date().toISOString().replaceAll(/[:.]/g,'-')),origin='http://127.0.0.1:4224',run=promisify(execFile),sha=b=>createHash('sha256').update(b).digest('hex');await fs.mkdir(out,{recursive:true});
const inventoryPath='docs/adaptive-v3/handoff/desktop-20261109/asset-manifest.json';
const inventory=JSON.parse(await fs.readFile(path.join(repo,inventoryPath),'utf8'));
const selected=new Map();for(const a of inventory.assets)if(a.path.startsWith('frontend/public/models/v3/'))selected.set(a.asset_id,a);
const skipAt=process.argv.indexOf('--skip-assets'),skipIds=new Set(skipAt>=0?process.argv[skipAt+1].split(','):[]);const models=[...selected.values()].filter(a=>!skipIds.has(a.asset_id));
const paths=[inventoryPath,'frontend/stand-v3.html','frontend/src/adaptive-v3/assetStand.ts','frontend/tools/check-current-model-fourviews-v3.mjs',...models.map(a=>a.path)];
const performanceOnly=process.argv.includes('--performance-only');
const pins=Object.fromEntries(await Promise.all(paths.map(async p=>[p,sha(await fs.readFile(path.join(repo,p)))])));
let server,browser,context,page,failure,owned=[],forced=false,cleanupComplete=false,functionalPassed=false,performanceResult=null;const cases=[],errors=[],consoleErrors=[],cleanup=[],captures=[],observations=[],failedRequests=[],diagnosticRequests=[],diagnosticConsole=[],consoleLocations=[],sourceTransitions=[],started=Date.now();
const bound=async(p,ms,label)=>{let timer;try{return await Promise.race([p,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error(label+' exceeded '+ms+'ms')),ms))]);}finally{clearTimeout(timer);}};
async function progress(stage){await fs.writeFile(path.join(out,'progress.json'),JSON.stringify({stage,cases,elapsed_ms:Date.now()-started,failure},null,2)+'\n');console.log(JSON.stringify({stage,cases:cases.length,elapsed_ms:Date.now()-started}));}
async function pass(name){cases.push(name);await progress(name);}
async function processRows(){const r=await run('pwsh',['-NoProfile','-NonInteractive','-Command',"Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,@{Name='CreationDate';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}},CommandLine | ConvertTo-Json -Compress"],{timeout:15000,windowsHide:true,maxBuffer:8*1024*1024});return JSON.parse(r.stdout||'[]');}
async function attest(){const pid=server.process().pid,rows=await processRows(),root=rows.find(r=>r.ProcessId===pid);if(root){assert.equal(root.ParentProcessId,process.pid);assert(root.CommandLine.includes('playwright_chromiumdev_profile-')&&root.CommandLine.includes('--headless'));}const ids=new Set([pid]);for(let i=0;i<12;i++){const size=ids.size;for(const row of rows)if(ids.has(row.ParentProcessId))ids.add(row.ProcessId);if(size===ids.size)break;}const map=new Map(owned.map(r=>[r.ProcessId,r]));for(const row of rows)if(ids.has(row.ProcessId))map.set(row.ProcessId,row);owned=[...map.values()];assert(owned.some(r=>r.ProcessId===pid));await fs.writeFile(path.join(out,'owned-processes.json'),JSON.stringify(owned,null,2)+'\n');}
async function closeOwned(){
 if(!server){cleanupComplete=true;return;}try{await attest();}catch(e){cleanup.push('Final attestation: '+e.message);}
 for(const[label,fn,ms]of [['CDP Browser.close',async()=>{if(browser?.isConnected()){const c=await bound(browser.newBrowserCDPSession(),2000,'CDP session');await c.send('Browser.close');}},5000],['context.close',()=>context?.close(),2000],['browser.close',()=>browser?.close(),2000],['server.close',()=>server.close(),3000]])try{await bound(Promise.resolve().then(fn),ms,label);cleanup.push(label+' returned');}catch(e){cleanup.push(e.message);}
 const saved=path.join(out,'owned-processes.json').replaceAll("'","''"),kill="$saved=Get-Content -LiteralPath '"+saved+"' -Raw|ConvertFrom-Json; foreach($item in @($saved)){ $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$item.ProcessId); if($p -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$item.CreationDate).ToUniversalTime().Ticks){ try{Stop-Process -Id $item.ProcessId -Force -ErrorAction Stop; Write-Output ('stopped_owned_'+$item.ProcessId)}catch{if(Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue){throw}} } }; exit 0";
 const stopped=await run('pwsh',['-NoProfile','-NonInteractive','-Command',kill],{timeout:15000,windowsHide:true});forced=stopped.stdout.includes('stopped_owned_');cleanup.push(stopped.stdout.trim()||'No live attested process required fallback');try{await bound(server.kill(),5000,'Owned server transport release');cleanup.push('Owned server transport released');}catch(e){cleanup.push(e.message);}
 const verify="$saved=Get-Content -LiteralPath '"+saved+"' -Raw|ConvertFrom-Json; $live=@(); foreach($item in @($saved)){ if(Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue){$live+=$item.ProcessId} }; ConvertTo-Json -InputObject @($live) -Compress; exit 0";
 await new Promise(resolve=>setTimeout(resolve,2000));const fresh=await run('pwsh',['-NoProfile','-NonInteractive','-Command',verify],{timeout:15000,windowsHide:true});const remaining=JSON.parse(fresh.stdout||'[]');cleanupComplete=owned.length>0&&remaining.length===0;await fs.writeFile(path.join(out,'fresh-process-absence.json'),JSON.stringify({remaining_PIDs:remaining,cleanup_complete:cleanupComplete,identity_before_fallback:'Exact saved PID+CIM creation time, root headless uniqueprofile+parent; only attested descendants',absence_check:'Fresh Get-Process by every saved PID, without timestamp filtering'},null,2)+'\n');
}

const actualModels=[];let current='startup';
const snapshot=()=>page.evaluate(()=>window.__QOIMA_STAND_V3__.snapshot());
const frames=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
try{
 const executablePath=process.env.QOIMA_TEST_BROWSER_PATH??path.join(process.env.LOCALAPPDATA??'','ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe');await fs.access(executablePath);server=await chromium.launchServer({executablePath,headless:true,args:['--mute-audio','--no-proxy-server']});await attest();
 browser=await chromium.connect(server.wsEndpoint());context=await browser.newContext({viewport:{width:1600,height:1060},deviceScaleFactor:1,reducedMotion:'reduce'});page=await context.newPage();
 page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});
 const served=new Map();page.on('response',async response=>{if(response.url().includes('/models/v3/')&&response.url().endsWith('.glb')&&response.ok())try{served.set(new URL(response.url()).pathname,sha(await response.body()));}catch{}});
 await page.goto(origin+'/stand-v3.html?asset='+encodeURIComponent(models[0].asset_id),{waitUntil:'commit',timeout:15000});
 for(const [index,model]of models.entries()){
  current=model.asset_id;
  if(index)await page.evaluate(id=>window.__QOIMA_STAND_V3__.load(id),model.asset_id);
  await page.waitForFunction(()=>['ready','error'].includes(window.__QOIMA_STAND_V3__?.snapshot().phase),null,{timeout:index?45000:120000});
  const initial=await snapshot();assert.equal(initial.phase,'ready',model.asset_id+': '+await page.locator('#status').textContent());assert.equal(initial.modelId,model.asset_id);
  const url='/models/v3/'+model.asset_id+'.glb';
  await page.waitForTimeout(60);assert.equal(served.get(url),model.sha256,'actual served GLB hash '+model.asset_id);
  assert(initial.triangles>0&&initial.materials.length>0);const folder=path.join(out,model.asset_id);await fs.mkdir(folder,{recursive:true});
  const views=[];
  for(const view of ['front','rear','side','quarter']){
   await page.evaluate(v=>window.__QOIMA_STAND_V3__.view(v),view);await frames();const state=await snapshot();
   assert.equal(state.view,view);assert.deepEqual(state.dimensions_m,initial.dimensions_m);assert.equal(state.triangles,initial.triangles);
   const b=state.screen_bounds_px,c=state.canvas;assert(b&&b.min_x>=-1&&b.min_y>=-1&&b.max_x<=c.width+1&&b.max_y<=c.height+1,'four-view frame clips native geometry '+model.asset_id+'/'+view);
   const file=path.join(folder,view+'.png');const clip=await page.locator('#canvas-host').boundingBox();assert(clip&&clip.width>0&&clip.height>0);await page.screenshot({path:file,clip,timeout:90000});views.push({view,file:path.relative(repo,file).replaceAll('\\','/'),image_sha256:sha(await fs.readFile(file)),state});
  }
  actualModels.push({asset_id:model.asset_id,path:model.path,model_sha256:model.sha256,served_url:url,served_sha256:served.get(url),views,independent_reference:await page.locator('#reference').getAttribute('src')});
  await progress(model.asset_id);
 }
 await pass('all_selected_native_GLB_bytes_loaded_with_materials_finite_dimensions_and_four_unclipped_views');
 assert.deepEqual(errors,[]);assert.deepEqual(consoleErrors,[]);for(const[p,h]of Object.entries(pins))assert.equal(sha(await fs.readFile(path.join(repo,p))),h,'source drift '+p);
 functionalPassed=true;
}catch(error){failure={current,error:String(error),stack:error.stack};}
finally{try{await closeOwned();}catch(error){cleanup.push(String(error));}}
const report={schema_id:'qoima.current-selected-model-fourviews.v1',passed:functionalPassed&&cleanupComplete,functional_passed:functionalPassed,source_kind:'visual_fixture',engine_operation:false,source_hashes:pins,models:actualModels,selected_model_count:models.length,actual_model_count:actualModels.length,view_count:actualModels.reduce((n,m)=>n+m.views.length,0),cases,errors,consoleErrors,failure,cleanup_complete:cleanupComplete,forced_cleanup:forced,cleanup,root_visual_review:'PENDING: capture and framing assertions do not by themselves accept design/reference match',duration_s:(Date.now()-started)/1000};
await fs.writeFile(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:report.passed,models:actualModels.length,views:report.view_count,failure,out}));
process.exit(report.passed?0:1);
