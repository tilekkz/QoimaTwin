/** Actual desktop GPU magnifier checks. Root runs after the shared viewer build freezes. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {chromium} from '@playwright/test';

const powerShell=path.join(process.env.SystemRoot??'C:/Windows','System32/WindowsPowerShell/v1.0/powershell.exe');
const run = promisify(execFile), front = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const origin = (process.env.QOIMA_QA_ORIGIN ?? process.env.QOIMA_TEST_BASE_URL ?? 'http://127.0.0.1:4188').replace(/\/$/, '');
const dist = path.resolve(process.env.QOIMA_TEST_DIST_ROOT ?? path.join(front, 'dist'));
const stamp = new Date().toISOString().replaceAll(/[:.]/g, '-');
const outFlag = process.argv.indexOf('--out');
const out = path.resolve(outFlag >= 0 ? process.argv[outFlag + 1] : process.argv[2] ?? path.join(front, '../work/warehouse-magnifier-browser', stamp));
const within = path.relative(path.resolve(front, '../work'), out);
assert(within && !within.startsWith('..') && !path.isAbsolute(within), 'Evidence must stay in this repository/work');
await fs.mkdir(out, {recursive: true});
await assert.rejects(fs.access(path.join(out, 'checks.json')), e => e.code === 'ENOENT');
const sha = raw => createHash('sha256').update(raw).digest('hex');
const nativePairId = 'a'.repeat(64);
// Pure synthetic base_noop transport; the registered common/registry hashes are unchanged.
function nativeFixture(arm) {
  const identity = {run_id: 'b'.repeat(64), input_hash: 'c'.repeat(64), common_input_hash: '47ea8d54101f63b7dd2f958a41174c716607019a6f43a7379d2b80b3f42b3f99', registry_common_hash: '753452460289b494f9e59583091245a5f1c7d2e8a2bcd28c670e4a0f620c70ab'};
  const catalog = {...identity, schema_version: 'qoima-relocation-run-0.1.0', engine_version: 'qoima-manual-relocation-proposal-1', observed_until_tick: 100000000, status: 'complete', outcome_kind: 'base_noop'};
  const files = new Map([['catalog.json', catalog], ['snapshots/0000000000000000.json', {tick: 0, last_seq: -1, workers: [], belt: {carriers: []}}]]);
  const descriptors = [...files].map(([path, value]) => {const raw = Buffer.from(JSON.stringify(value)); return {path, bytes: raw.length, sha256: sha(raw)};});
  const manifest = {...identity, schema_version: catalog.schema_version, transport_version: 'qoima-relocation-run-bundle-0.1.0', engine_version: catalog.engine_version, inputs: {path: 'inputs.json', bytes: 10, sha256: identity.input_hash}, catalog: descriptors[0], event_chunks: [], snapshot_chunks: [{...descriptors[1], tick: 0, last_seq: -1}]};
  const manifestRaw = Buffer.from(JSON.stringify(manifest)); files.set('manifest.json', manifest); descriptors.push({path: 'manifest.json', bytes: manifestRaw.length, sha256: sha(manifestRaw)});
  return Buffer.from([{record_type: 'header', schema_version: 'qoima-saved-relocation-arm-ndjson-0.1.0', pair_id: nativePairId, arm, native_run_id: identity.run_id, ...identity, pair_input_hash: 'f'.repeat(64), origin: 'verified_saved_native_pair', transport_manifest: manifest, stream_descriptors: descriptors}, ...descriptors.map(d => ({record_type: 'file', ...d, body_base64: Buffer.from(JSON.stringify(files.get(d.path))).toString('base64')}))].map(r => JSON.stringify(r)).join('\n') + '\n');
}
const nativeFixtures = {baseline: nativeFixture('baseline'), candidate: nativeFixture('candidate')};
const sourceFiles = ['src/ui/warehouseMagnifier.ts', 'src/adaptive-v3/warehouseScene.ts', 'src/adaptive-v3/twin/twinPage.ts', 'src/adaptive-v3/twin/twinRender.ts', 'src/adaptive-v3/twin/twin.css', 'src/adaptive-v3/scenarioPage.ts', 'src/adaptive-v3/warehousePage.ts', 'src/adaptive-v3/heavyInboundPage.ts', 'src/native-v3/page.ts', 'tools/check-warehouse-magnifier-browser-v3.mjs'];
const pins = Object.fromEntries(await Promise.all(sourceFiles.map(async f => [f, sha(await fs.readFile(path.join(front, f)))])));
const cases = [], screenshots = [], errors = [], consoleErrors = [], warnings = [], failedRequests = [], httpErrors = [], served = [], assetTasks = [];
let browserPID, browser, context, page, fatal, gpu, stage = 'startup', owned = [], cleanup = false, forcedCleanup = false;
const bounded = async (promise, ms) => {let timer; try {return await Promise.race([promise, new Promise((_, reject) => {timer = setTimeout(() => reject(Error('Timeout ' + ms + 'ms')), ms);})]);} finally {clearTimeout(timer);}};
async function check(name, fn) {
  if(process.argv.includes('--performance-only')&&name!=='optical-frame-time-top-and-perspective')return;
  stage = name;
  try {const observations = await bounded(fn(), 90000); cases.push({name, passed: true, observations});}
  catch (error) {cases.push({name, passed: false, error: String(error.stack ?? error)}); if (page) await page.screenshot({path: path.join(out, name + '-FAIL.png'), timeout: 10000}).catch(() => {});}
  await fs.writeFile(path.join(out, 'progress.json'), JSON.stringify({stage, cases}, null, 2));
  console.log(JSON.stringify(cases.at(-1)));
}
async function attest() {
  // CDP supplies only this owned browser's processes; WMI is unavailable in the sandbox.
  const cdp=await browser.newBrowserCDPSession();let info;try{info=await cdp.send('SystemInfo.getProcessInfo');}finally{await cdp.detach();}
  const root=info.processInfo.find(p=>p.type==='browser');assert(root,'Owned browser process is present');browserPID??=root.id;assert.equal(root.id,browserPID,'CDP stays bound to our launched browser');
  const ids=[...new Set(info.processInfo.map(p=>p.id))];
  const result=await run(powerShell,['-NoProfile','-NonInteractive','-Command',"Get-Process -Id "+ids.join(',')+" -ErrorAction SilentlyContinue | Select-Object @{Name='ProcessId';Expression={$_.Id}},@{Name='CreationDate';Expression={$_.StartTime.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress"],{windowsHide:true,timeout:15000});
  const saved=new Map(owned.map(r=>[r.ProcessId,r]));for(const row of [].concat(JSON.parse(result.stdout)))saved.set(row.ProcessId,row);
  owned=[...saved.values()];assert(owned.length);await fs.writeFile(path.join(out,'owned-processes.json'),JSON.stringify(owned,null,2));
}
const viewers = {
  twin: {url: 'twin-v3.html', api: '__QOIMA_TWIN_V3__', canvas: '#tw-viewport > canvas'},
  warehouse: {url: 'warehouse-v3.html', api: '__QOIMA_WAREHOUSE_V3__', canvas: '#warehouse-viewport > canvas'},
  N3: {url: 'scenario-v3.html?scenario=N3', api: '__QOIMA_SCENARIO_V3__', canvas: '#sc-viewport > canvas'},
  N4: {url: 'scenario-v3.html?scenario=N4', api: '__QOIMA_SCENARIO_V3__', canvas: '#sc-viewport > canvas'},
  heavy: {url: 'heavy-inbound-v3.html', api: '__QOIMA_HEAVY_INBOUND_V3__', canvas: '#hi-viewport > canvas'},
  native: {url: 'native-pair-v3.html', api: '__QOIMA_NATIVE_PAIR__', canvas: '#native-viewport > canvas'},
};
async function snapshot(kind) {return page.evaluate(key => window[key]?.snapshot(), viewers[kind].api);}
async function open(kind) {
  await page.goto(origin + '/' + viewers[kind].url, {waitUntil: 'commit', timeout: 60000});
  await page.waitForFunction(api => ['ready', 'error'].includes(window[api]?.snapshot().phase), viewers[kind].api, {timeout: 65000});
  const s = await snapshot(kind); assert(s.phase === 'ready', 'Viewer refused: ' + JSON.stringify({phase: s?.phase, kind}));
  await page.locator(viewers[kind].canvas).scrollIntoViewIfNeeded();
  assert.equal(await page.locator(viewers[kind].canvas).count(), 1);
  assert.equal(await page.locator('.warehouse-magnifier-toggle').count(), 1, 'One source scene owns one toggle');
  assert.equal(await page.locator('.warehouse-magnifier-lens').count(), 1, 'One body overlay only');
  assert.equal(await page.locator('.warehouse-magnifier-lens canvas').count(), 0, 'Lens canvas remains lazy while disabled');
  assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-label'), 'Лупа');
  assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'false');
  return s;
}
async function pause(kind) {await page.evaluate(api => window[api].setPlaying?.(false), viewers[kind].api);}
async function lens() {return page.evaluate(() => {
  const element = document.querySelector('.warehouse-magnifier-lens'), r = element?.getBoundingClientRect();
  return {visible: !!element && !element.hidden && !!r?.width, kind: element?.dataset.kind, zoom: Number(element?.dataset.zoom), draws: Number(element?.dataset.draws ?? 0), captures: Number(element?.dataset.captures ?? 0), target_pixels: Number(element?.dataset.pixels ?? 0), caption: element?.dataset.caption, point: {x:Number(element?.dataset.pointX),y:Number(element?.dataset.pointY)}, canvas_count: element?.querySelectorAll('canvas').length, body_overlay: element?.parentElement === document.body, pointer_events: element ? getComputedStyle(element).pointerEvents : null, rect: r ? {left:r.left,top:r.top,right:r.right,bottom:r.bottom} : null, probe: window.__MAGNIFIER_PROBE__?.snapshot()};
});}
// Inspect real compositor screenshots, rather than trusting product counters or a 2D fallback.
async function pixelProof(state, pointer) {
 const png = await page.screenshot();
 return page.evaluate(async ({base64,state,pointer}) => {
  const bitmap = await createImageBitmap(await (await fetch('data:image/png;base64,'+base64)).blob());
  const c=document.createElement('canvas');c.width=bitmap.width;c.height=bitmap.height;const g=c.getContext('2d');g.drawImage(bitmap,0,0);bitmap.close();
  const crop=(x,y,size)=>{const out=document.createElement('canvas');out.width=out.height=224;const ctx=out.getContext('2d');ctx.imageSmoothingQuality='high';ctx.drawImage(c,x,y,size,size,0,0,224,224);return ctx.getImageData(0,0,224,224).data;};
  const real=crop(state.rect.left,state.rect.top,224), patch=pointer?crop(pointer.x-112/state.zoom,pointer.y-112/state.zoom,224/state.zoom):null;
  const colors=new Set();let edge=0,oldEdge=0,difference=0,n=0,strong=0,oldStrong=0;
  const luma=(p,i)=>.2126*p[i]+.7152*p[i+1]+.0722*p[i+2];
  // Stay inside the circle, above the caption and away from the crosshair/ring.
  for(let y=28;y<152;y++)for(let x=28;x<196;x++){
   if(Math.hypot(x-112,y-112)>83||Math.hypot(x-112,y-112)<12)continue;
   const i=4*(y*224+x),e=Math.abs(luma(real,i)-luma(real,i+4));edge+=e;strong+=e>18?1:0;colors.add(real[i]+','+real[i+1]+','+real[i+2]);
   if(patch){const e=Math.abs(luma(patch,i)-luma(patch,i+4));oldEdge+=e;oldStrong+=e>18?1:0;difference+=(Math.abs(real[i]-patch[i])+Math.abs(real[i+1]-patch[i+1])+Math.abs(real[i+2]-patch[i+2]))/3;}n++;
  }
  return {colors:colors.size,edge:edge/n,screen_patch_edge:oldEdge/n,strong_edges:strong,screen_patch_strong_edges:oldStrong,mean_difference:difference/n};
 },{base64:png.toString('base64'),state,pointer});
}
async function lensInteriorHash(){
 const state=await lens(),png=await page.screenshot({clip:{x:state.rect.left+35,y:state.rect.top+45,width:154,height:125}});
 return page.evaluate(async base64=>{const bitmap=await createImageBitmap(await(await fetch('data:image/png;base64,'+base64)).blob()),c=document.createElement('canvas');c.width=154;c.height=125;const g=c.getContext('2d');g.drawImage(bitmap,0,0);bitmap.close();const data=g.getImageData(0,0,154,125).data;for(let y=0;y<125;y++)for(let x=0;x<154;x++)if(Math.hypot(x+35-112,y+45-112)<13)data.fill(0,(y*154+x)*4,(y*154+x)*4+4);const hash=await crypto.subtle.digest('SHA-256',data);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('');},png.toString('base64'));
}
async function waitLens() {await page.waitForFunction(() => {const l = document.querySelector('.warehouse-magnifier-lens'); return l && !l.hidden && Number(l.dataset.draws) > 0;}, null, {timeout: 10000}); return lens();}
async function point(kind, fx = .25, fy = .5) {
  const r = await page.locator(viewers[kind].canvas).boundingBox(); assert(r?.width && r?.height);
  const p = {x: r.x + r.width * fx, y: r.y + r.height * fy}; await page.mouse.move(p.x, p.y); return {...p, rect: r};
}
async function enable(kind) {await page.locator('.warehouse-magnifier-toggle').focus(); await page.keyboard.press('Space'); assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'true'); await point(kind,kind==='twin'?.4:.5,kind==='twin'?.36:.5); const s = await waitLens(); assert.equal(s.body_overlay, true); assert.equal(s.pointer_events, 'none'); assert(s.captures > 0 && s.target_pixels >= 224); assert.equal(s.kind,'optical-3d'); assert.equal(s.canvas_count,0); assert.equal(s.probe.copies_from_WebGL_canvas,0); const proof=await pixelProof(s); assert(proof.colors>=1&&s.probe.gl_draw_calls>0,'Optical render has visible pixels and actual GL draws'); assert.equal(await page.locator(viewers[kind].canvas).evaluate(c => c.classList.contains('warehouse-magnifier-source-active')), true); return s;}
async function crop(kind, fx, fy = .5, syntheticBoundary = false) {
  const before = (await lens()).draws, p = await point(kind, fx, fy);
  if (syntheticBoundary) await page.locator(viewers[kind].canvas).evaluate((canvas, p) => canvas.dispatchEvent(new PointerEvent('pointermove', {clientX: p.x, clientY: p.y, pointerType: 'mouse', bubbles: true})), p);
  await page.waitForFunction(n => Number(document.querySelector('.warehouse-magnifier-lens')?.dataset.draws) > n, before);
  const s=await lens();
  assert(Math.abs(s.point.x-fx*p.rect.width)<2,'Lens camera centres on the actual horizontal pointer');
  assert(Math.abs(s.point.y-fy*p.rect.height)<2,'Lens camera centres on the actual vertical pointer');
  const proof=await pixelProof(s,p);
  assert.equal(s.probe.copies_from_WebGL_canvas,0,'No full-canvas copies');
  s.colors=proof.colors;s.proof=proof;
  return {pointer: p, lens: s, synthetic_boundary_event: syntheticBoundary};
}
async function settlePausedLens() {
  for (let i = 0; i < 16; i++) {const a = await lens(); await page.waitForTimeout(200); const b = await lens(); if (a.captures === b.captures && a.probe.gl_draw_calls === b.probe.gl_draw_calls && b.probe.pending_raf === 0) return b;}
  throw Error('Paused viewer did not settle to an idle composed frame');
}
async function capture(name) {const file = path.join(out, name + '.png'); await page.screenshot({path: file, timeout: 20000}); screenshots.push({file, sha256: sha(await fs.readFile(file)), stage});}
async function smoke(kind) {await open(kind); await pause(kind); const s = await enable(kind); assert(s.zoom >= 2 && s.zoom <= 10); await page.keyboard.press('Escape'); assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'false'); assert.equal((await lens()).visible, false); return {kind, magnifier: s};}

try {
  browser = await chromium.launch({channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--mute-audio', '--no-proxy-server']});
  await attest();
  context = await browser.newContext({viewport: {width: 1600, height: 1000}, deviceScaleFactor: 1, reducedMotion: 'no-preference'});
  await context.route('**/favicon.ico', r => r.fulfill({status: 204}));
  await context.addInitScript(() => {
    let mainColorClears=0, glDraws = 0, rafExecuted = 0, lastCrop = null, copiesFromWebGLCanvas = 0, lastFrame=0,frameCPU=0,lastFrameCPU=0,gpuEnabled=false,gpuGeneration=0,activeGPU=null,gpuPending=[],gpuTimes=[],mainClears=new Map();
    const timerExtensions=new WeakMap(),drawFramebuffers=new WeakMap();
    function pollGPU(){gpuPending=gpuPending.filter(row=>{const {gl,q,ext,generation}=row;if(!gl.getQueryParameter(q,gl.QUERY_RESULT_AVAILABLE))return true;if(generation===gpuGeneration&&!gl.getParameter(ext.GPU_DISJOINT_EXT))gpuTimes.push(gl.getQueryParameter(q,gl.QUERY_RESULT)/1e6);gl.deleteQuery(q);return false;});}
    const pending = new Set(), realRAF = requestAnimationFrame.bind(window), realCancel = cancelAnimationFrame.bind(window);
    window.requestAnimationFrame = callback => {let id; id = realRAF(t => {pending.delete(id); rafExecuted++; if(t!==lastFrame){lastFrame=t;lastFrameCPU=frameCPU;frameCPU=0;} const start=performance.now();try{callback(t);}finally{if(activeGPU){activeGPU.gl.endQuery(activeGPU.ext.TIME_ELAPSED_EXT);gpuPending.push(activeGPU);activeGPU=null;}frameCPU+=performance.now()-start;}}); pending.add(id); return id;};
    window.cancelAnimationFrame = id => {pending.delete(id); realCancel(id);};
    for (const Type of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) if (Type) for (const key of ['drawElements', 'drawArrays', 'drawElementsInstanced', 'drawArraysInstanced']) {const real = Type.prototype[key]; if (real) Type.prototype[key] = function(...args) {glDraws++; if(gpuEnabled&&!activeGPU&&this instanceof WebGL2RenderingContext){let ext=timerExtensions.get(this);if(!ext){ext=this.getExtension('EXT_disjoint_timer_query_webgl2');timerExtensions.set(this,ext);}if(ext){const q=this.createQuery();this.beginQuery(ext.TIME_ELAPSED_EXT,q);activeGPU={gl:this,q,ext,generation:gpuGeneration};}}return real.apply(this, args);};}
    const bind=WebGL2RenderingContext.prototype.bindFramebuffer,clear=WebGL2RenderingContext.prototype.clear;
    WebGL2RenderingContext.prototype.bindFramebuffer=function(target,framebuffer){if(target===this.FRAMEBUFFER||target===this.DRAW_FRAMEBUFFER)drawFramebuffers.set(this,framebuffer);return bind.call(this,target,framebuffer);};
    WebGL2RenderingContext.prototype.clear=function(mask){if(!drawFramebuffers.get(this)&&(mask&this.COLOR_BUFFER_BIT))mainColorClears++;if(gpuEnabled&&!drawFramebuffers.get(this)&&(mask&this.COLOR_BUFFER_BIT)){const frame=Number(document.timeline.currentTime);mainClears.set(frame,(mainClears.get(frame)??0)+1);}return clear.call(this,mask);};
    const draw = CanvasRenderingContext2D.prototype.drawImage;
    CanvasRenderingContext2D.prototype.drawImage = function(...args) {
      const result = draw.apply(this, args), source = args[0];
      if (source instanceof HTMLCanvasElement && source.classList.contains('warehouse-magnifier-source-active')) copiesFromWebGLCanvas++;
      if (this.canvas.closest('.warehouse-magnifier-lens') && args.length === 9) lastCrop = {sx: args[1], sy: args[2], sw: args[3], sh: args[4], source_width: source.width, source_height: source.height};
      return result;
    };
    window.__MAGNIFIER_PROBE__ = {startSample(){pollGPU();gpuGeneration++;gpuTimes=[];mainClears.clear();gpuEnabled=true;},finishSample(){gpuEnabled=false;pollGPU();return {gpu_ms:gpuTimes,max_main_draws_per_display_frame:Math.max(0,...mainClears.values())};},snapshot: () => ({main_color_clears:mainColorClears,gl_draw_calls: glDraws, raf_executed: rafExecuted, pending_raf: pending.size, copies_from_WebGL_canvas: copiesFromWebGLCanvas, last_crop: lastCrop,last_frame_cpu_ms:lastFrameCPU})};
  });
  page = await context.newPage(); page.setDefaultTimeout(10000);
  const cdp = await browser.newBrowserCDPSession(); const version = await cdp.send('Browser.getVersion'); await cdp.detach();
  const health = await fetch(origin + '/twin-v3.html', {signal: AbortSignal.timeout(10000)}); assert.equal(health.status, 200); await health.arrayBuffer();
  await fs.writeFile(path.join(out, 'startup-health.json'), JSON.stringify({version, origin, HTTP_status: health.status}, null, 2));
  page.on('pageerror', e => errors.push({stage, message: String(e)}));
  page.on('console', m => {const row = {stage, text: m.text(), location: m.location()}; if (m.type() === 'error') consoleErrors.push(row); else if (m.type() === 'warning') warnings.push(row);});
  page.on('requestfailed', r => failedRequests.push({stage, url: r.url(), error: r.failure()}));
  page.on('response', response => {
    const url = new URL(response.url()), responseStage = stage;
    if (response.status() >= 400) httpErrors.push({stage: responseStage, url: response.url(), status: response.status()});
    if (url.origin !== new URL(origin).origin || response.status() !== 200 || !/\.(?:html|js|css)$/.test(url.pathname)) return;
    assetTasks.push((async () => {const raw = await response.body(), relative = decodeURIComponent(url.pathname).replace(/^\//, ''), local = path.resolve(dist, relative), rel = path.relative(dist, local); assert(rel && !rel.startsWith('..') && !path.isAbsolute(rel)); assert.equal(sha(raw), sha(await fs.readFile(local)), 'Production dist mismatch ' + relative); served.push({path: relative, bytes: raw.length, sha256: sha(raw)});})().catch(e => errors.push({stage: 'dist-attestation', source_stage: responseStage, error: String(e)})));
  });
  await check('twin-keyboard-toggle-and-escape', async () => {
    await open('twin'); await pause('twin');
    await page.locator('.warehouse-magnifier-toggle').click(); assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'true'); await point('twin'); const mouse = await waitLens(); assert(mouse.draws > 0 && mouse.captures > 0); await page.keyboard.press('Escape'); assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'false'); assert.equal((await lens()).visible, false);
    const initial = await enable('twin'); assert.equal(initial.zoom, 4);
    const bounds = await page.locator(viewers.twin.canvas).boundingBox();
    if (bounds && 770 > bounds.x && 770 < bounds.x + bounds.width && 390 > bounds.y && 390 < bounds.y + bounds.height) {const before = (await lens()).draws; await page.mouse.move(770, 390); await page.waitForFunction(n => Number(document.querySelector('.warehouse-magnifier-lens').dataset.draws) > n, before); await capture('Twin-racks-magnified');}
    const gl = await page.locator(viewers.twin.canvas).evaluate(canvas => {const ctx = canvas.getContext('webgl2'), ext = ctx.getExtension('WEBGL_debug_renderer_info'); return {renderer: ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL), vendor: ctx.getParameter(ext.UNMASKED_VENDOR_WEBGL)};});
    assert(gl.renderer && !/SwiftShader|llvmpipe|softpipe|software rasterizer/i.test(gl.renderer)); assert(/Direct3D11|D3D11/i.test(gl.renderer)); gpu = gl;
    const p = (await lens()).point; await page.keyboard.press('ArrowRight'); await page.keyboard.press('+');
    await page.waitForFunction(() => Number(document.querySelector('.warehouse-magnifier-lens').dataset.zoom) === 4.5);
    assert((await lens()).point.x >= p.x); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'false'); assert.equal((await lens()).visible, false);
    return {trusted_mouse_click: mouse, initial, gpu: gl};
  });
  await check('twin-live-playback-capture', async () => {
    await enable('twin'); const before = await lens(), clock = (await snapshot('twin')).t;
    await page.evaluate(() => window.__QOIMA_TWIN_V3__.setPlaying(true));
    await page.waitForFunction(({at, captures}) => window.__QOIMA_TWIN_V3__.snapshot().t > at && Number(document.querySelector('.warehouse-magnifier-lens').dataset.captures) > captures, {at: clock, captures: before.captures});
    const after = await lens(), at = (await snapshot('twin')).t; await page.mouse.wheel(0, -400); const during = await snapshot('twin'); assert.equal(during.playing, true, 'Wheel does not pause playback'); assert(during.t >= at); await page.waitForFunction(at => window.__QOIMA_TWIN_V3__.snapshot().t > at, during.t); await pause('twin');
    assert(after.draws > before.draws && after.probe.gl_draw_calls > before.probe.gl_draw_calls && after.probe.copies_from_WebGL_canvas === 0); return {before, after, from_s: clock, to_s: at};
  });
  await check('twin-wheel-does-not-change-camera-or-clock', async () => {
    await pause('twin'); await page.waitForFunction(() => {const s = window.__QOIMA_TWIN_V3__.snapshot(); return !s.motion.camera_frame && !s.motion.pending_mode_change;}); await point('twin');
    const before = await snapshot('twin');
    for (let i = 0; i < 12; i++) await page.mouse.wheel(0, -400); assert.equal((await lens()).zoom, 10);
    for (let i = 0; i < 20; i++) await page.mouse.wheel(0, 400); assert.equal((await lens()).zoom, 2);
    const after = await snapshot('twin'); assert.equal(after.t, before.t); assert.deepEqual(after.motion.camera, before.motion.camera); assert.equal(after.playing, false);
    return {before_camera: before.motion.camera, after_camera: after.motion.camera, at_s: after.t, zoom: (await lens()).zoom};
  });
  await check('twin-complete-side-and-swipe-crops', async () => {
    const observations = [];
    for (let i = 0; i < 3; i++) await page.keyboard.press('+');
    for (const mode of ['side', 'swipe']) {
      await page.evaluate(mode => window.__QOIMA_TWIN_V3__.setMode(mode), mode);
      await page.waitForFunction(mode => {const s = window.__QOIMA_TWIN_V3__.snapshot(); return s.mode === mode && !s.motion.pending_mode_change && !s.motion.camera_frame;}, mode);
      const left = await crop('twin', mode==='side'?.4:.35,mode==='side'?.36:.54), right = await crop('twin', mode==='side'?.4:.75,mode==='side'?.76:.54); assert(left.lens.caption.startsWith('A ·'),'A selected by ray/pass'); assert(right.lens.caption.startsWith('B ·'),'B selected by ray/pass'); assert(left.lens.colors > 1 && right.lens.colors > 1, 'Both A and B contain actual rendered scene pixels');
      observations.push({mode, left, right}); await capture('twin-' + mode + '-magnified');
    }
    return observations;
  });
  await check('twin-paused-cache-edges-resize-and-leave', async () => {
    await pause('twin'); await point('twin', .25); await waitLens(); const before = await settlePausedLens(), staticRenders=(await snapshot('twin')).perf.totals.scene_renders;
    for (const fx of [.26, .29, .32, .35, .38]) await point('twin', fx);
    await page.waitForTimeout(200); const moved = await lens(); assert(moved.probe.gl_draw_calls > before.probe.gl_draw_calls,'Pointer movement re-renders real detail'); assert(moved.captures > before.captures); assert.equal(moved.probe.copies_from_WebGL_canvas,0); const cached=await snapshot('twin'); assert.equal(cached.perf.totals.scene_renders,staticRenders,'Lens movement preserves main static caches');
    await page.waitForTimeout(350); const idle = await lens(); assert.equal(idle.probe.raf_executed, moved.probe.raf_executed, 'No continuous idle RAF'); assert.equal(idle.probe.pending_raf, 0);
    const edges = [];
    for (const [x, y] of [[.001, .001], [.999, .001], [.001, .999], [.999, .999]]) {const row = await crop('twin', x, y, true); const r = row.lens.rect; assert(r.left >= 0 && r.top >= 0 && r.right <= 1600 && r.bottom <= 1000); edges.push(row);}
    await page.setViewportSize({width: 1440, height: 900}); await point('twin', .6); await waitLens(); const resized = await lens(); assert(resized.rect.right <= 1440 && resized.rect.bottom <= 900);
    await page.locator('.warehouse-magnifier-toggle').hover(); await page.waitForFunction(() => document.querySelector('.warehouse-magnifier-lens').hidden); assert.equal((await lens()).visible, false);
    await page.setViewportSize({width: 1600, height: 1000}); return {before, moved, idle, edges, resized};
  });
  await check('twin-context-loss-reload-cleanup', async () => {
    await point('twin'); await waitLens();
    await page.locator(viewers.twin.canvas).evaluate(canvas => {const ext = canvas.getContext('webgl2').getExtension('WEBGL_lose_context'); if (!ext) throw Error('Actual context-loss extension unavailable'); ext.loseContext();});
    await page.waitForFunction(() => window.__QOIMA_TWIN_V3__.snapshot().phase === 'error');
    assert.equal(await page.locator('.warehouse-magnifier-lens').count(), 0, 'Disposed overlay removed before retry'); assert.equal(await page.locator('.warehouse-magnifier-toggle').count(), 0);
    await open('twin'); assert.equal(await page.locator('.warehouse-magnifier-toggle').count(), 1); assert.equal(await page.locator('.warehouse-magnifier-lens').count(), 1); return {actual_context_loss: true, singleton_after_reload: true};
  });
  await check('warehouse-v3-magnifier-smoke', () => smoke('warehouse'));
  await check('scenario-N3-and-N4-magnifier-smoke', async () => {const rows = []; for (const id of ['N3', 'N4']) {await open(id); await pause(id); await page.evaluate(() => window.__QOIMA_SCENARIO_V3__.seek(300)); const s = await enable(id);if(id==='N3'){const a=await lens();await page.evaluate(()=>{window.__QOIMA_SCENARIO_V3__.seek(301);window.__QOIMA_SCENARIO_V3__.seek(300);});await page.waitForTimeout(150);const b=await lens(),clears=b.probe.main_color_clears-a.probe.main_color_clears;assert(clears>0,'Repeated scene updates render the source');assert(b.draws-a.draws>=clears,'Every completed source frame restores the optical composite');s.repeated_scene_frames={clears,lens_draws:b.draws-a.draws};}const before = await snapshot(id); await page.mouse.wheel(0, -400); const after = await snapshot(id); assert.equal(after.clock.at_s, before.clock.at_s); assert.equal(after.scenario_id, id); rows.push({id, clock_s: after.clock.at_s, lens: s}); if (id === 'N3') await capture('scenario-N3-magnified'); await page.keyboard.press('Escape');} return rows;});
  await check('heavy-inbound-magnifier-smoke', () => smoke('heavy'));
  await check('NativePair-synthetic-warehouse-live-magnifier', async () => {
    await page.goto(origin + '/native-pair-v3.html', {waitUntil: 'commit', timeout: 60000});
    await page.waitForFunction(() => !!window.__QOIMA_NATIVE_PAIR__);
    await page.locator('#native-source').selectOption('files'); await page.locator('#native-pair').fill(nativePairId);
    for (const arm of ['baseline', 'candidate']) await page.locator('#native-' + arm + '-file').setInputFiles({name: arm + '-synthetic.ndjson', mimeType: 'application/x-ndjson', buffer: nativeFixtures[arm]});
    await page.locator('#native-load').click();
    await page.waitForFunction(() => ['ready', 'error'].includes(window.__QOIMA_NATIVE_PAIR__.snapshot().phase), null, {timeout: 65000});
    const initial = await snapshot('native'); assert.equal(initial.phase, 'ready', await page.locator('#native-status').textContent()); assert.equal(initial.tick, 0); assert.equal(initial.playing, false);
    await page.locator(viewers.native.canvas).scrollIntoViewIfNeeded(); assert.equal(await page.locator(viewers.native.canvas).count(), 1); assert.equal(await page.locator('.warehouse-magnifier-toggle').count(), 1); assert.equal(await page.locator('.warehouse-magnifier-lens').count(), 1); assert.equal(await page.locator('.warehouse-magnifier-lens canvas').count(), 0);
    const before = await enable('native'); await page.locator('#native-play').click(); await point('native');
    await page.waitForFunction(captures => window.__QOIMA_NATIVE_PAIR__.snapshot().tick > 0 && window.__QOIMA_NATIVE_PAIR__.snapshot().playing && Number(document.querySelector('.warehouse-magnifier-lens').dataset.captures) > captures, before.captures);
    const moving = await snapshot('native'), movingLens = await lens();
    await page.waitForFunction(({tick, captures}) => window.__QOIMA_NATIVE_PAIR__.snapshot().tick > tick && Number(document.querySelector('.warehouse-magnifier-lens').dataset.captures) > captures, {tick: moving.tick, captures: movingLens.captures});
    await page.mouse.wheel(0, -400); const afterWheel = await snapshot('native'); assert.equal(afterWheel.playing, true); assert.equal(afterWheel.rate, moving.rate); assert(afterWheel.tick >= moving.tick); assert((await lens()).zoom > before.zoom);
    await page.locator('#native-play').click(); assert.equal((await snapshot('native')).playing, false); await page.locator('#native-reset').click(); assert.equal((await snapshot('native')).tick, 0);
    await point('native'); await waitLens(); await capture('NativePair-synthetic-magnified'); await page.keyboard.press('Escape'); assert.equal((await lens()).visible, false);
    await page.evaluate(() => {window.__QOIMA_NATIVE_PAIR__.dispose(); window.__QOIMA_NATIVE_PAIR__.dispose();}); assert.equal(await page.locator('.warehouse-magnifier-toggle').count(), 0); assert.equal(await page.locator('.warehouse-magnifier-lens').count(), 0); assert.equal(await page.locator(viewers.native.canvas).count(), 0);
    return {synthetic_empty_base_noop: true, observed_until_tick: 100000000, initial_tick: initial.tick, moving_tick: moving.tick, tick_after_wheel: afterWheel.tick, magnifier_before: before, magnifier_moving: movingLens, double_dispose_cleanup: true, actual_backend_http: false};
  });
  await check('optical-overview-detail-and-layout-evidence',async()=>{
    await page.setViewportSize({width:1920,height:1080});await page.emulateMedia({reducedMotion:'reduce'});await open('twin');await pause('twin');await enable('twin');
    const p=await point('twin',770/1920,390/1080);await waitLens();await settlePausedLens();
    const a=await lens(),detail=await pixelProof(a,p);assert(a.caption.startsWith('A ·'));assert(detail.edge>detail.screen_patch_edge*1.4,'Native 3D edges exceed the upscaled screen patch');assert(detail.strong_edges>detail.screen_patch_strong_edges*1.4,'Real subpixel geometry is resolved');assert(detail.mean_difference>2,'Lens is not a copied screen patch');await capture('overview-A-racks-3D');
    // Match the original 8dfb20c screenshot at exactly (770,390), t=85 and 3×.
    await page.keyboard.press('-');await page.keyboard.press('-');await settlePausedLens();await capture('same-spot-new-3D-3x');await page.keyboard.press('+');await page.keyboard.press('+');
    const b=await crop('twin',620/1920,800/1080);assert(b.lens.caption.startsWith('B ·'));await capture('overview-B-rebuilt-racks-3D');
    await page.evaluate(()=>window.__QOIMA_TWIN_V3__.fly([72,1.5,78],291.2713211578926,[0,1,0]));await point('twin',.4,.37);await settlePausedLens();await capture('top-view-A-racks-3D');
    return {A:a.caption,B:b.lens.caption,detail};
  });
  await check('optical-live-packing-and-swipe-evidence',async()=>{
    await page.emulateMedia({reducedMotion:'no-preference'});await page.evaluate(()=>window.__QOIMA_TWIN_V3__.fly([72,1.5,78],291.2713211578926,[0,.7546055221635046,.6561787149247867]));await pause('twin');await settlePausedLens();
    await point('twin',1180/1920,595/1080);await settlePausedLens();const before=await lens();assert.match(before.caption,/B · Упаковка/);
    await page.evaluate(()=>window.__QOIMA_TWIN_V3__.setPlaying(true));await page.waitForTimeout(500);const png1=await lensInteriorHash();let png2=png1;for(let i=0;i<12&&png2===png1;i++){await page.waitForTimeout(200);png2=await lensInteriorHash();}assert.notEqual(png1,png2,'Moving workers and belt update inside live composed frames');await capture('playing-busy-packing-line-3D');await pause('twin');
    await page.evaluate(()=>window.__QOIMA_TWIN_V3__.setMode('swipe'));await page.waitForFunction(()=>!window.__QOIMA_TWIN_V3__.snapshot().motion.camera_frame);const a=await crop('twin',.35,.54);assert(a.lens.caption.startsWith('A ·'));await capture('swipe-A-3D');const b=await crop('twin',.75,.54);assert(b.lens.caption.startsWith('B ·'));await capture('swipe-B-3D');return{packing:before.caption,lens_interior_hashes:[png1,png2],A:a.lens.caption,B:b.lens.caption};
  });
  await check('optical-reduced-motion-touch-DPR-and-warehouse-evidence',async()=>{
    await page.emulateMedia({reducedMotion:'reduce'});await point('twin',.4,.5);await settlePausedLens();const before=await lens();
    await page.locator(viewers.twin.canvas).evaluate(canvas=>canvas.dispatchEvent(new PointerEvent('pointermove',{pointerType:'touch',clientX:800,clientY:300,bubbles:true})));await page.waitForTimeout(150);assert.deepEqual((await lens()).point,before.point,'Touch leaves lens position unchanged');
    await page.keyboard.press('ArrowRight');await page.keyboard.press('+');await settlePausedLens();const moved=await lens();assert(moved.point.x>before.point.x);assert.equal(moved.zoom,before.zoom+.5);await page.keyboard.press('Escape');assert.equal((await lens()).visible,false);
    await page.emulateMedia({reducedMotion:'no-preference'});await page.emulateMedia({reducedMotion:'reduce'});await enable('twin');await settlePausedLens();const stable=await lens();await page.waitForTimeout(350);assert.equal((await lens()).draws,stable.draws,'Reduced lens has no animation loop');await page.keyboard.press('Escape');
    await open('warehouse');await pause('warehouse');const warehouse=await enable('warehouse');await point('warehouse',.62,.5);await waitLens();await capture('warehouse-v3-3D');await page.keyboard.press('Escape');
    // DPR 2 validates target allocation and compositor scale, without a second WebGL context.
    const retina=await browser.newContext({viewport:{width:1200,height:850},deviceScaleFactor:2,reducedMotion:'reduce'}),rp=await retina.newPage();
    try{await rp.goto(origin+'/warehouse-v3.html');await rp.waitForFunction(()=>window.__QOIMA_WAREHOUSE_V3__?.snapshot().phase==='ready',null,{timeout:65000});await rp.locator('.warehouse-magnifier-toggle').focus();await rp.keyboard.press('Space');await rp.waitForFunction(()=>Number(document.querySelector('.warehouse-magnifier-lens').dataset.draws)>0);assert.equal(await rp.locator('.warehouse-magnifier-lens').getAttribute('data-pixels'),'448');await rp.screenshot({path:path.join(out,'warehouse-DPR2-3D.png')});}finally{await retina.close();}
    return{touch_ignored:true,reduced_no_idle_loop:true,live_media_toggle:true,target_DPR2:448,warehouse};
  });
  await check('optical-frame-time-top-and-perspective',async()=>{
    await page.setViewportSize({width:1920,height:1080});await page.emulateMedia({reducedMotion:'no-preference'});await open('twin');await pause('twin');
    const rows=[];
    const sample=()=>page.evaluate(()=>new Promise(resolve=>{const intervals=[],rafWork=[],probe=window.__MAGNIFIER_PROBE__;probe.startSample();let previous=0,count=0;function frame(now){if(previous){intervals.push(now-previous);rafWork.push(probe.snapshot().last_frame_cpu_ms);}previous=now;if(++count<181)requestAnimationFrame(frame);else{const sorted=a=>a.slice().sort((a,b)=>a-b),pct=(a,p)=>sorted(a)[Math.floor((a.length-1)*p)];const gpu=probe.finishSample();resolve({samples:intervals.length,gpu_samples:gpu.gpu_ms.length,gpu_p50_ms:pct(gpu.gpu_ms,.5),gpu_p95_ms:pct(gpu.gpu_ms,.95),max_main_draws_per_display_frame:gpu.max_main_draws_per_display_frame,raf_p50_ms:pct(intervals,.5),raf_p95_ms:pct(intervals,.95),callback_cpu_p50_ms:pct(rafWork,.5),callback_cpu_p95_ms:pct(rafWork,.95)});}}requestAnimationFrame(frame);}));
    for(const [view,dir]of [['top',[0,1,0]],['perspective',[0,.7546055221635046,.6561787149247867]]]){
      await page.evaluate(dir=>window.__QOIMA_TWIN_V3__.fly([72,1.5,78],291.2713211578926,dir),dir);await page.waitForFunction(()=>!window.__QOIMA_TWIN_V3__.snapshot().motion.camera_frame);await page.evaluate(()=>window.__QOIMA_TWIN_V3__.setPlaying(true));
      const runs=[];for(const on of [false,true,false,true]){if(on){await enable('twin');await point('twin',.4,view==='top'?.4:.36);}else if((await lens()).visible)await page.keyboard.press('Escape');await page.waitForTimeout(650);runs.push({lens:on,...await sample()});}
      const avg=(flag,key)=>runs.filter(r=>r.lens===flag).reduce((n,r)=>n+r[key],0)/2;
      const row={view,runs,off:{p50:avg(false,'raf_p50_ms'),p95:avg(false,'raf_p95_ms')},on:{p50:avg(true,'raf_p50_ms'),p95:avg(true,'raf_p95_ms')},added_gpu_p50_ms:avg(true,'gpu_p50_ms')-avg(false,'gpu_p50_ms'),added_gpu_p95_ms:avg(true,'gpu_p95_ms')-avg(false,'gpu_p95_ms'),added_cpu_p50_ms:avg(true,'callback_cpu_p50_ms')-avg(false,'callback_cpu_p50_ms'),added_cpu_p95_ms:avg(true,'callback_cpu_p95_ms')-avg(false,'callback_cpu_p95_ms')};
      rows.push(row);await pause('twin');await page.keyboard.press('Escape');await fs.writeFile(path.join(out,'frame-times.json'),JSON.stringify({gpu,viewport:[1920,1080],rows},null,2));
    }
    await fs.writeFile(path.join(out,'frame-times.json'),JSON.stringify({gpu,viewport:[1920,1080],rows},null,2));for(const row of rows){const runs=row.runs;assert(runs.every(r=>r.gpu_samples>=120),'Real non-disjoint GPU timer samples');assert(runs.every(r=>r.max_main_draws_per_display_frame===1),'Main drawing stays coalesced to once per display frame');assert(row.added_gpu_p95_ms<=4.1,'Added GPU p95 <= ~4 ms: '+JSON.stringify(row));assert(row.added_cpu_p95_ms<=4.100001,'Added callback CPU p95 <= ~4 ms');}return rows;
  });
  await Promise.all(assetTasks);
} catch (error) {fatal = String(error.stack ?? error);}
finally {
  if (browser?.isConnected()) await attest().catch(error => {fatal ??= String(error);});
  for (const close of [async () => {if (browser?.isConnected()) {const c = await browser.newBrowserCDPSession(); await c.send('Browser.close');}}, () => context?.close(), () => browser?.close()]) try {await bounded(Promise.resolve().then(close), 4000);} catch {}
  try { if (browserPID && owned.length) {
    const saved = path.join(out, 'owned-processes.json').replaceAll("'", "''");
    const liveScript = "$rows=Get-Content -LiteralPath '" + saved + "' -Raw|ConvertFrom-Json;$live=@();foreach($saved in @($rows)){$p=Get-Process -Id $saved.ProcessId -ErrorAction SilentlyContinue;if($p -and -not $p.HasExited -and $p.StartTime.ToUniversalTime().Ticks -eq ([datetime]$saved.CreationDate).ToUniversalTime().Ticks){$live+=$saved.ProcessId}};ConvertTo-Json -InputObject @($live) -Compress";
    let live = JSON.parse((await run(powerShell, ['-NoProfile', '-NonInteractive', '-Command', liveScript], {windowsHide: true, timeout: 15000})).stdout || '[]');
    if (live.length) {
      forcedCleanup = true;
      await run(powerShell, ['-NoProfile', '-NonInteractive', '-Command', "$rows=Get-Content -LiteralPath '" + saved + "' -Raw|ConvertFrom-Json;foreach($saved in @($rows)){$p=Get-Process -Id $saved.ProcessId -ErrorAction SilentlyContinue;if($p -and -not $p.HasExited -and $p.StartTime.ToUniversalTime().Ticks -eq ([datetime]$saved.CreationDate).ToUniversalTime().Ticks){Stop-Process -Id $saved.ProcessId -Force -ErrorAction SilentlyContinue}};exit 0"], {windowsHide: true, timeout: 15000});
    }
    await new Promise(resolve => setTimeout(resolve, 1200));
    const fresh = await run(powerShell, ['-NoProfile', '-NonInteractive', '-Command', "$rows=Get-Content -LiteralPath '" + saved + "' -Raw|ConvertFrom-Json;$live=@();foreach($saved in @($rows)){$p=Get-Process -Id $saved.ProcessId -ErrorAction SilentlyContinue;if($p -and -not $p.HasExited -and $p.StartTime.ToUniversalTime().Ticks -eq ([datetime]$saved.CreationDate).ToUniversalTime().Ticks){$live+=$saved.ProcessId}};ConvertTo-Json -InputObject @($live) -Compress"], {windowsHide: true, timeout: 15000});
    live = JSON.parse(fresh.stdout || '[]'); cleanup = live.length === 0;
    await fs.writeFile(path.join(out, 'cleanup.json'), JSON.stringify({checked_utc: new Date().toISOString(), forced_owned_cleanup: forcedCleanup, fresh_GetProcess_live: live, cleanup}, null, 2));
  } else cleanup = !browser; } catch (error) {fatal ??= 'Cleanup verification: ' + String(error.stack ?? error); cleanup = false;}
}
const drift = [];
for (const [file, digest] of Object.entries(pins)) if (sha(await fs.readFile(path.join(front, file))) !== digest) drift.push(file);
const unexpectedRequests = failedRequests.filter(row => !(row.stage === 'twin-context-loss-reload-cleanup' && row.error?.errorText === 'net::ERR_ABORTED'));
const report = {passed: !fatal && cases.length === 14 && cases.every(c => c.passed) && !errors.length && !consoleErrors.length && !httpErrors.length && !unexpectedRequests.length && !drift.length && cleanup, viewer_scope: 'V3_ONLY', cases, fatal, gpu, screenshots, pageErrors: errors, consoleErrors, warnings, httpErrors, failedRequests, unexpected_request_failures: unexpectedRequests, source_hashes: pins, source_drift_during_run: drift, production_assets: served, cleanup, forced_owned_cleanup: forcedCleanup, synthetic_native_fixtures: {baseline_sha256: sha(nativeFixtures.baseline), candidate_sha256: sha(nativeFixtures.candidate), observed_until_tick: 100000000, recorded_workers: 0, recorded_carriers: 0, actual_backend_http: false}, scope: 'Actual desktop muted Chrome D3D11, one owned browser, warehouse viewers V3 only. Trusted mouse/keyboard/wheel, native-resolution optical 3D render, screenshot edge contrast and WebGL draw calls observed without product hooks. Twin preserved main static caches/no-idle-loop; Warehouse V3/Scenario N3+N4/Heavy and NativePair warehouse from explicitly synthetic empty base_noop files. Actual context loss and reload; no backend/native-pair capture or physical collision acceptance claimed. Only the explicit context-loss/reload stage permits ERR_ABORTED request cancellation.'};
await fs.writeFile(path.join(out, 'checks.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({passed: report.passed, cases: cases.length, failed: cases.filter(c => !c.passed).map(c => c.name), fatal, cleanup, forced_owned_cleanup: forcedCleanup, out}));
process.exit(report.passed ? 0 : 1);
