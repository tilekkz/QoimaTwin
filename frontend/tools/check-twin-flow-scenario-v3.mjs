/** Deterministic source-topology packing story. Pure Node, no renderer/engine. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';

const front = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cache = await fs.mkdtemp(path.join(tmpdir(), 'qoima-twin-flow-'));
const compiled = new Map();
async function compile(relative) {
  if (compiled.has(relative)) return compiled.get(relative);
  const output = path.join(cache, relative + '.mjs');
  compiled.set(relative, output);
  let code = ts.transpileModule(await fs.readFile(path.join(front, relative), 'utf8'), {
    compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
  }).outputText;
  for (const hit of [...code.matchAll(/import\s+(\w+)\s+from\s+['"]([^'"]+\.json)['"];?/g)]) {
    const json = await fs.readFile(path.resolve(front, path.dirname(relative), hit[2]), 'utf8');
    code = code.replace(hit[0], 'const ' + hit[1] + '=' + json + ';');
  }
  for (const hit of [...code.matchAll(/from ['"](\.[^'"]+)['"]/g)]) {
    const dependency = path.posix.normalize(path.posix.join(path.posix.dirname(relative), hit[1] + '.ts'));
    code = code.replace(hit[0], 'from ' + JSON.stringify(pathToFileURL(await compile(dependency)).href));
  }
  await fs.mkdir(path.dirname(output), {recursive: true});
  await fs.writeFile(output, code);
  return output;
}
const load = async name => import(pathToFileURL(await compile('src/adaptive-v3/' + name + '.ts')));
const {adaptWarehouseV3} = await load('warehouseAdapter');
const texts = {};
for (const [key, file] of Object.entries({fixture: 'v3/warehouse-fixture-v3.json', layout: 'adaptive-v3/layout-manifest.json', registry: 'v3/worker-registry-v3.json', profiles: 'v3/worker-profiles-v3.json'})) {
  texts[key] = await fs.readFile(path.join(front, 'public/data', file), 'utf8');
}
const bundle = await adaptWarehouseV3(texts), conveyor = bundle.layout.data.conveyor;
for (const id of ['V3_SPUR03', 'V3_SPUR05', 'V3_SPUR06', 'V3_T03', 'V3_T05', 'V3_T06', 'V3_CURVE_EXCLUSIVE']) {
  assert.equal(conveyor.resources.find(row => row.resource_id === id).capacity, 1);
}
assert.equal(conveyor.source_assumptions.speed_m_s, .55);
assert.equal(conveyor.source_assumptions.transfer_dwell_s, .8);
assert(conveyor.cells.filter(row => row.resource_id === 'V3_MAIN').every(row => row.max_handling_units === 1));
const source = path.join(front, 'src/adaptive-v3/twin/twinFlowScenario.ts');
assert(await fs.access(source).then(() => true, () => false), 'Shared physical packing-flow story is implemented');
const {compileTwinFlowScenario} = await load('twin/twinFlowScenario');
const ready = {PK05: 106.84666666666668, PK06: 108.84666666666668};
const story = compileTwinFlowScenario(bundle, {staffReady_s: ready});
let checks = 0;
assert.equal(story.source_kind, 'visual_fixture'); assert.equal(story.engine_operation, false); checks++;
assert.equal(story.jobs.length, 18); assert(new Set(story.jobs.map(job => job.id)).size === 18); checks++;
for (const variant of ['A', 'B']) for (let tick = 0; tick <= story.duration_s; tick++) {
  const state = story.sample(variant, tick), counts = state.counts;
  assert.equal(counts.arrived, counts.waiting + counts.in_service + counts.in_transit + counts.completed);
  assert.equal(state.cargoFrames.filter(frame => frame.visible).length + counts.completed + state.queue.upstream, counts.arrived);
}
checks++;
const beforeA = story.sample('A', 30), beforeB = story.sample('B', 30);
assert.deepEqual(beforeA.cargoFrames, beforeB.cargoFrames); checks++;
assert(story.sample('A', 140).queue.main >= 8); assert(story.sample('A', 140).queue.main <= 16); checks++;
assert.equal(story.sample('B', story.duration_s).queue.total, 0); checks++;
assert(story.sample('B', 240).counts.packed > story.sample('A', 240).counts.packed); checks++;
for (const variant of ['A', 'B']) {
  const resources = Map.groupBy(story.audit(variant).reservations, row => row.resource_id);
  for (const [id, rows] of resources) {
    rows.sort((a, b) => a.from_s - b.from_s);
    for (let index = 1; index < rows.length; index++) assert(rows[index - 1].to_s <= rows[index].from_s + 1e-8, id);
  }
}
checks++;
const noDecision = compileTwinFlowScenario(bundle, {staffReady_s: ready, decisionEnabled: false});
for (const at of [0, 30, 46, 95, 140, 240]) assert.deepEqual(noDecision.sample('A', at).cargoFrames, noDecision.sample('B', at).cargoFrames);
checks++;
for (const at of [-1, story.duration_s + 1, NaN, Infinity]) assert.throws(() => story.sample('A', at));
assert.throws(() => story.sample('invalid', 0)); checks++;
const frozen = story.sample('B', 140), altered = story.sample('B', 140);
altered.cargoFrames[0].position[0] = -1000;
assert.deepEqual(story.sample('B', 140), frozen); checks++;
for (const variant of ['A', 'B']) {
  const audit = story.audit(variant);
  for (const job of story.jobs) {
    const work = audit.activities.filter(row => row.job_id === job.id && row.phase === 'packing');
    const total = work.reduce((sum, row) => sum + row.to_s - row.from_s, 0);
    assert(total <= 7.5 + 1e-8);
    if (work.length && work.at(-1).to_s <= 360) assert(Math.abs(total - 7.5) < 1e-8);
    for (const row of work) {
      if (row.station_id === 'PK03') assert(row.to_s <= 30 + 1e-8 || row.from_s >= 150 - 1e-8);
      else assert(row.from_s >= ready[row.station_id] && row.to_s <= 260);
    }
  }
  for (const row of audit.activities.filter(row => row.phase.startsWith('pivot'))) assert(Math.abs(row.to_s - row.from_s - .8) < 1e-8);
}
checks++;
for (const at of [0, 46, 140, 240, 360]) {
  const a = noDecision.sample('A', at), b = noDecision.sample('B', at);
  assert.deepEqual({...a, variant: 'B'}, b);
}
checks++;
const unavailable = compileTwinFlowScenario(bundle);
assert.equal(unavailable.sample('B', 240).stations.filter(row => row.station_id !== 'PK03' && row.available).length, 0);
assert(unavailable.sample('B', 240).queue.total > 0); checks++;
for (const variant of ['A', 'B']) {
  assert(story.atmosphere_events[variant].every(row => row.zone_id === 'PACKING_LIGHT_LINE'));
  assert(story.atmosphere_events[variant].some(row => row.at_s === 30));
}
checks++;
const original = story.sample('B', 140);
const beforeRestart = story.atmosphere_events.A.filter(row => row.at_s < 150).at(-1);
const restart = story.atmosphere_events.A.find(row => row.at_s === 150);
assert(restart, 'Outage end updates its cause even while the SOS state remains');
assert.equal(restart.state, beforeRestart.state);
assert(restart.cause.includes('PK03 доступен'));
assert(!restart.cause.includes('Ожидают '), 'Event reasons use thresholds, current counts come from sample');
checks++;
ready.PK05 = 240; ready.PK06 = 240;
assert.deepEqual(story.sample('B', 140), original); checks++;
console.log(JSON.stringify({state: 'PASS', checks, cuts: [0, 30, 46, 108.84666666666668, 140, 240, 360].map(at => ({at_s: at, A: story.sample('A', at).counts, B: story.sample('B', at).counts})), backend_engine_runs: 0, browser: 'NOT_RUN'}));
