import assert from 'node:assert/strict';
import {chromium} from '../../../frontend/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url)),trace=JSON.parse(await readFile(path.join(root,'trace.json'),'utf8'));
const folder=path.join(root,'qa');await mkdir(folder,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const failures=[],captures=[],checks=[],errors=[];
try{
 const page=await browser.newPage({viewport:{width:1680,height:990},deviceScaleFactor:1});
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:4193/',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__loadedWalkReplay,{timeout:30000});
 assert.equal(await page.locator('#error').textContent(),'');
 const initial=await page.evaluate(()=>window.__loadedWalkReplay.snapshot());
 const equal=(name,a,b)=>{assert.deepEqual(a,b,name);checks.push(name);};
 for(const [name,time]of [['start',0],['turn',7.568333333333335],['walk',10.044683098490498],['end',trace.duration_s],['backwards',.6097529420605104]]){
  const state=await page.evaluate(t=>window.__loadedWalkReplay.seek(t),time),frame=trace.frames[state.index];
  equal(name+' actor world matrix exactly replayed',state.body_world_matrix,frame.actor_root_world_matrix);
  equal(name+' original native joint TRS exactly replayed',state.joints,frame.joints);
  equal(name+' four original cargo part world matrices exactly replayed',state.cargo_world_matrices,frame.cargo_parts.map(p=>p.world_matrix));
  equal(name+' same worker instance',state.body_uuid,initial.body_uuid);equal(name+' same cargo instances',state.cargo_mesh_uuids,initial.cargo_mesh_uuids);equal(name+' one canvas',state.canvas_count,1);
  if(name!=='backwards'){const file=path.join(folder,name+'.png');await page.screenshot({path:file});captures.push({name,at_s:state.at_s,file});}
 }
 await page.getByRole('button',{name:'В начало',exact:true}).click();equal('actual start button restores first frame',(await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).at_s,0);
 await page.getByRole('button',{name:'Воспроизвести',exact:true}).click();await page.waitForFunction(()=>window.__loadedWalkReplay.snapshot().at_s>.15);assert((await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).playing);checks.push('actual play control advances native trace');
 await page.getByRole('button',{name:'Пауза',exact:true}).click();assert(!(await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).playing);checks.push('actual pause control stops trace');
 await page.emulateMedia({reducedMotion:'reduce'});await page.getByRole('button',{name:'Воспроизвести',exact:true}).click();assert(!(await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).playing);checks.push('reduced motion blocks automatic replay');
 equal('no browser page errors',errors,[]);
 const report={schema_id:'qoima.loaded-walk-replay.browser-review.v1',executed:true,passed:true,passed_native_gate:trace.passed_native_gate,scope:'Exact discrete native trace replay and controls only. Browser does not certify micrometre GPU contacts, continuous motion, source pickup or live Scene action.',browser:await browser.version(),checks,captures};
 await writeFile(path.join(folder,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,passed_native_gate:trace.passed_native_gate,checks:checks.length,captures:captures.length}));
}finally{await browser.close();}
