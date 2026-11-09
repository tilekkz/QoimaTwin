import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';

const args=process.argv.slice(2),urlIndex=args.indexOf('--url'),traceIndex=args.indexOf('--trace'),modelIndex=args.indexOf('--worker-model-path');
if(urlIndex>=0&&!args[urlIndex+1])throw Error('--url needs the built motion-v3.html URL');
if(traceIndex>=0&&!args[traceIndex+1])throw Error('--trace needs a repository-relative JSON or gzipped trace path');
if(modelIndex>=0&&!args[modelIndex+1])throw Error('--worker-model-path needs the accepted canonical worker model path');
const url=urlIndex>=0?args[urlIndex+1]:'http://127.0.0.1:4173/motion-v3.html';
const repo=fileURLToPath(new URL('../../',import.meta.url));
const folder=path.join(repo,'work/v3/motion-review-page/qa');await mkdir(folder,{recursive:true});
const tracePath=traceIndex>=0?args[traceIndex+1]:'assets/v3/iterations/worker-base/W05.3.7/accepted-native-and-live-browser/native-trace.json.gz';
assert(!path.isAbsolute(tracePath)&&path.resolve(repo,tracePath).startsWith(path.resolve(repo)+path.sep),'Trace must stay within this repository');
const traceBytes=await readFile(path.join(repo,tracePath)),trace=JSON.parse(tracePath.endsWith('.gz')?gunzipSync(traceBytes):traceBytes.toString('utf8'));
assert.equal(trace.passed_native_gate,true);assert(Array.isArray(trace.frames)&&trace.frames.length>0);
if(traceIndex<0)assert.equal(trace.frames.length,2135);
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio']});
const checks=[],captures=[],errors=[],consoleErrors=[],requests=[],referenceComparisons=[],limitations=[],anatomySamples=[],gripSupportSamples=[];
const equal=(name,actual,expected)=>{assert.deepEqual(actual,expected,name);checks.push(name);};
const check=(name,condition)=>{assert(condition,name);checks.push(name);};
function reference(name,actual,expected){
 let maximum=0;
 function compare(a,b){
  assert.equal(typeof a,typeof b,name);
  if(typeof a==='number'){assert(Number.isFinite(a)&&Number.isFinite(b),name);maximum=Math.max(maximum,Math.abs(a-b));assert(Math.abs(a-b)<=1e-9,name);}
  else if(a&&typeof a==='object'){assert.deepEqual(Object.keys(a),Object.keys(b),name);for(const key of Object.keys(a))compare(a[key],b[key]);}
  else assert.equal(a,b,name);
 }
 compare(actual,expected);referenceComparisons.push({name,maximum_component_delta:maximum,tolerance:1e-9});checks.push(name);
}
const nativeGuards=state=>state.live_contacts.length===2&&state.live_contacts.every(c=>c.gap_m<=2e-6)&&state.live_feet.length===2&&state.live_feet.every(f=>f.error_m<=2e-6&&f.native_bottom_y_m>=-2e-6&&(!f.stance||Math.abs(f.native_bottom_y_m)<=2e-6));
function checkAnatomy(name,state){
 anatomySamples.push({name,at_s:state.at_s,arms:state.arm_anatomy});
 if(state.carry_pose==='close_hold'){
  const rows=state.grip_support;
  gripSupportSamples.push({name,at_s:state.at_s,hands:rows});
  check(name+' actual bilateral palm support is available',rows?.length===2&&JSON.stringify(rows.map(row=>row.side).sort())==='["L","R"]');
  check(name+' lower and upper native palm faces cover at least 95 percent',rows.every(row=>[row.lower,row.upper].every(patch=>Number.isFinite(patch.coverage_ratio)&&patch.coverage_ratio>=.95&&Number.isFinite(patch.area_m2)&&patch.area_m2>0)));
  check(name+' native palm plane gaps stay within 2 micrometres',rows.every(row=>[row.lower,row.upper].every(patch=>Number.isFinite(patch.maximum_plane_gap_m)&&patch.maximum_plane_gap_m<=2e-6)));
  check(name+' lower palm centroids stay within 25 millimetres of HU depth centre',rows.every(row=>Number.isFinite(row.lower_centroid_z_offset_m)&&Math.abs(row.lower_centroid_z_offset_m)<=.025));
 }
 if(state.carry_pose!=='vertical_90'&&state.carry_pose!=='close_hold')return;
 check(name+' actual native arm anatomy is available',state.arm_anatomy?.length===2&&new Set(state.arm_anatomy.map(arm=>arm.side)).size===2&&state.arm_anatomy.every(arm=>Number.isFinite(arm.upper_tilt_from_down_deg)&&Number.isFinite(arm.elbow_inner_deg)));
 check(name+' upper arms remain within 5 degrees of vertical down',state.arm_anatomy.every(arm=>arm.upper_tilt_from_down_deg<=5+1e-8));
 check(name+' actual inner elbow angles remain 85 to 95 degrees',state.arm_anatomy.every(arm=>arm.elbow_inner_deg>=85-1e-8&&arm.elbow_inner_deg<=95+1e-8));
}
const ready=async page=>{
 await page.goto(url,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__QOIMA_MOTION_REVIEW_V3__||document.querySelector('#motion-review')?.dataset.state==='error',undefined,{timeout:60000});
 const failure=await page.locator('#motion-review').getAttribute('data-failure');
 assert.equal(await page.locator('#motion-review').getAttribute('data-state'),'ready',failure??'Review did not become ready');
};
const state=page=>page.evaluate(()=>window.__QOIMA_MOTION_REVIEW_V3__.snapshot());
const seek=(page,time)=>page.evaluate(t=>window.__QOIMA_MOTION_REVIEW_V3__.seek(t),time);
try{
 const page=await browser.newPage({viewport:{width:1680,height:990},deviceScaleFactor:1});
 page.on('pageerror',error=>errors.push(error.message));
 page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});
 page.on('request',request=>requests.push(request.url()));
 await ready(page);
 const initial=await state(page);
 const manifestResponse=await page.request.get(new URL('./data/v3/motion-review/manifest.json',url).href);
 assert(manifestResponse.ok(),'Accepted motion manifest must be readable');
 const manifest=await manifestResponse.json();
 const declaredModels=[modelIndex>=0?args[modelIndex+1]:undefined,trace.worker_model_path,manifest.worker_model_path].filter(value=>value!==undefined);
 const expectedModel=declaredModels[0]??(initial.carry_pose==='source'?'frontend/public/models/v3/worker-base.glb':initial.carry_pose==='close_hold'?'frontend/public/models/v3/worker-base-close-hold-jointfit.glb':'frontend/public/models/v3/worker-base-carry-natural.glb');
 assert(declaredModels.every(value=>value===expectedModel),'Accepted trace, model option and manifest representations must agree');
 const allowedModels=initial.carry_pose==='source'?['frontend/public/models/v3/worker-base.glb']:initial.carry_pose==='low_close'?['frontend/public/models/v3/worker-base-carry-natural.glb']:initial.carry_pose==='close_hold'?['frontend/public/models/v3/worker-base-close-hold-jointfit.glb']:['frontend/public/models/v3/worker-base-carry-natural.glb','frontend/public/models/v3/worker-base-vertical-carry.glb'];
 assert(allowedModels.includes(expectedModel),'Accepted representation must be canonical for this carry pose');
 equal('real original native controller',initial.render_mode,'live_original_controller');
 equal('grounded carry motion profile',initial.motion_profile.style,'grounded_carry');
 equal('native source profile remains 1.2 m/s',initial.motion_profile.source_profile_speed_m_s,1.2);
 equal('calibration carry cap is 0.7 m/s',initial.motion_profile.actual_calibration_speed_cap_m_s,.7);
 check('native duration is 28.47 seconds',Math.abs(initial.duration_s-28.47)<1e-9);
 check('review carry pose is explicit',['source','low_close','vertical_90','close_hold'].includes(initial.carry_pose));
 equal('review uses the accepted explicit model representation',initial.body_asset_path,expectedModel);
 checkAnatomy('initial',initial);
 equal('configured breathing starts in the allowed motion mode',initial.breathing.enabled,initial.configured_breathing);
 equal('original root remains owned through TRS',initial.root_matrix_auto_update,true);
 equal('one visible original worker',initial.scope.visible_actors,1);equal('one visible original HU',initial.scope.visible_HUs,1);
 equal('same source population',initial.scope.source_logical_population,{actors:24,HUs:530});
 equal('demo does not execute engine operations',initial.engine_operation,false);
 equal('demo does not join the warehouse runtime scene',initial.runtime_scene_joined,false);
 equal('desktop has three camera views',initial.visible_camera_count,3);
 const turns=trace.frames.filter(frame=>frame.gait_stage==='turn_step'),afterTurn=turns.at(-1).at_s;
 const walks=trace.frames.filter(frame=>frame.gait_stage==='walk_step'&&frame.at_s>afterTurn);
 const selected=[['start',trace.frames[0]],['turn',turns[Math.floor(turns.length/2)]],['walk',walks[Math.floor(walks.length/3)]],['end',trace.frames.at(-1)],['backwards',trace.frames[Math.floor(trace.frames.length/17)]]];
 for(const [name,frame]of selected){
  const current=await seek(page,frame.at_s);
  reference(name+' native actor matrix',current.body_world_matrix,frame.actor_root_world_matrix);
  reference(name+' original joint TRS',current.joints,frame.joints);
  reference(name+' four original cargo world matrices',current.cargo_world_matrices,frame.cargo_parts.map(part=>part.world_matrix));
  equal(name+' preserves worker instance',current.body_uuid,initial.body_uuid);
  equal(name+' preserves cargo instances',current.cargo_mesh_uuids,initial.cargo_mesh_uuids);
  equal(name+' uses one WebGL canvas',current.canvas_count,1);
  check(name+' native grip and sole guards',nativeGuards(current));
  checkAnatomy(name,current);
  const framing=await page.evaluate(()=>window.__QOIMA_MOTION_REVIEW_V3__.framing());
  check(name+' whole body and HU fit all desktop camera views',framing.length===3&&framing.every(f=>f.min_x>=-.99&&f.max_x<=.99&&f.min_y>=-.99&&f.max_y<=.99));
  if(name!=='backwards'){
   const file=path.join(folder,'desktop-'+name+'.png');await page.screenshot({path:file,fullPage:true});captures.push({name:'desktop-'+name,at_s:current.at_s,file});
  }
 }
 for(const time of [.7123456789,2.246813579,5.135792468,8.765432109,11.123456789,15.246813579,18.987654321,27.234567891]){
  const current=await seek(page,time);
  equal('arbitrary time '+time+' is calculated without frame snap',current.at_s,time);
  check('arbitrary time '+time+' retains native contacts and feet',nativeGuards(current));
  checkAnatomy('arbitrary time '+time,current);
 }
 await page.getByRole('button',{name:'В начало',exact:true}).click();equal('actual reset control returns to start',(await state(page)).at_s,0);
 await page.locator('#motion-timeline').fill('2.125');check('actual slider seeks native controller',Math.abs((await state(page)).at_s-2.125)<1e-12);
 await page.getByRole('button',{name:'Воспроизвести',exact:true}).click();
 await page.waitForFunction(()=>window.__QOIMA_MOTION_REVIEW_V3__.snapshot().at_s>2.6);
 check('actual play advances native movement',(await state(page)).playing);
 await page.getByRole('button',{name:'Пауза',exact:true}).click();
 const paused=await state(page);await page.waitForTimeout(160);equal('actual pause holds exact time',(await state(page)).at_s,paused.at_s);
 await page.getByRole('button',{name:'В начало',exact:true}).click();
 await page.getByRole('button',{name:'Половинная скорость',exact:true}).click();equal('actual half-speed control sets playback rate',(await state(page)).playback_rate,.5);
 const halfStart=await page.evaluate(()=>{const h=window.__QOIMA_MOTION_REVIEW_V3__;h.play();return performance.now();});
 await page.waitForTimeout(700);
 const halfEnd=await page.evaluate(()=>({state:window.__QOIMA_MOTION_REVIEW_V3__.pause(),now:performance.now()}));
 const wall=(halfEnd.now-halfStart)/1000;
 check('half speed changes playback clock only',halfEnd.state.at_s>0&&halfEnd.state.at_s<=wall*.75+.05);
 check('half-speed retains native clip duration',Math.abs(halfEnd.state.duration_s-28.47)<1e-9);
 await page.getByRole('button',{name:'Половинная скорость',exact:true}).click();equal('half-speed toggle restores normal rate',(await state(page)).playback_rate,1);
 await page.getByRole('button',{name:'Воспроизвести',exact:true}).click();await page.emulateMedia({reducedMotion:'reduce'});
 await page.waitForFunction(()=>!window.__QOIMA_MOTION_REVIEW_V3__.snapshot().playing);
 check('reduced motion stops active playback',!(await state(page)).playing);
 check('reduced motion disables automatic playback',await page.locator('#motion-play').isDisabled());
 check('reduced-motion message is visible',await page.locator('#motion-reduced').isVisible());
 await page.locator('#motion-timeline').fill('9.375');
 const reducedState=await state(page);
 equal('manual seek works under reduced motion',reducedState.at_s,9.375);
 check('manual reduced-motion pose retains native contacts and feet',nativeGuards(reducedState));
 checkAnatomy('reduced motion',reducedState);
 equal('reduced motion disables breathing',reducedState.breathing.enabled,false);
 equal('reduced motion leaves neutral breathing angle',reducedState.breathing.angle_rad,0);
 reference('reduced motion restores the original neutral torso',reducedState.joints.joint__torso.quaternion,trace.frames[0].joints.joint__torso.quaternion);
 await page.emulateMedia({reducedMotion:'no-preference'});
 const restored=await seek(page,9.375);
 equal('manual seek restores configured breathing after reduction',restored.breathing.enabled,initial.configured_breathing);
 check('restored motion mode retains native contacts and feet',nativeGuards(restored));
 checkAnatomy('restored motion',restored);
 check('restoring motion enables playback controls',await page.locator('#motion-play').isEnabled());
 check('restoring motion hides the reduced-motion notice',await page.locator('#motion-reduced').isHidden());
 await page.setViewportSize({width:360,height:800});
 await page.getByRole('tab',{name:'Сбоку',exact:true}).click();
 const mobile=await state(page);equal('mobile uses one full-width camera',mobile.visible_camera_count,1);equal('mobile side tab selects side camera',mobile.selected_camera,1);
 check('360px page has no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 check('360px controls stay inside viewport',await page.locator('.mr-actions').evaluate(node=>[...node.querySelectorAll('button')].every(button=>{const r=button.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.height>=44;})));
 for(const label of ['Спереди','Сбоку','Объём']){
  await page.getByRole('tab',{name:label,exact:true}).click();
  const framing=await page.evaluate(()=>window.__QOIMA_MOTION_REVIEW_V3__.framing());
  check('mobile '+label+' keeps whole body and HU visible',framing.length===1&&framing.every(f=>f.min_x>=-.99&&f.max_x<=.99&&f.min_y>=-.99&&f.max_y<=.99));
 }
 await page.getByRole('tab',{name:'Спереди',exact:true}).focus();await page.keyboard.press('ArrowRight');
 equal('camera tabs support keyboard selection',(await state(page)).selected_camera,1);
 equal('selected mobile tab is accessible',await page.getByRole('tab',{name:'Сбоку',exact:true}).getAttribute('aria-selected'),'true');
 const mobileShot=path.join(folder,'mobile-side.png');await page.screenshot({path:mobileShot,fullPage:true});captures.push({name:'mobile-side',at_s:(await state(page)).at_s,file:mobileShot});
 const runtime=await state(page);check('rendered frames retain native grip and ground thresholds',runtime.metrics.maximum_contact_gap_m<=2e-6&&runtime.metrics.maximum_sole_error_m<=2e-6&&runtime.metrics.frames>15);
 checkAnatomy('final runtime',runtime);
 check('portable page never requests repository filesystem URLs',requests.every(request=>!request.includes('/@fs/')&&!/[A-Za-z]:[\\/]/.test(new URL(request).pathname)));
 check('native reference trace stays in Node QA only',requests.every(request=>!request.includes('trace.json')));
 equal('no browser page errors',errors,[]);equal('no browser console errors',consoleErrors,[]);
 const destroyed=await page.evaluate(()=>window.__QOIMA_MOTION_REVIEW_V3__.destroy());
 equal('teardown disposes private worker after controller',destroyed.actor_disposed,true);equal('teardown disposes original binding',destroyed.binding_disposed,true);
 equal('teardown removes WebGL canvas',destroyed.canvas_count,0);equal('teardown clears cached source promises',destroyed.cached_source_count,0);equal('teardown stops playback',destroyed.playing,false);
 // A real damaged model response must show an error, with no partially ready controls or scene.
 const invalid=await browser.newPage({viewport:{width:390,height:844}}),invalidErrors=[];
 invalid.on('pageerror',error=>invalidErrors.push(error.message));
 await invalid.route(/\/models\/v3\/worker-base(?:-carry-natural|-vertical-carry|-close-hold-jointfit)?\.glb(?:\?.*)?$/,route=>route.fulfill({status:200,contentType:'application/octet-stream',body:'damaged asset for review failure check'}));
 await invalid.goto(url,{waitUntil:'domcontentloaded'});
 await invalid.waitForFunction(()=>document.querySelector('#motion-review')?.dataset.state==='error',undefined,{timeout:60000});
 check('invalid native asset shows visible failure',await invalid.locator('#motion-error').isVisible());
 check('invalid asset never publishes ready hook',await invalid.evaluate(()=>!window.__QOIMA_MOTION_REVIEW_V3__));
 check('invalid asset leaves controls disabled',await invalid.locator('.mr-controls').evaluate(node=>[...node.querySelectorAll('button,input')].every(control=>control.disabled)));
 equal('invalid asset leaves no partial canvas',await invalid.locator('canvas').count(),0);equal('invalid asset failure is handled without uncaught errors',invalidErrors,[]);
 const errorShot=path.join(folder,'invalid-asset.png');await invalid.screenshot({path:errorShot,fullPage:true});captures.push({name:'invalid-asset',file:errorShot});
 limitations.push('Visibility pause is implemented using document.hidden; background-tab visibility is not emulated by this headless browser check.');
 const report={schema_id:'qoima.motion-review.browser-checks.v1',executed:true,passed:true,url,browser:await browser.version(),render_mode:runtime.render_mode,motion_profile:runtime.motion_profile,carry_pose:runtime.carry_pose,body_asset_path:runtime.body_asset_path,configured_breathing:runtime.configured_breathing,native_trace:{repo_path:tracePath,sha256:createHash('sha256').update(traceBytes).digest('hex'),frame_count:trace.frames.length},
  scope:'Actual portable page and live original native calibration. Native-reference component comparison permits 1e-9 roundoff; live CPU native grip and foot guards separately retain 2e-6 metres. No micrometre GPU measurement, continuous foreign-clearance certificate, pickup execution or operational Scene admission.',
  reference_comparisons:referenceComparisons,live_frame_metrics:runtime.metrics,arm_anatomy:{measurement:'Actual shoulder, elbow and wrist world vectors; inner elbow angle, never joint Euler X',vertical_90_limits:{upper_tilt_from_down_deg_max:5,elbow_inner_deg_min:85,elbow_inner_deg_max:95},close_hold_limits:{upper_tilt_from_down_deg_max:5,elbow_inner_deg_min:85,elbow_inner_deg_max:95},samples:anatomySamples},grip_support:{measurement:'Native controller lower and upper palm face projection on the whole-HU side rectangles; actual cargo clearance is checked independently',limits:{minimum_coverage_ratio:.95,maximum_plane_gap_m:2e-6,maximum_abs_lower_centroid_z_offset_m:.025},samples:gripSupportSamples},checks,captures,limitations};
 await writeFile(path.join(folder,'checks.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({passed:true,checks:checks.length,captures:captures.length,report:path.join(folder,'checks.json')}));
}catch(error){
 await writeFile(path.join(folder,'failure.json'),JSON.stringify({passed:false,url,message:String(error?.stack??error),checks,errors,consoleErrors},null,2)+'\n');throw error;
}finally{await browser.close();}
