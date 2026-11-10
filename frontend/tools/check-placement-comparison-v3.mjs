import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import ts from 'typescript';
import {chromium} from '@playwright/test';
const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),out=path.join(repo,'work/v3/placement-functional-20261109',Date.now().toString());
await mkdir(out,{recursive:true});
const sha=b=>createHash('sha256').update(b).digest('hex'),inputs={};
for(const rel of ['frontend/src/adaptive-v3/twin/twinPlacementComparison.ts','frontend/src/adaptive-v3/twin/twinPlacementComparisonBinding.json','frontend/public/data/v3/placement-comparison.json','tools/visual/v3/build_placement_comparison_view.py'])inputs[rel]=sha(await readFile(path.join(repo,rel)));
const raw=await readFile(path.join(front,'public/data/v3/placement-comparison.json')),data=JSON.parse(raw),source=await readFile(path.join(front,'src/adaptive-v3/twin/twinPlacementComparison.ts'),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/import binding from ['"][^'"]+['"];?/,'const binding={};').replace(/import ['"][^'"]+\.css['"];?/g,'');
const {validatePlacementComparison}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
assert.equal(validatePlacementComparison(data),data);const rejected=[];
for(const [name,mutate]of [
 ['unpriced_relocation',d=>d.cases[1].relocation_proxy_cost_s=0],['fake_engine_run',d=>d.engine_operation=true],
 ['extra_workers',d=>d.headcount++],['lost_HU',d=>d.handling_units--],['unmodelled_queues_claim',d=>d.queues_modelled=true],
 ['period_presented_as_hours',d=>d.period_is_hours=true],['NaN_cost',d=>d.cases[1].adapted_proxy_cost_s=NaN],
 ['negative_relocation_cost',d=>d.cases[1].relocation_proxy_cost_s=-1],['fractional_transfer',d=>d.cases[1].transfer_count=.5],
 ['missing_pair_hash',d=>d.cases[1].comparison_inputs_sha256=''],['invented_default_gain',d=>d.cases[0].net_proxy_saving_s=10]
]){const bad=structuredClone(data);mutate(bad);assert.throws(()=>validatePlacementComparison(bad),undefined,name);rejected.push(name);}
const negative=structuredClone(data),c=negative.cases[1];c.adapted_proxy_cost_s=c.baseline_proxy_cost_s+100;c.relocation_proxy_cost_s=200;c.net_proxy_saving_s=-300;assert.equal(validatePlacementComparison(negative).cases[1].net_proxy_saving_s,-300);
let browser,server,context,page,failure;const cases=[],errors=[];const origin=process.env.QOIMA_QA_ORIGIN??'http://127.0.0.1:4224';assert.equal(new URL(origin).hostname,'127.0.0.1');
const ready=()=>page.waitForFunction(()=>window.__QOIMA_TWIN_V3__?.snapshot().phase==='ready',null,{timeout:30000});
try{
 server=await chromium.launchServer({channel:'chrome',headless:true,args:['--mute-audio']});browser=await chromium.connect(server.wsEndpoint());context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/twin-v3.html',{waitUntil:'domcontentloaded'});await ready();await page.waitForFunction(()=>document.querySelector('#tw-placement-cost')?.getAttribute('data-phase')==='ready');
 const before=await page.evaluate(()=>window.__QOIMA_TWIN_V3__.snapshot().scene);await page.locator('[data-open="diff"]').first().click();const panel=page.locator('#tw-placement-cost');await panel.scrollIntoViewIfNeeded();assert.equal(await panel.getAttribute('data-horizon'),'1');assert.equal(await panel.getAttribute('data-noop'),'true');assert((await panel.innerText()).includes('оставить груз на месте'));cases.push('default_one_period_noop_visible');
 for(const n of [2,4,8,1]){await panel.locator('button[data-period="'+n+'"]').click();assert.equal(await panel.getAttribute('data-horizon'),String(n));assert.equal(await panel.locator('button[aria-pressed="true"]').count(),1);}
 const after=await page.evaluate(()=>window.__QOIMA_TWIN_V3__.snapshot().scene);assert.equal(after.workers,24);assert.equal(after.stock_HUs,530);assert.deepEqual(after.stock_positions,before.stock_positions);assert.deepEqual(after.worker_ids,before.worker_ids);cases.push('all_horizons_reversible_preserve_cargo_and_staff');await page.screenshot({path:path.join(out,'placement-noop.png')});
 await page.route('**/data/v3/placement-comparison.json',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...data,headcount:25})}),{times:1});await page.reload({waitUntil:'domcontentloaded'});await ready();await page.waitForFunction(()=>document.querySelector('#tw-placement-cost')?.getAttribute('data-phase')==='error');await page.locator('[data-open="diff"]').first().click();await panel.scrollIntoViewIfNeeded();assert.equal(await panel.locator('dl div').count(),0);await panel.getByRole('button',{name:'Повторить загрузку'}).click();await page.waitForFunction(()=>document.querySelector('#tw-placement-cost')?.getAttribute('data-phase')==='ready');assert.equal(await panel.getAttribute('data-horizon'),'1');cases.push('changed_hash_refused_then_real_retry_recovers');
 assert.deepEqual(errors,[]);
}catch(e){failure=e.stack??String(e);}finally{await context?.close().catch(()=>{});await browser?.close().catch(()=>{});await server?.close().catch(()=>{});}
const drift=[];for(const [rel,pin]of Object.entries(inputs))if(sha(await readFile(path.join(repo,rel)))!==pin)drift.push(rel);
const report={passed:!failure&&drift.length===0,component_rejections:rejected,legitimate_negative_outcome_accepted:true,browser_cases:cases,page_errors:errors,failure,input_hashes:inputs,source_drift:drift,desktop_only:true,engine_operation:false,queues_modelled:false};await writeFile(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,input_hashes:undefined,out}));if(!report.passed)process.exitCode=1;
