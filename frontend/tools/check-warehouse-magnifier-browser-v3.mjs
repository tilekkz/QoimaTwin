/** Actual desktop GPU magnifier checks. Root runs after the shared viewer build freezes. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {chromium} from '@playwright/test';

const run = promisify(execFile), front = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const origin = (process.env.QOIMA_TEST_BASE_URL ?? 'http://127.0.0.1:4282').replace(/\/$/, '');
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
const sourceFiles = ['src/ui/warehouseMagnifier.ts', 'src/adaptive-v3/warehouseScene.ts', 'src/adaptive-v3/twin/twinPage.ts', 'src/adaptive-v3/twin/twinRender.ts', 'src/adaptive-v3/scenarioPage.ts', 'src/adaptive-v3/warehousePage.ts', 'src/adaptive-v3/heavyInboundPage.ts', 'src/native-v3/page.ts', 'tools/check-warehouse-magnifier-browser-v3.mjs'];
const pins = Object.fromEntries(await Promise.all(sourceFiles.map(async f => [f, sha(await fs.readFile(path.join(front, f)))])));
const cases = [], screenshots = [], errors = [], consoleErrors = [], warnings = [], failedRequests = [], httpErrors = [], served = [], assetTasks = [];
let server, browser, context, page, fatal, gpu, stage = 'startup', owned = [], cleanup = false, forcedCleanup = false;
const bounded = async (promise, ms) => {let timer; try {return await Promise.race([promise, new Promise((_, reject) => {timer = setTimeout(() => reject(Error('Timeout ' + ms + 'ms')), ms);})]);} finally {clearTimeout(timer);}};
async function check(name, fn) {
  stage = name;
  try {const observations = await bounded(fn(), 90000); cases.push({name, passed: true, observations});}
  catch (error) {cases.push({name, passed: false, error: String(error.stack ?? error)}); if (page) await page.screenshot({path: path.join(out, name + '-FAIL.png'), timeout: 10000}).catch(() => {});}
  await fs.writeFile(path.join(out, 'progress.json'), JSON.stringify({stage, cases}, null, 2));
  console.log(JSON.stringify(cases.at(-1)));
}
async function attest() {
  const result = await run('pwsh', ['-NoProfile', '-NonInteractive', '-Command', "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,@{Name='CreationDate';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}},CommandLine | ConvertTo-Json -Compress"], {windowsHide: true, timeout: 15000, maxBuffer: 8 * 1024 * 1024});
  const rows = JSON.parse(result.stdout), root = rows.find(r => r.ProcessId === server.process().pid);
  if (root) {assert.equal(root.ParentProcessId, process.pid); assert(root.CommandLine.includes('playwright_chromiumdev_profile-') && root.CommandLine.includes('--headless'));}
  const ids = new Set([server.process().pid]);
  for (let i = 0; i < 12; i++) for (const row of rows) if (ids.has(row.ParentProcessId)) ids.add(row.ProcessId);
  const saved = new Map(owned.map(r => [r.ProcessId, r]));
  for (const row of rows) if (ids.has(row.ProcessId)) saved.set(row.ProcessId, row);
  owned = [...saved.values()]; assert(owned.length);
  await fs.writeFile(path.join(out, 'owned-processes.json'), JSON.stringify(owned, null, 2));
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
  const element = document.querySelector('.warehouse-magnifier-lens'), canvas = element?.querySelector('canvas'), ctx = canvas?.getContext('2d');
  let colors = 0, opaque = 0;
  if (ctx && canvas.width && canvas.height) {const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data, set = new Set(); for (let y = 0; y < canvas.height; y += 12) for (let x = 0; x < canvas.width; x += 12) {const i = 4 * (y * canvas.width + x); if (pixels[i + 3]) opaque++; set.add(pixels[i] + ',' + pixels[i + 1] + ',' + pixels[i + 2]);} colors = set.size;}
  const r = element?.getBoundingClientRect();
  return {visible: !!element && !element.hidden && !!r?.width, zoom: Number(element?.dataset.zoom), draws: Number(element?.dataset.draws ?? 0), captures: Number(element?.dataset.captures ?? 0), canvas: canvas ? {width: canvas.width, height: canvas.height} : null, body_overlay: element?.parentElement === document.body, pointer_events: element ? getComputedStyle(element).pointerEvents : null, rect: r ? {left: r.left, top: r.top, right: r.right, bottom: r.bottom} : null, colors, opaque, probe: window.__MAGNIFIER_PROBE__?.snapshot()};
});}
async function waitLens() {await page.waitForFunction(() => {const l = document.querySelector('.warehouse-magnifier-lens'); return l && !l.hidden && Number(l.dataset.draws) > 0;}, null, {timeout: 10000}); return lens();}
async function point(kind, fx = .25, fy = .5) {
  const r = await page.locator(viewers[kind].canvas).boundingBox(); assert(r?.width && r?.height);
  const p = {x: r.x + r.width * fx, y: r.y + r.height * fy}; await page.mouse.move(p.x, p.y); return {...p, rect: r};
}
async function enable(kind) {await page.locator('.warehouse-magnifier-toggle').focus(); await page.keyboard.press('Space'); assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'true'); await point(kind); const s = await waitLens(); assert.equal(s.body_overlay, true); assert.equal(s.pointer_events, 'none'); assert(s.opaque > 0 && s.captures > 0); assert.equal(await page.locator(viewers[kind].canvas).evaluate(c => c.classList.contains('warehouse-magnifier-source-active')), true); return s;}
async function crop(kind, fx, fy = .5, syntheticBoundary = false) {
  const before = (await lens()).draws, p = await point(kind, fx, fy);
  if (syntheticBoundary) await page.locator(viewers[kind].canvas).evaluate((canvas, p) => canvas.dispatchEvent(new PointerEvent('pointermove', {clientX: p.x, clientY: p.y, pointerType: 'mouse', bubbles: true})), p);
  await page.waitForFunction(n => Number(document.querySelector('.warehouse-magnifier-lens')?.dataset.draws) > n, before);
  const s = await lens(), d = s.probe.last_crop; assert(d, 'Observed real lens drawImage crop');
  assert(Math.abs(d.sx + d.sw / 2 - fx * d.source_width) < 2, 'Horizontal crop inspects the actual pointer pixel');
  assert(Math.abs(d.sy + d.sh / 2 - fy * d.source_height) < 2, 'Vertical crop inspects the actual pointer pixel');
  return {pointer: p, lens: s, synthetic_boundary_event: syntheticBoundary};
}
async function settlePausedLens() {
  for (let i = 0; i < 16; i++) {const a = await lens(); await page.waitForTimeout(200); const b = await lens(); if (a.captures === b.captures && a.probe.gl_draw_calls === b.probe.gl_draw_calls && b.probe.pending_raf === 0) return b;}
  throw Error('Paused viewer did not settle to an idle composed frame');
}
async function capture(name) {const file = path.join(out, name + '.png'); await page.screenshot({path: file, timeout: 20000}); screenshots.push({file, sha256: sha(await fs.readFile(file)), stage});}
async function smoke(kind) {await open(kind); await pause(kind); const s = await enable(kind); assert(s.zoom >= 1.5 && s.zoom <= 6); await page.keyboard.press('Escape'); assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'false'); assert.equal((await lens()).visible, false); return {kind, magnifier: s};}

try {
  server = await chromium.launchServer({channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--mute-audio', '--no-proxy-server']});
  await attest(); browser = await chromium.connect(server.wsEndpoint());
  context = await browser.newContext({viewport: {width: 1600, height: 1000}, deviceScaleFactor: 1, reducedMotion: 'no-preference'});
  await context.route('**/favicon.ico', r => r.fulfill({status: 204}));
  await context.addInitScript(() => {
    let glDraws = 0, rafExecuted = 0, lastCrop = null, copiesFromWebGLCanvas = 0;
    const pending = new Set(), realRAF = requestAnimationFrame.bind(window), realCancel = cancelAnimationFrame.bind(window);
    window.requestAnimationFrame = callback => {let id; id = realRAF(t => {pending.delete(id); rafExecuted++; callback(t);}); pending.add(id); return id;};
    window.cancelAnimationFrame = id => {pending.delete(id); realCancel(id);};
    for (const Type of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) if (Type) for (const key of ['drawElements', 'drawArrays', 'drawElementsInstanced', 'drawArraysInstanced']) {const real = Type.prototype[key]; if (real) Type.prototype[key] = function(...args) {glDraws++; return real.apply(this, args);};}
    const draw = CanvasRenderingContext2D.prototype.drawImage;
    CanvasRenderingContext2D.prototype.drawImage = function(...args) {
      const result = draw.apply(this, args), source = args[0];
      if (source instanceof HTMLCanvasElement && source.classList.contains('warehouse-magnifier-source-active')) copiesFromWebGLCanvas++;
      if (this.canvas.closest('.warehouse-magnifier-lens') && args.length === 9) lastCrop = {sx: args[1], sy: args[2], sw: args[3], sh: args[4], source_width: source.width, source_height: source.height};
      return result;
    };
    window.__MAGNIFIER_PROBE__ = {snapshot: () => ({gl_draw_calls: glDraws, raf_executed: rafExecuted, pending_raf: pending.size, copies_from_WebGL_canvas: copiesFromWebGLCanvas, last_crop: lastCrop})};
  });
  page = await context.newPage(); page.setDefaultTimeout(10000);
  await page.waitForFunction(() => document.readyState === 'complete');
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
    const initial = await enable('twin'); assert.equal(initial.zoom, 3);
    const bounds = await page.locator(viewers.twin.canvas).boundingBox();
    if (bounds && 770 > bounds.x && 770 < bounds.x + bounds.width && 390 > bounds.y && 390 < bounds.y + bounds.height) {const before = (await lens()).draws; await page.mouse.move(770, 390); await page.waitForFunction(n => Number(document.querySelector('.warehouse-magnifier-lens').dataset.draws) > n, before); await capture('Twin-racks-magnified');}
    const gl = await page.locator(viewers.twin.canvas).evaluate(canvas => {const ctx = canvas.getContext('webgl2'), ext = ctx.getExtension('WEBGL_debug_renderer_info'); return {renderer: ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL), vendor: ctx.getParameter(ext.UNMASKED_VENDOR_WEBGL)};});
    assert(gl.renderer && !/SwiftShader|llvmpipe|softpipe|software rasterizer/i.test(gl.renderer)); assert(/Direct3D11|D3D11/i.test(gl.renderer)); gpu = gl;
    const p = (await lens()).probe.last_crop; await page.keyboard.press('ArrowRight'); await page.keyboard.press('+');
    await page.waitForFunction(() => Number(document.querySelector('.warehouse-magnifier-lens').dataset.zoom) === 3.5);
    assert((await lens()).probe.last_crop.sx >= p.sx); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.warehouse-magnifier-toggle').getAttribute('aria-pressed'), 'false'); assert.equal((await lens()).visible, false);
    return {trusted_mouse_click: mouse, initial, gpu: gl};
  });
  await check('twin-live-playback-capture', async () => {
    await enable('twin'); const before = await lens(), clock = (await snapshot('twin')).t;
    await page.evaluate(() => window.__QOIMA_TWIN_V3__.setPlaying(true));
    await page.waitForFunction(({at, captures}) => window.__QOIMA_TWIN_V3__.snapshot().t > at && Number(document.querySelector('.warehouse-magnifier-lens').dataset.captures) > captures, {at: clock, captures: before.captures});
    const after = await lens(), at = (await snapshot('twin')).t; await page.mouse.wheel(0, -400); const during = await snapshot('twin'); assert.equal(during.playing, true, 'Wheel does not pause playback'); assert(during.t >= at); await page.waitForFunction(at => window.__QOIMA_TWIN_V3__.snapshot().t > at, during.t); await pause('twin');
    assert(after.draws > before.draws && after.probe.copies_from_WebGL_canvas > before.probe.copies_from_WebGL_canvas); return {before, after, from_s: clock, to_s: at};
  });
  await check('twin-wheel-does-not-change-camera-or-clock', async () => {
    await pause('twin'); await page.waitForFunction(() => {const s = window.__QOIMA_TWIN_V3__.snapshot(); return !s.motion.camera_frame && !s.motion.pending_mode_change;}); await point('twin');
    const before = await snapshot('twin');
    for (let i = 0; i < 12; i++) await page.mouse.wheel(0, -400); assert.equal((await lens()).zoom, 6);
    for (let i = 0; i < 12; i++) await page.mouse.wheel(0, 400); assert.equal((await lens()).zoom, 1.5);
    const after = await snapshot('twin'); assert.equal(after.t, before.t); assert.deepEqual(after.motion.camera, before.motion.camera); assert.equal(after.playing, false);
    return {before_camera: before.motion.camera, after_camera: after.motion.camera, at_s: after.t, zoom: (await lens()).zoom};
  });
  await check('twin-complete-side-and-swipe-crops', async () => {
    const observations = [];
    for (let i = 0; i < 3; i++) await page.keyboard.press('+');
    for (const mode of ['side', 'swipe']) {
      await page.evaluate(mode => window.__QOIMA_TWIN_V3__.setMode(mode), mode);
      await page.waitForFunction(mode => {const s = window.__QOIMA_TWIN_V3__.snapshot(); return s.mode === mode && !s.motion.pending_mode_change && !s.motion.camera_frame;}, mode);
      const left = await crop('twin', .25), right = await crop('twin', .75); assert(left.lens.colors > 1 && right.lens.colors > 1, 'Both A and B contain actual rendered scene pixels');
      observations.push({mode, left, right}); await capture('twin-' + mode + '-magnified');
    }
    return observations;
  });
  await check('twin-paused-cache-edges-resize-and-leave', async () => {
    await pause('twin'); await point('twin', .25); await waitLens(); const before = await settlePausedLens();
    for (const fx of [.26, .29, .32, .35, .38]) await point('twin', fx);
    await page.waitForTimeout(200); const moved = await lens(); assert.equal(moved.probe.gl_draw_calls, before.probe.gl_draw_calls, 'Cached pointer motion creates no 3D render'); assert.equal(moved.captures, before.captures);
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
  await check('scenario-N3-and-N4-magnifier-smoke', async () => {const rows = []; for (const id of ['N3', 'N4']) {await open(id); await pause(id); await page.evaluate(() => window.__QOIMA_SCENARIO_V3__.seek(300)); const s = await enable(id), before = await snapshot(id); await page.mouse.wheel(0, -400); const after = await snapshot(id); assert.equal(after.clock.at_s, before.clock.at_s); assert.equal(after.scenario_id, id); rows.push({id, clock_s: after.clock.at_s, lens: s}); if (id === 'N3') await capture('scenario-N3-magnified'); await page.keyboard.press('Escape');} return rows;});
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
  await Promise.all(assetTasks);
} catch (error) {fatal = String(error.stack ?? error);}
finally {
  if (server) await attest().catch(error => {fatal ??= String(error);});
  for (const close of [async () => {if (browser?.isConnected()) {const c = await browser.newBrowserCDPSession(); await c.send('Browser.close');}}, () => context?.close(), () => browser?.close(), () => server?.close()]) try {await bounded(Promise.resolve().then(close), 4000);} catch {}
  try { if (server && owned.length) {
    const saved = path.join(out, 'owned-processes.json').replaceAll("'", "''");
    const liveScript = "$rows=Get-Content -LiteralPath '" + saved + "' -Raw|ConvertFrom-Json;$live=@();foreach($saved in @($rows)){$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$saved.ProcessId);if($p -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$saved.CreationDate).ToUniversalTime().Ticks){$live+=$saved.ProcessId}};ConvertTo-Json -InputObject @($live) -Compress";
    let live = JSON.parse((await run('pwsh', ['-NoProfile', '-NonInteractive', '-Command', liveScript], {windowsHide: true, timeout: 15000})).stdout || '[]');
    if (live.length) {
      forcedCleanup = true; try {await bounded(server.kill(), 5000);} catch {}
      await run('pwsh', ['-NoProfile', '-NonInteractive', '-Command', "$rows=Get-Content -LiteralPath '" + saved + "' -Raw|ConvertFrom-Json;foreach($saved in @($rows)){$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$saved.ProcessId);if($p -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$saved.CreationDate).ToUniversalTime().Ticks){Stop-Process -Id $saved.ProcessId -Force -ErrorAction SilentlyContinue}}"], {windowsHide: true, timeout: 15000});
    }
    await new Promise(resolve => setTimeout(resolve, 350));
    const fresh = await run('pwsh', ['-NoProfile', '-NonInteractive', '-Command', "$rows=Get-Content -LiteralPath '" + saved + "' -Raw|ConvertFrom-Json;$live=@();foreach($saved in @($rows)){if(Get-Process -Id $saved.ProcessId -ErrorAction SilentlyContinue){$live+=$saved.ProcessId}};ConvertTo-Json -InputObject @($live) -Compress"], {windowsHide: true, timeout: 15000});
    live = JSON.parse(fresh.stdout || '[]'); cleanup = live.length === 0;
    await fs.writeFile(path.join(out, 'cleanup.json'), JSON.stringify({checked_utc: new Date().toISOString(), forced_owned_cleanup: forcedCleanup, fresh_GetProcess_live: live, cleanup}, null, 2));
  } else cleanup = !server; } catch (error) {fatal ??= 'Cleanup verification: ' + String(error.stack ?? error); cleanup = false;}
}
const drift = [];
for (const [file, digest] of Object.entries(pins)) if (sha(await fs.readFile(path.join(front, file))) !== digest) drift.push(file);
const unexpectedRequests = failedRequests.filter(row => !(row.stage === 'twin-context-loss-reload-cleanup' && row.error?.errorText === 'net::ERR_ABORTED'));
const report = {passed: !fatal && cases.length === 10 && cases.every(c => c.passed) && !errors.length && !consoleErrors.length && !httpErrors.length && !unexpectedRequests.length && !drift.length && cleanup, viewer_scope: 'V3_ONLY', cases, fatal, gpu, screenshots, pageErrors: errors, consoleErrors, warnings, httpErrors, failedRequests, unexpected_request_failures: unexpectedRequests, source_hashes: pins, source_drift_during_run: drift, production_assets: served, cleanup, forced_owned_cleanup: forcedCleanup, synthetic_native_fixtures: {baseline_sha256: sha(nativeFixtures.baseline), candidate_sha256: sha(nativeFixtures.candidate), observed_until_tick: 100000000, recorded_workers: 0, recorded_carriers: 0, actual_backend_http: false}, scope: 'Actual desktop muted Chrome D3D11, one owned browser, warehouse viewers V3 only. Trusted mouse/keyboard/wheel, real 2D crop and WebGL draw calls observed without product hooks. Twin paused-cache/no-idle-loop; Warehouse V3/Scenario N3+N4/Heavy and NativePair warehouse from explicitly synthetic empty base_noop files. Actual context loss and reload; no backend/native-pair capture or physical collision acceptance claimed. Only the explicit context-loss/reload stage permits ERR_ABORTED request cancellation.'};
await fs.writeFile(path.join(out, 'checks.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({passed: report.passed, cases: cases.length, failed: cases.filter(c => !c.passed).map(c => c.name), fatal, cleanup, forced_owned_cleanup: forcedCleanup, out}));
process.exit(report.passed ? 0 : 1);
