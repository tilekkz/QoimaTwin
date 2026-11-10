import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, mkdtemp, readFile, writeFile} from 'node:fs/promises';
import {dirname, resolve, join} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';

// Synthetic authenticated bundles only: no HTTP/backend capture or 3D claim.
const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(frontend, '..');
const outArg = process.argv.indexOf('--out');
const report = resolve(outArg < 0 ? join(repo, 'work/native-pair-adversarial/checks.json') : process.argv[outArg + 1]);
assert(report.startsWith(join(repo, 'work') + '\\') || report.startsWith(join(repo, 'work') + '/'), 'Report must remain in this worktree/work');
await mkdir(dirname(report), {recursive: true});
const cache = await mkdtemp(join(dirname(report), 'compiled-'));
const hash = raw => createHash('sha256').update(raw).digest('hex');
const sourceHashes = {};
for (const name of ['stream', 'playback']) {
  const source = await readFile(join(frontend, 'src/native-v3', name + '.ts'));
  sourceHashes[name + '.ts'] = hash(source);
  const code = ts.transpileModule(source.toString(), {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}}).outputText.replace(/from ['"]\.\/(\w+)['"]/g, "from './$1.mjs'");
  await writeFile(join(cache, name + '.mjs'), code);
}
const {decodeArmStream, verifyArmPair, parseNativeJSON, canonical} = await import(pathToFileURL(join(cache, 'stream.mjs')));
const {compilePlayback, createPlaybackClock} = await import(pathToFileURL(join(cache, 'playback.mjs')));
const id = letter => letter.repeat(64);
const fraction = (n, d = 1) => ({numerator: n, denominator: d});
const pose = n => ({edge_id: 'belt', progress: fraction(n), yaw_quarters: fraction(0)});
const op = {kind: 'relocation_carry', start_tick: 10, planned_end_tick: 20, source_node: 'a', target_node: 'b', route: {node_ids: ['a', 'b'], arc_ids: ['ab']}};
const moved = {actor_id: 'S01', job_id: 'move', hu_id: 'HU', source_owner: 'source', destination_owner: 'target', status: 'carrying', taken_tick: 10, placed_tick: null, returned_tick: null};
function fixture(change = () => {}, arm = 'baseline') {
  const catalog = {schema_version: 'qoima-relocation-run-0.1.0', run_id: id('b'), input_hash: id('c'), common_input_hash: id('d'), registry_common_hash: id('e'), engine_version: 'qoima-manual-relocation-proposal-1', observed_until_tick: 30, horizon_tick: 30, end_tick_limit: 40, outcome_kind: 'relocation', status: 'complete', outcome: {observation_end_tick: 30}};
  const events = [
    {seq: 0, tick: 10, kind: 'operation_started', actor_id: 'S01', operation: structuredClone(op)},
    {seq: 1, tick: 10, kind: 'relocation_taken', actor_id: 'S01', relocation: structuredClone(moved)},
    {seq: 2, tick: 10, kind: 'belt:admitted', belt_event: {job_id: 'order', hu_id: 'C1', payload_id: 'C1', pose: pose(0), kind: 'admitted', tick: 10}},
    {seq: 3, tick: 10, kind: 'belt:motion_started', belt_event: {job_id: 'order', hu_id: 'C1', payload_id: 'C1', pose: pose(0), kind: 'motion_started', tick: 10, planned_end_tick: 20}},
    {seq: 4, tick: 20, kind: 'operation_completed', actor_id: 'S01', operation: structuredClone(op)},
    {seq: 5, tick: 20, kind: 'relocation_placed', actor_id: 'S01', relocation: {...moved, status: 'returning', placed_tick: 20}},
    {seq: 6, tick: 20, kind: 'belt:motion_completed', belt_event: {job_id: 'order', hu_id: 'C1', payload_id: 'C1', pose: pose(1), kind: 'motion_completed', tick: 20}},
    {seq: 7, tick: 30, kind: 'relocation_returned', actor_id: 'S01', relocation: {...moved, status: 'complete', placed_tick: 20, returned_tick: 30}},
  ];
  const snapshot = {tick: 0, last_seq: -1, workers: [{actor_id: 'S01', node: 'a', operation: null}], belt: {carriers: []}, relocations: []};
  change({catalog, events, snapshot});
  const files = new Map([['catalog.json', catalog], ['events/00000001.json', events], ['snapshots/0000000000000000.json', snapshot]]);
  const rawFiles = new Map([...files].map(([path, body]) => [path, Buffer.from(canonical(body))]));
  const descriptors = [...rawFiles].map(([path, raw]) => ({path, bytes: raw.length, sha256: hash(raw)}));
  const manifest = {schema_version: catalog.schema_version, transport_version: 'qoima-relocation-run-bundle-0.1.0', engine_version: catalog.engine_version, run_id: catalog.run_id, input_hash: catalog.input_hash, common_input_hash: catalog.common_input_hash, registry_common_hash: catalog.registry_common_hash, inputs: {path: 'inputs.json', bytes: 10, sha256: id('c')}, catalog: descriptors[0], event_chunks: [{...descriptors[1], start_tick: 0, end_tick: 60000000, first_seq: 0, last_seq: 7}], snapshot_chunks: [{...descriptors[2], tick: 0, last_seq: -1, roles: ['checkpoint']}]};
  const rawManifest = Buffer.from(canonical(manifest));
  descriptors.push({path: 'manifest.json', bytes: rawManifest.length, sha256: hash(rawManifest)});
  rawFiles.set('manifest.json', rawManifest);
  const header = {record_type: 'header', schema_version: 'qoima-saved-relocation-arm-ndjson-0.1.0', pair_id: id('a'), arm, native_run_id: id('b'), input_hash: id('c'), pair_input_hash: id('f'), common_input_hash: id('d'), registry_common_hash: id('e'), origin: 'verified_saved_native_pair', note: 'Склад 📦 UTF-8', transport_manifest: manifest, stream_descriptors: descriptors};
  return [header, ...descriptors.map(d => ({record_type: 'file', ...d, body_base64: rawFiles.get(d.path).toString('base64')}))];
}
const bytes = records => Buffer.from(records.map(canonical).join('\n') + '\n');
function stream(raw, size = 137, hooks = {}) {
  let offset = 0;
  return new ReadableStream({pull(controller) {
    if (offset === raw.length) { controller.close(); return; }
    controller.enqueue(raw.subarray(offset, offset + size)); offset = Math.min(raw.length, offset + size);
  }, cancel(reason) { hooks.cancelled = true; hooks.reason = String(reason); }});
}
const decode = (records, options = {}, arm = 'baseline') => decodeArmStream(stream(bytes(records)), id('a'), arm, options);
function geometry() {return {nodes: new Map([['a', [0, 0, 0]], ['b', [10, 0, 0]]]), arcs: new Map([['ab', ['a', 'b']]]), slots: new Map([['source', {position: [0, 1, 0], yaw: 0}], ['target', {position: [10, 2, 0], yaw: 0}]]), edges: new Map([['belt', {from: [0, .92, 0], to: [10, .92, 0]}]])};}
const results = [];
async function check(name, run) {
  try { await run(); results.push({name, passed: true}); }
  catch (error) { results.push({name, passed: false, error: String(error?.stack ?? error)}); }
}
const original = await decode(fixture());
for (const size of [1, 2, 3, 7, 137, 65536]) await check('UTF8/chunk-split-' + size, async () => {
  const arm = await decodeArmStream(stream(bytes(fixture()), size), id('a'), 'baseline');
  assert.deepEqual(arm, original);
});
await check('valid-no-final-newline', async () => {assert.equal((await decodeArmStream(stream(bytes(fixture()).subarray(0, -1)), id('a'), 'baseline')).events.length, 8);});
await check('truncated-last-record', async () => {await assert.rejects(decodeArmStream(stream(bytes(fixture()).subarray(0, -13)), id('a'), 'baseline'));});
await check('missing-member', async () => {const a = fixture(); a.pop(); await assert.rejects(decode(a));});
await check('duplicate-member', async () => {const a = fixture(); a.push(a[1]); await assert.rejects(decode(a), /duplicate/i);});
await check('raw-member-corruption', async () => {const a = fixture(); a[1].body_base64 = Buffer.from('{}').toString('base64'); await assert.rejects(decode(a), /bytes|hash/i);});
await check('catalog-before-capture', async () => {const a = fixture(); [a[1], a[3]] = [a[3], a[1]]; await assert.rejects(decode(a), /catalog/i);});
await check('nonsemantic-member-order', async () => {const a = fixture(); [a[2], a[4]] = [a[4], a[2]]; assert.deepEqual(await decode(a), original);});
await check('event-sequence-gap', async () => {await assert.rejects(decode(fixture(({events}) => {events[4].seq = 42;})), /sequence/i);});
await check('duplicate-capture-tick', async () => {const a = fixture(); const d = a[0].transport_manifest.snapshot_chunks[0]; a[0].transport_manifest.snapshot_chunks.push(d); await assert.rejects(decode(a), /duplicate|descriptor|member/i);});
await check('invalid-UTF8', async () => {await assert.rejects(decodeArmStream(stream(Buffer.from([0x7b, 0x22, 0x80, 0x22, 0x7d, 0x0a])), id('a'), 'baseline'), /encoded|UTF|valid/i);});
await check('invalid-base64', async () => {const a = fixture(); a[1].body_base64 = '!!!!'; await assert.rejects(decode(a), /base64/i);});
await check('unsafe-integer-event-tick', async () => {await assert.rejects(decode(fixture(({events}) => {events[0].tick = 9007199254740993n;})), /integer/i);});
await check('exact-BigInt-and-string-preserved', async () => {const n = 10n ** 400n; const a = parseNativeJSON('{"n":' + n + ',"text":"' + n + '"}'); assert.equal(a.n, n); assert.equal(a.text, String(n));});
await check('retained-header-budget-immediate', async () => {const a = fixture(); await assert.rejects(decode([a[0]], {budgetBytes: 10}), /budget/i);});
await check('unicode-record-byte-limit', async () => {const a = fixture(); a[0].padding = 'Ж'.repeat(3 * 1024 * 1024); await assert.rejects(decodeArmStream(stream(bytes(a), 65536), id('a'), 'baseline'), /record.*limit/i);});
await check('pre-abort-cancels-owned-reader', async () => {const c = new AbortController(), hooks = {}; c.abort(new Error('test pre-abort')); await assert.rejects(decodeArmStream(stream(bytes(fixture()), 137, hooks), id('a'), 'baseline', {signal: c.signal}), /pre-abort/); assert(hooks.cancelled);});
await check('abort-interrupts-pending-read', async () => {
  const c = new AbortController(); let controller, cancelled = false;
  const body = new ReadableStream({start(v) {controller = v;}, cancel() {cancelled = true;}});
  const result = decodeArmStream(body, id('a'), 'baseline', {signal: c.signal}).then(() => 'resolved', e => String(e));
  await new Promise(r => setTimeout(r, 10)); c.abort(new Error('test pending-abort'));
  const outcome = await Promise.race([result, new Promise(r => setTimeout(() => r('PENDING_AFTER_ABORT'), 100))]);
  if (!cancelled) controller.close();
  await result;
  assert.match(outcome, /test pending-abort/); assert(cancelled);
});
await check('abort-during-buffered-members', async () => {const c = new AbortController(); await assert.rejects(decode(fixture(), {signal: c.signal, progress() {c.abort(new Error('test progress-abort'));}}), /progress-abort/);});
await check('header-and-body-pair-identities', async () => {const b = await decode(fixture(() => {}, 'candidate'), {}, 'candidate'); verifyArmPair(original, b); assert.throws(() => verifyArmPair(original, {...b, header: {...b.header, pair_input_hash: id('7')}}), /pair.*identity/i);});
await check('nonfinite-node-geometry-refused', async () => {const g = geometry(); g.nodes.get('b')[0] = NaN; assert.throws(() => compilePlayback(original, g), /finite|geometry/i);});
await check('nonfinite-slot-geometry-refused', async () => {const g = geometry(); g.slots.get('target').yaw = Infinity; assert.throws(() => compilePlayback(original, g), /finite|geometry/i);});
await check('negative-conveyor-radius-refused', async () => {const g = geometry(); Object.assign(g.edges.get('belt'), {centre: [0, .92, 0], radius: -1, startAngle: 0, endAngle: Math.PI / 2}); assert.throws(() => compilePlayback(original, g), /radius|geometry/i);});
await check('huge-valid-rational-finite-projection', async () => {
  const n = 10n ** 400n;
  const arm = await decode(fixture(({snapshot}) => {snapshot.belt.carriers.push({job_id: 'huge', hu_id: 'hugeHU', payload_id: 'hugeHU', status: 'admitted', pose: {edge_id: 'belt', progress: fraction(n, 2n * n), yaw_quarters: fraction(n, 2n * n)}, motion: null});}));
  const frame = compilePlayback(arm, geometry()).sample(0).carriers[0];
  assert(frame.position.every(Number.isFinite)); assert.equal(frame.position[0], 5); assert.equal(frame.yaw, Math.PI / 4);
});
await check('tiny-valid-rational-remains-nonzero', async () => {
  const arm = await decode(fixture(({snapshot}) => {snapshot.belt.carriers.push({job_id: 'tiny', hu_id: 'tinyHU', payload_id: 'tinyHU', status: 'admitted', pose: {edge_id: 'belt', progress: fraction(1n, 10n ** 100n), yaw_quarters: fraction(-1n, 10n ** 100n)}, motion: null});}));
  const f = compilePlayback(arm, geometry()).sample(0).carriers[0]; assert(f.position[0] > 0); assert(f.yaw < 0); assert(Math.abs(f.position[0] / 1e-99 - 1) < 1e-15); assert(Math.abs(f.yaw / (-1e-100 * Math.PI / 2) - 1) < 1e-15);
});
await check('rational-subnormal-and-underflow', async () => {
  for (const exponent of [323, 400]) {
    const arm = await decode(fixture(({snapshot}) => {snapshot.belt.carriers.push({job_id: 'small', hu_id: 'smallHU', payload_id: 'smallHU', status: 'admitted', pose: {edge_id: 'belt', progress: fraction(1n, 10n ** BigInt(exponent)), yaw_quarters: fraction(-1n, 10n ** BigInt(exponent))}, motion: null});}));
    const f = compilePlayback(arm, geometry()).sample(0).carriers[0]; assert.equal(f.position[0], Number('1e-' + exponent) * 10); assert.equal(f.yaw, -Number('1e-' + exponent) * Math.PI / 2);
  }
});
await check('duplicate-captured-actor-refused', async () => {await assert.rejects(decode(fixture(({snapshot}) => {snapshot.workers.push(structuredClone(snapshot.workers[0]));})), /duplicate|actor/i);});
await check('reversed-relocation-times-refused', async () => {await assert.rejects(decode(fixture(({events}) => {events[5].relocation.taken_tick = 25;})), /relocation|interval|time/i);});
await check('belt-inner-outer-event-tick-refused', async () => {await assert.rejects(decode(fixture(({events}) => {events[2].belt_event.tick = 9;})), /tick|event/i);});
await check('captured-motion-null-end-refused', async () => {await assert.rejects(decode(fixture(({snapshot}) => {snapshot.belt.carriers.push({job_id: 'bad', hu_id: 'badHU', payload_id: 'badHU', status: 'motion', pose: pose(0), motion: {start: pose(0), end: null, start_tick: 0, planned_end_tick: 5}});})), /motion|pose|endpoint/i);});
await check('partial-nullable-relocation-preserved', async () => {const arm = await decode(fixture(({events}) => {events[5].relocation.taken_tick = null;})); assert.equal(arm.events[5].relocation.taken_tick, null); assert.equal(compilePlayback(arm, geometry()).sample(20).relocations[0].custody, 'target');});
await check('captured-operation-with-null-node', async () => {const arm = await decode(fixture(({snapshot}) => {snapshot.workers[0] = {actor_id: 'S01', node: null, operation: {...op, start_tick: 0}};})); assert.deepEqual(compilePlayback(arm, geometry()).sample(0).actors[0].position, [0, 0, 0]);});
await check('unrelated-optional-curve-fields-remain-optional', async () => {const g = geometry(); g.edges.get('belt').radius = 1; assert.equal(compilePlayback(original, g).sample(15).carriers[0].position[0], 5);});
await check('huge-periodic-yaw-and-exact-pivot-delta', async () => {
  const n = 10n ** 400n;
  const arm = await decode(fixture(({snapshot}) => {const start = {...pose(0), yaw_quarters: fraction(n + 3n)}, end = {...pose(1), yaw_quarters: fraction(n + 4n)}; snapshot.belt.carriers.push({job_id: 'periodic', hu_id: 'periodicHU', payload_id: 'periodicHU', status: 'pivot', pose: start, motion: {start, end, start_tick: 0, planned_end_tick: 10}});}));
  assert.equal(arm.captures[0].carriers[0].pose.yaw_quarters.numerator, n + 3n);
  const play = compilePlayback(arm, geometry()); assert.equal(play.sample(0).carriers[0].yaw, 3 * Math.PI / 2); assert.equal(play.sample(5).carriers[0].yaw, 7 * Math.PI / 4); assert.equal(play.sample(10).carriers[0].yaw % (2 * Math.PI), 0);
});
await check('huge-yaw-phase-exact-before-periodic-reduction', async () => {
  const n = 10n ** 400n;
  for (const sign of [1n, -1n]) {
    const arm = await decode(fixture(({snapshot}) => {const start = {...pose(0), yaw_quarters: fraction(0)}, end = {...pose(1), yaw_quarters: fraction(sign * (n + 1n))}; snapshot.belt.carriers.push({job_id: 'long-spin', hu_id: 'spinHU', payload_id: 'spinHU', status: 'pivot', pose: start, motion: {start, end, start_tick: 0, planned_end_tick: 10}});}));
    const play = compilePlayback(arm, geometry()); assert.equal(arm.captures[0].carriers[0].motion.end.yaw_quarters.numerator, sign * (n + 1n));
    for (let tick = 0; tick <= 10; tick++) {const yaw = play.sample(tick).carriers[0].yaw; assert(Number.isFinite(yaw)); assert(Math.abs(yaw - Number(sign) * tick / 10 * Math.PI / 2) < 1e-14);}
  }
});
await check('finite-but-overflowing-geometry-fails-closed', async () => {const g = geometry(); g.nodes.get('a')[0] = -1e308; g.nodes.get('b')[0] = 1e308; assert.throws(() => compilePlayback(original, g).sample(15), /finite|geometry/i);});
await check('stalled-underlying-cancel-does-not-hang-rejection', async () => {
  const body = new ReadableStream({start(c) {c.enqueue(Buffer.from('{}\n'));}, cancel() {return new Promise(() => {});}});
  const result = decodeArmStream(body, id('a'), 'baseline').then(() => 'resolved', e => String(e));
  const outcome = await Promise.race([result, new Promise(r => setTimeout(() => r('PENDING_CANCEL'), 100))]); assert.match(outcome, /Unsupported native stream/);
});
await check('deterministic-seek-custody', async () => {
  const play = compilePlayback(original, geometry()); const at15 = play.sample(15); assert.equal(at15.actors[0].position[0], 5); assert.equal(at15.relocations[0].custody, 'actor:S01'); assert.equal(play.sample(20).relocations[0].custody, 'target');
  for (const t of [30, 0, 20, 1, 30, 15]) play.sample(t);
  assert.deepEqual(play.sample(15), at15); assert.deepEqual(play.sample(0), play.sample(0));
});
await check('returned-frame-does-not-mutate-future-seek', async () => {const play = compilePlayback(original, geometry()); const frame = play.sample(0); frame.actors[0].position[0] = 999; assert.equal(play.sample(0).actors[0].position[0], 0);});
await check('tick-boundaries-and-pause-rate', async () => {const p = compilePlayback(original, geometry()); for (const t of [-1, .1, 31, NaN]) assert.throws(() => p.sample(t)); const c = createPlaybackClock(30); c.play(); c.advance(.00001); assert.equal(c.tick, 10); c.pause(); c.advance(1); assert.equal(c.tick, 10); c.setRate(60); c.seek(5); c.play(); c.advance(1); assert.equal(c.tick, 30); assert.equal(c.playing, false);});

const after = {};
for (const name of ['stream', 'playback']) after[name + '.ts'] = hash(await readFile(join(frontend, 'src/native-v3', name + '.ts')));
assert.deepEqual(after, sourceHashes, 'Source changed during this test run');
const receipt = {schema_id: 'qoima.native-pair-adversarial-tests.v1', created_utc: new Date().toISOString(), passed: results.every(x => x.passed), total: results.length, passed_count: results.filter(x => x.passed).length, failed_count: results.filter(x => !x.passed).length, source_hashes: sourceHashes, checker_sha256: hash(await readFile(fileURLToPath(import.meta.url))), contract_scope: 'Available local stream/playback guards and existing synthetic test protocol; ADR0099 primary document unavailable. Authenticated hashes are recomputed for semantic negative fixtures.', browser: 'NOT_RUN', actual_http: 'NOT_RUN', native_backend_capture: 'NOT_CLAIMED', results};
await writeFile(report, JSON.stringify(receipt, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify({passed: receipt.passed, total: receipt.total, passed_count: receipt.passed_count, failed_count: receipt.failed_count, failures: results.filter(x => !x.passed).map(x => ({name: x.name, error: x.error.split('\n')[0]})), report, source_hashes: sourceHashes}));
if (!receipt.passed) process.exitCode = 1;
