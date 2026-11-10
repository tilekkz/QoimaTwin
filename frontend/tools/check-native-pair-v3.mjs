import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp, readFile, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import {createReadStream} from 'node:fs';
import {Readable} from 'node:stream';

const cache = await mkdtemp(join(tmpdir(), 'qoima-native-pair-'));
for (const name of ['stream', 'playback']) {
  const source = await readFile(resolve('src/native-v3/' + name + '.ts'), 'utf8');
  const code = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}}).outputText.replace(/from ['"]\.\/(\w+)['"]/g, "from './$1.mjs'");
  await writeFile(join(cache, name + '.mjs'), code);
}
const {decodeArmStream, verifyArmPair, parseNativeJSON} = await import(pathToFileURL(join(cache, 'stream.mjs')));
const {compilePlayback, createPlaybackClock} = await import(pathToFileURL(join(cache, 'playback.mjs')));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const id = character => character.repeat(64);
const fraction = n => ({numerator: n, denominator: 1});
const pose = progress => ({edge_id: 'belt', progress: fraction(progress), yaw_quarters: fraction(0)});
const operation = {kind: 'relocation_carry', start_tick: 10, planned_end_tick: 20, source_node: 'a', target_node: 'b', route: {node_ids: ['a', 'b'], arc_ids: ['ab']}};
const relocation = {actor_id: 'S01', job_id: 'move', hu_id: 'HU', source_owner: 'source', destination_owner: 'target', status: 'carrying', taken_tick: 10, placed_tick: null, returned_tick: null};
const events = [
  {seq: 0, tick: 10, kind: 'operation_started', actor_id: 'S01', operation},
  {seq: 1, tick: 10, kind: 'relocation_taken', actor_id: 'S01', relocation},
  {seq: 2, tick: 10, kind: 'belt:admitted', belt_event: {job_id: 'order', hu_id: 'C1', payload_id: 'C1', pose: pose(0), kind: 'admitted', tick: 10}},
  {seq: 3, tick: 10, kind: 'belt:motion_started', belt_event: {job_id: 'order', hu_id: 'C1', payload_id: 'C1', pose: pose(0), kind: 'motion_started', tick: 10, planned_end_tick: 20}},
  {seq: 4, tick: 20, kind: 'operation_completed', actor_id: 'S01', operation},
  {seq: 5, tick: 20, kind: 'relocation_placed', actor_id: 'S01', relocation: {...relocation, status: 'returning', placed_tick: 20}},
  {seq: 6, tick: 20, kind: 'belt:motion_completed', belt_event: {job_id: 'order', hu_id: 'C1', payload_id: 'C1', pose: pose(1), kind: 'motion_completed', tick: 20}},
  {seq: 7, tick: 30, kind: 'relocation_returned', actor_id: 'S01', relocation: {...relocation, status: 'complete', placed_tick: 20, returned_tick: 30}},
];
const capture = {tick: 0, last_seq: -1, workers: [{actor_id: 'S01', node: 'a', operation: null}], belt: {carriers: []}, relocations: []};

function fixture(arm = 'baseline', changes = {}, baseNoop = false) {
  const catalog = {schema_version: 'qoima-relocation-run-0.1.0', run_id: id('b'), input_hash: id('c'), common_input_hash: id('d'), registry_common_hash: id('e'), engine_version: 'qoima-manual-relocation-proposal-1', observed_until_tick: 30, horizon_tick: 30, end_tick_limit: 40, outcome_kind: 'relocation', status: 'complete', outcome: {observation_end_tick: 30}};
  const initial = structuredClone(capture);
  if (baseNoop) {catalog.outcome_kind = 'base_noop'; delete initial.relocations;}
  const files = new Map([['catalog.json', catalog], ['events/00000001.json', events], ['snapshots/0000000000000000.json', initial]]);
  const rows = [...files].map(([path, value]) => {const raw = Buffer.from(JSON.stringify(value)); return {path, bytes: raw.length, sha256: hash(raw)};});
  const manifest = {schema_version: catalog.schema_version, transport_version: 'qoima-relocation-run-bundle-0.1.0', engine_version: catalog.engine_version, run_id: catalog.run_id, input_hash: catalog.input_hash, common_input_hash: catalog.common_input_hash, registry_common_hash: catalog.registry_common_hash, inputs: {path: 'inputs.json', bytes: 10, sha256: id('c')}, catalog: rows[0], event_chunks: [{...rows[1], start_tick: 0, end_tick: 60000000, first_seq: 0, last_seq: 7}], snapshot_chunks: [{...rows[2], tick: 0, last_seq: -1, roles: ['checkpoint']}]};
  const rawManifest = Buffer.from(JSON.stringify(manifest));
  rows.push({path: 'manifest.json', bytes: rawManifest.length, sha256: hash(rawManifest)});
  files.set('manifest.json', manifest);
  const header = {record_type: 'header', schema_version: 'qoima-saved-relocation-arm-ndjson-0.1.0', pair_id: id('a'), arm, native_run_id: id('b'), input_hash: id('c'), pair_input_hash: id('f'), common_input_hash: id('d'), registry_common_hash: id('e'), origin: 'verified_saved_native_pair', transport_manifest: manifest, stream_descriptors: rows, ...changes};
  const records = [header, ...rows.map(row => ({record_type: 'file', ...row, body_base64: Buffer.from(JSON.stringify(files.get(row.path))).toString('base64')}))];
  return {records, header};
}
const readable = records => {const raw = new TextEncoder().encode(records.map(row => JSON.stringify(row)).join('\n') + '\n'); return new ReadableStream({start(controller) {for (let i = 0; i < raw.length; i += 137) controller.enqueue(raw.slice(i, i + 137)); controller.close();}});};
const decode = (records, arm = 'baseline', options = {}) => decodeArmStream(readable(records), id('a'), arm, options);
let checks = 0;
async function rejects(change, message) {const data = fixture(); change(data.records); await assert.rejects(() => decode(data.records), message); checks++;}
const data = fixture();
const arm = await decode(data.records);
const baseNoop = await decode(fixture('baseline', {}, true).records);
assert.deepEqual(baseNoop.captures[0].relocations, []); checks++;
assert.equal(parseNativeJSON('{"numerator":12345678901234567890,"text":"12345678901234567890"}').numerator, 12345678901234567890n);
assert.equal(parseNativeJSON('{"text":"12345678901234567890"}').text, '12345678901234567890'); checks++;
assert.throws(() => parseNativeJSON('{"n":09007199254740993}'), /JSON|number|integer/i); checks++;
assert.equal(arm.captures.length, 1);
assert.equal(arm.events.length, 8);
assert(arm.retainedBytes < 64 * 1024 * 1024);
checks++;
await rejects(rows => {rows[0].arm = 'candidate';}, /arm/i);
await rejects(rows => {rows[0].pair_id = id('9');}, /pair/i);
await rejects(rows => {rows[1].body_base64 = Buffer.from('{}').toString('base64');}, /bytes|hash/i);
await rejects(rows => {rows.push(rows[1]);}, /duplicate|member/i);
await rejects(rows => {rows.pop();}, /missing|incomplete/i);
await rejects(rows => {rows[0].transport_manifest.inputs.sha256 = id('8');}, /input/i);
await rejects(rows => {rows[0].stream_descriptors[0].bytes = 2 ** 40;}, /limit|descriptor|bytes/i);
await assert.rejects(() => decode(data.records, 'baseline', {budgetBytes: 10}), /budget|limit/i); checks++;
const other = await decode(fixture('candidate').records, 'candidate');
assert.doesNotThrow(() => verifyArmPair(arm, other)); checks++;
assert.throws(() => verifyArmPair(arm, {...other, header: {...other.header, pair_input_hash: id('7')}}), /pair|input/i); checks++;
const geometry = {nodes: new Map([['a', [0, 0, 0]], ['b', [10, 0, 0]]]), arcs: new Map([['ab', ['a', 'b']]]), slots: new Map([['source', {position: [0, 1, 0], yaw: 0}], ['target', {position: [10, 2, 0], yaw: 0}]]), edges: new Map([['belt', {from: [0, .92, 0], to: [10, .92, 0]}]])};
const playback = compilePlayback(arm, geometry);
assert.equal(playback.sample(9).relocations.length, 0);
assert.equal(playback.sample(10).relocations[0].custody, 'actor:S01');
assert.equal(playback.sample(15).carriers[0].position[0], 5);
assert.equal(playback.sample(15).actors[0].position[0], 5);
assert.equal(playback.sample(20).relocations[0].custody, 'target');
assert.equal(playback.sample(20).relocations[0].position[1], 2);
assert.equal(playback.sample(30).relocations[0].status, 'complete'); checks++;
const beforeRewind = playback.sample(15), initialFrame = playback.sample(0);
playback.sample(30);
assert.deepEqual(playback.sample(15), beforeRewind);
assert.deepEqual(playback.sample(0), initialFrame); checks++;
const withCapture = structuredClone(arm);
withCapture.captures.push({tick: 15, last_seq: 3, workers: [{actor_id: 'S01', node: null, operation}], carriers: [{job_id: 'order', hu_id: 'C1', payload_id: 'C1', status: 'motion', pose: pose(.5), motion: {start: pose(0), end: pose(1), start_tick: 10, planned_end_tick: 20}}], relocations: [relocation]});
const capturedPlayback = compilePlayback(withCapture, geometry);
assert.equal(capturedPlayback.sample(15).actors[0].position[0], 5);
assert.equal(capturedPlayback.sample(15).carriers[0].position[0], 5);
assert.deepEqual(capturedPlayback.sample(0), initialFrame); checks++;
const partial = structuredClone(arm);
partial.catalog.observed_until_tick = 15; partial.catalog.status = 'partial';
partial.events = partial.events.filter(row => row.tick <= 15);
assert.throws(() => compilePlayback(partial, geometry), /endpoint|partial/i); checks++;
assert.throws(() => playback.sample(31), /observed|tick/i);
assert.throws(() => playback.sample(-1), /tick/i);
assert.throws(() => playback.sample(.5), /tick/i); checks++;
const clock = createPlaybackClock(30);
clock.play(); clock.advance(.00001); assert.equal(clock.tick, 10);
clock.pause(); clock.advance(1); assert.equal(clock.tick, 10);
clock.seek(5); assert.equal(clock.tick, 5);
clock.play(); clock.advance(1); assert.equal(clock.tick, 30); assert.equal(clock.playing, false); checks++;
console.log(JSON.stringify({state: 'PASS', checks, browser: 'NOT_RUN', actual_http: 'NOT_RUN'}));
if (process.argv[2]) {
  const raw = process.argv[2], pair = process.argv[3], selected = process.argv[4];
  const actual = await decodeArmStream(Readable.toWeb(createReadStream(raw)), pair, selected);
  console.log(JSON.stringify({actual_file_projection: 'PASS', arm: selected, snapshots: actual.captures.length, events: actual.events.length, retained_bytes: actual.retainedBytes, observed_until_tick: actual.catalog.observed_until_tick, source_kind: actual.header.origin}));
}
