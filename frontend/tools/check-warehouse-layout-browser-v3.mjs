import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {chromium} from '@playwright/test';
const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),out=path.join(repo,'work/v3/warehouse-layout-browser-20261109',String(Date.now()));
await mkdir(out,{recursive:true});const sha=b=>createHash('sha256').update(b).digest('hex'),plan=JSON.parse(await readFile(path.join(repo,'work/v3/warehouse-density-20261109/candidate-layout.json'),'utf8'));
const inputs={};for(const rel of ['frontend/tools/check-warehouse-layout-browser-v3.mjs','frontend/src/adaptive-v3/twin/twinPage.ts','frontend/src/adaptive-v3/twin/twinRender.ts','frontend/src/adaptive-v3/twin/twinLayoutVariant.ts','frontend/src/adaptive-v3/twin/twinMinimap.ts','frontend/src/adaptive-v3/warehouseLayoutPlan.ts','frontend/src/adaptive-v3/warehouseLayoutAccess.ts','frontend/src/adaptive-v3/twin/twinLayoutControls.ts','frontend/twin-v3.html'])inputs[rel]=sha(await readFile(path.join(repo,rel)));
const origin=process.env.QOIMA_QA_ORIGIN??'http://127.0.0.1:4224';assert.equal(new URL(origin).hostname,'127.0.0.1');
let server,browser,context,page,failure;const cases=[],errors=[],consoleErrors=[],cleanup=[],started=Date.now();let owned=[],forced=false,cleanupComplete=false;
const run=promisify(execFile),snap=()=>page.evaluate(()=>window.__QOIMA_TWIN_V3__.snapshot());
const bounded=async(p,ms,label)=>{let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' exceeded '+ms+'ms')),ms);})]);}finally{clearTimeout(timer);}};
async function checkpoint(stage){const value={stage,elapsed_ms:Date.now()-started,cases:[...cases],failure,owned_processes:owned};await writeFile(path.join(out,'progress.json'),JSON.stringify(value,null,2)+'\n');console.log(JSON.stringify({stage,elapsed_ms:value.elapsed_ms,cases:cases.length}));}
async function passCase(name){cases.push(name);await checkpoint('PASS '+name);}
async function processRows(){const r=await run('powershell',['-NoProfile','-NonInteractive','-Command',"Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,@{Name='CreationDate';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}},CommandLine | ConvertTo-Json -Compress"],{timeout:5000,windowsHide:true,maxBuffer:8*1024*1024});return JSON.parse(r.stdout||'[]');}
async function attest(){
 const pid=server?.process().pid;if(!pid)return;const rows=await processRows(),root=rows.find(r=>r.ProcessId===pid);
 if(root){assert.equal(root.ParentProcessId,process.pid,'Browser server must be this runner direct child');assert(root.CommandLine?.includes('playwright_chromiumdev_profile-')&&root.CommandLine.includes('--headless'),'Unique headless Playwright profile required');}
 const ids=new Set([pid]);for(let i=0;i<12;i++){const n=ids.size;for(const row of rows)if(ids.has(row.ParentProcessId))ids.add(row.ProcessId);if(ids.size===n)break;}
 const map=new Map(owned.map(r=>[r.ProcessId,r]));for(const r of rows)if(ids.has(r.ProcessId))map.set(r.ProcessId,r);owned=[...map.values()];
 assert(owned.some(r=>r.ProcessId===pid),'Owned browser identity was never attested');await writeFile(path.join(out,'owned-processes.json'),JSON.stringify(owned,null,2)+'\n');
}
async function liveOwned(){
 const payload=Buffer.from(JSON.stringify(owned.map(({ProcessId,CreationDate})=>({ProcessId,CreationDate})))).toString('base64');
 const code="$saved = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+payload+"')) | ConvertFrom-Json; $live=@(); foreach ($item in @($saved)) { $p=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue; if ($p -and $p.StartTime.ToUniversalTime().Ticks -eq ([datetime]$item.CreationDate).ToUniversalTime().Ticks) { $live += $p.Id } }; ConvertTo-Json -InputObject @($live) -Compress";
 const result=await run('powershell',['-NoProfile','-NonInteractive','-Command',code],{timeout:5000,windowsHide:true});return JSON.parse(result.stdout||'[]');
}
async function closeOwned(){
 await checkpoint('cleanup-start');try{await attest();}catch(e){cleanup.push('Final attestation: '+e.message);}
 async function attempt(label,action,ms){try{await bounded(action(),ms,label);cleanup.push(label+' returned');}catch(e){cleanup.push(label+': '+e.message);}}
 if(browser?.isConnected())await attempt('Native CDP Browser.close',async()=>{const cdp=await bounded(browser.newBrowserCDPSession(),2000,'CDP session');await cdp.send('Browser.close');},5000);
 if(context)await attempt('Context close',()=>context.close(),2000);
 if(browser)await attempt('Browser disconnect',()=>browser.close(),2000);
 if(server)await attempt('Browser server close',()=>server.close(),3000);
 let rows=await processRows(),live=owned.filter(s=>rows.some(r=>r.ProcessId===s.ProcessId&&r.CreationDate===s.CreationDate));
 if(live.length){
  const payload=Buffer.from(JSON.stringify(live)).toString('base64');
  const code="$saved = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+payload+"')) | ConvertFrom-Json; foreach ($item in @($saved)) { $current = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $item.ProcessId); if ($current -and $current.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$item.CreationDate).ToUniversalTime().Ticks) { try { Stop-Process -Id $item.ProcessId -Force -ErrorAction Stop; Write-Output ('stopped_owned_' + $item.ProcessId) } catch { if (Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue) { throw } } } }";
  const result=await run('powershell',['-NoProfile','-NonInteractive','-Command',code],{timeout:6000,windowsHide:true});forced=result.stdout.includes('stopped_owned_');cleanup.push(result.stdout.trim()||'Attested processes exited before fallback');
  if(server)await attempt('Browser server transport release',()=>server.kill(),2000);
 }
 // CIM may retain already-exiting process rows; verify actual live process handles too.
 const remaining=await liveOwned();cleanupComplete=owned.length>0&&remaining.length===0;cleanup.push('Direct Get-Process remaining owned count '+remaining.length);await checkpoint('cleanup-complete');
}
const ready=()=>page.waitForFunction(()=>{const s=window.__QOIMA_TWIN_V3__?.snapshot();return s?.phase==='ready'&&!s.layout.busy;},null,{timeout:45000});
const frames=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
function conserved(s,base){assert.equal(s.scene.stock_HUs,530);assert.equal(s.scene.cargo_binding_count,530);assert.equal(s.scene.workers,24);assert.deepEqual(s.scene.stock_positions,base.scene.stock_positions);assert.deepEqual(s.scene.worker_ids,base.scene.worker_ids);assert.deepEqual(s.scene.vehicle_poses,base.scene.vehicle_poses);assert.equal(s.scene.actions_scheduled,0);assert.equal(s.scene.completed_jobs,0);}
async function mode(value){await page.evaluate(v=>window.__QOIMA_TWIN_V3__.setLayoutMode(v),value);await ready();await frames();assert.equal((await snap()).layout.mode,value);}
async function searchFor(q,{B=false}={}){await page.locator('#tw-search-btn').click();await page.locator('#tw-search-input').fill(q);await page.locator('#tw-search-input').press(B?'Shift+Enter':'Enter');await frames();}
function nearXZ(actual,expected){assert(Math.hypot(actual[0]-expected[0],actual[2]-expected[2])<1e-6,JSON.stringify({actual,expected}));}
try{await bounded((async()=>{
 await checkpoint('launch');
 server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio','--no-proxy-server']});browser=await chromium.connect(server.wsEndpoint());context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});page=await context.newPage();page.setDefaultTimeout(10000);page.setDefaultNavigationTimeout(60000);page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('CONTEXT_LOST_WEBGL'))consoleErrors.push(m.text());});
 await attest();await checkpoint('cold-navigation');
 await page.goto(origin+'/twin-v3.html?layout=sections',{waitUntil:'domcontentloaded'});await ready();let s=await snap();const base=s;
 assert.equal(s.layout.mode,'sections');assert.equal(s.layout.render.module_count,plan.modules.length);assert.equal(s.layout.render.HU_count,530);assert.equal(s.layout.render.added_empty_modules,plan.modules.filter(m=>m.is_new).length);assert.equal(s.layout.render.A_restored,true);assert.equal(s.layout.access.ok,true);assert.equal(s.layout.access.required_heavy_HUs,35);await passCase('cold_B_actual_sections_and_empty_racks_after_access_guard');await page.screenshot({path:path.join(out,'dense-B.png')});
 await page.locator('[data-open="diff"]').first().click();await page.locator('[data-layout="cargo"]').click();await ready();s=await snap();assert.equal(s.layout.mode,'cargo');assert.equal(s.layout.counts.racksB,132);assert.equal(s.layout.render,null);assert(s.moves.length>0);conserved(s,base);await passCase('native_control_restores_cargo_only_B');
 await page.locator('[data-layout="sections"]').click();await ready();s=await snap();assert.equal(s.layout.mode,'sections');assert.equal(s.moves.length,0);assert.equal(s.layout.render.plan_sha256,plan.plan_sha256);assert.equal(s.layout.render.A_restored,true);conserved(s,base);await passCase('native_control_restores_structural_B_without_greedy_HU_double_move');await page.screenshot({path:path.join(out,'layout-controls.png')});await page.keyboard.press('Escape');
 for(let i=0;i<8;i++){await mode(i%2?'sections':'cargo');conserved(await snap(),base);}assert.equal((await snap()).layout.render.added_empty_modules,32);await passCase('repeated_switches_no_inventory_or_actor_duplication');
 const firstHU=plan.HUs.find(h=>plan.modules.find(m=>m.module_id===h.target_module_id)?.family==='SMALL');assert(firstHU);const sku=firstHU.handling_unit_id.match(/DEMO_\d+/)[0];await searchFor(sku,{B:true});s=await snap();assert.equal(s.selected,firstHU.handling_unit_id);nearXZ(s.motion.camera.target,[firstHU.position_world[0],0,firstHU.position_world[2]+84]);await passCase('B_HU_search_focus_uses_rigid_new_slot_position');await page.keyboard.press('Escape');
 const slot=plan.slots.find(s=>s.is_new&&!s.reserve_only&&!s.retrieval_blocked);assert(slot);await searchFor(slot.slot_id);s=await snap();nearXZ(s.motion.camera.target,[slot.bin_anchor_world[0],slot.bin_anchor_world[1],slot.bin_anchor_world[2]+84]);await passCase('new_empty_slot_search_is_B_only_and_uses_new_frame');
 await searchFor('SMALL_E',{B:true});s=await snap();const zone=plan.zones.find(z=>z.zone_id==='SMALL_E').floor_bounds_xz_m;nearXZ(s.motion.camera.target,[(zone.min[0]+zone.max[0])/2,0,(zone.min[1]+zone.max[1])/2+84]);await passCase('B_zone_search_uses_resized_section');await page.screenshot({path:path.join(out,'small-B-close.png')});
 for(const t of [300,1,179,0]){await page.evaluate(t=>window.__QOIMA_TWIN_V3__.seek(t),t);await frames();s=await snap();conserved(s,base);assert.equal(s.layout.render.A_restored,true);}await passCase('absolute_seek_does_not_rebuild_or_duplicate_layout');
 for(const m of ['swipe','side']){await page.evaluate(m=>window.__QOIMA_TWIN_V3__.setMode(m),m);await frames();s=await snap();assert.equal(s.layout.render.A_restored,true);assert.equal(s.layout.render.module_count,164);}await passCase('shared_camera_modes_keep_A_restored');
 await page.reload({waitUntil:'domcontentloaded'});await ready();s=await snap();assert.equal(s.layout.render.plan_sha256,plan.plan_sha256);conserved(s,base);await passCase('reload_deterministic_same_plan_and_business_inputs');
 await page.goto(origin+'/twin-v3.html?layout=cargo',{waitUntil:'domcontentloaded'});await ready();s=await snap();assert.equal(s.layout.mode,'cargo');assert.equal(s.layout.render,null);await mode('sections');s=await snap();assert.equal(s.layout.render.plan_sha256,plan.plan_sha256);conserved(s,base);await passCase('cargo_deep_link_then_structural_plan_recovers');
 await page.evaluate(()=>{window.__QOIMA_TWIN_V3__.seek(60);window.__QOIMA_TWIN_V3__.setSheet('now');});await page.locator('.tw-issue[data-k="B:STANDARD_E"]').hover();await frames();s=await snap();conserved(s,base);assert.equal(s.layout.render.A_restored,true);await page.screenshot({path:path.join(out,'B-state-hover.png')});await passCase('actual_B_STANDARD_issue_hover_preserves_layout_and_stock');
 assert.deepEqual(errors,[]);assert.deepEqual(consoleErrors,[]);
})(),150000,'Desktop layout checks');
}catch(e){failure=e.stack??String(e);try{await page?.screenshot({path:path.join(out,'RED.png'),timeout:5000});}catch{}}
finally{await checkpoint('assertions-finished');try{await bounded(closeOwned(),40000,'Owned browser cleanup');}catch(e){cleanup.push(e.message);}}
const drift=[];for(const [rel,pin]of Object.entries(inputs))if(sha(await readFile(path.join(repo,rel)))!==pin)drift.push(rel);
const report={passed:!failure&&!drift.length&&cleanupComplete,assertions_passed:!failure&&!drift.length,desktop_only:true,cases,errors,console_errors:consoleErrors,failure,cleanup_complete:cleanupComplete,normal_cleanup:cleanupComplete&&!forced,forced_owned_cleanup:forced,cleanup,owned_processes:owned,elapsed_ms:Date.now()-started,plan_sha256:plan.plan_sha256,input_hashes:inputs,source_drift:drift,engine_operation:false};await writeFile(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,input_hashes:undefined,owned_processes:undefined,out}));process.exit(report.passed?0:1);
