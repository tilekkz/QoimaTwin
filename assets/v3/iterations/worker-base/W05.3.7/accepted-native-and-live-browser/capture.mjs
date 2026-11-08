import assert from 'node:assert/strict';
import {chromium} from '../../../frontend/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url)),trace=JSON.parse(await readFile(path.join(root,'trace.json'),'utf8'));
const folder=path.join(root,'qa');await mkdir(folder,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const captures=[],checks=[],errors=[],referenceComparisons=[];
try{
 const page=await browser.newPage({viewport:{width:1680,height:990},deviceScaleFactor:1});
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:4193/',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__loadedWalkReplay,{timeout:30000});
 assert.equal(await page.locator('#error').textContent(),'');
 const initial=await page.evaluate(()=>window.__loadedWalkReplay.snapshot());
 const equal=(name,a,b)=>{assert.deepEqual(a,b,name);checks.push(name);};
 const reference=(name,a,b)=>{let maximum=0;function compare(x,y){assert.equal(typeof x,typeof y,name);if(typeof x==='number'){assert(Number.isFinite(x)&&Number.isFinite(y));maximum=Math.max(maximum,Math.abs(x-y));assert(Math.abs(x-y)<=1e-9,name);}else if(x&&typeof x==='object'){assert.deepEqual(Object.keys(x),Object.keys(y),name);for(const k of Object.keys(x))compare(x[k],y[k]);}else assert.equal(x,y,name);}compare(a,b);referenceComparisons.push({name,maximum_component_delta:maximum,tolerance:1e-9});checks.push(name);};
 equal('actual live native controller',initial.render_mode,'live_original_controller');
 const turn=trace.frames.filter(f=>f.gait_stage==='turn_step'),afterTurn=turn.at(-1).at_s,walk=trace.frames.filter(f=>f.gait_stage==='walk_step'&&f.at_s>afterTurn);
 const selected=[['start',trace.frames[0]],['turn',turn[Math.floor(turn.length/2)]],['walk',walk[Math.floor(walk.length/3)]],['end',trace.frames.at(-1)],['backwards',trace.frames[Math.floor(trace.frames.length/17)]]];
 for(const [name,frame]of selected){
  const state=await page.evaluate(i=>window.__loadedWalkReplay.frame(i),trace.frames.indexOf(frame));
  reference(name+' live actor matrix agrees with native reference',state.body_world_matrix,frame.actor_root_world_matrix);
  reference(name+' live original joint TRS agree with native reference',state.joints,frame.joints);
  reference(name+' live cargo matrices agree with native reference',state.cargo_world_matrices,frame.cargo_parts.map(p=>p.world_matrix));
  equal(name+' same worker instance',state.body_uuid,initial.body_uuid);equal(name+' same cargo instances',state.cargo_mesh_uuids,initial.cargo_mesh_uuids);equal(name+' one canvas',state.canvas_count,1);
  if(name!=='backwards'){const file=path.join(folder,name+'.png');await page.screenshot({path:file});captures.push({name,at_s:state.at_s,file});}
 }
 for(const time of [.7123456789,2.246813579,5.135792468,8.765432109,11.123456789,15.246813579,18.987654321]){
  const state=await page.evaluate(t=>window.__loadedWalkReplay.seek(t),time);
  equal('arbitrary seek '+time+' calculated exactly without frame snap',state.at_s,time);
  assert(state.live_contacts.every(c=>c.gap_m<=2e-6)&&state.live_feet.every(f=>f.error_m<=2e-6&&f.native_bottom_y_m>=-2e-6));checks.push('arbitrary seek '+time+' native grip and foot support valid');
 }
 await page.getByRole('button',{name:'В начало',exact:true}).click();equal('actual start button restores first frame',(await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).at_s,0);
 await page.getByRole('button',{name:'Воспроизвести',exact:true}).click();await page.waitForFunction(()=>window.__loadedWalkReplay.snapshot().at_s>1.1);assert((await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).playing);checks.push('actual play control advances live native movement through a step');
 await page.getByRole('button',{name:'Пауза',exact:true}).click();assert(!(await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).playing);checks.push('actual pause control stops trace');
 await page.emulateMedia({reducedMotion:'reduce'});await page.getByRole('button',{name:'Воспроизвести',exact:true}).click();assert(!(await page.evaluate(()=>window.__loadedWalkReplay.snapshot())).playing);checks.push('reduced motion blocks automatic replay');
 equal('no browser page errors',errors,[]);
 const runtime=await page.evaluate(()=>window.__loadedWalkReplay.snapshot());assert(runtime.metrics.frames>15);assert(runtime.metrics.maximum_contact_gap_m<=2e-6&&runtime.metrics.maximum_sole_error_m<=2e-6);checks.push('continuous controller applies native grip and ground guards on actual rendered frames');
 const report={schema_id:'qoima.loaded-walk-live.browser-review.v2',executed:true,passed:true,passed_native_gate:trace.passed_native_gate,render_mode:runtime.render_mode,motion_profile:runtime.motion_profile,scope:'Actual original native calibration controller at every rendered/arbitrary-time frame; numeric CPU-reference equivalence permits1e-9component roundoff. Live native grip/ground guards retain their separate unchanged2e-6metre threshold. No micrometre GPU, continuous foreign clearance, source pickup or operational Scene certificate.',browser:await browser.version(),reference_comparisons:referenceComparisons,live_frame_metrics:runtime.metrics,checks,captures};
 await writeFile(path.join(folder,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,passed_native_gate:trace.passed_native_gate,checks:checks.length,captures:captures.length}));
}finally{await browser.close();}
