/** Pure narration oracle and real source-flow smoke. No renderer or engine. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';

const front = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = await fs.mkdtemp(path.join(tmpdir(), 'qoima-flow-presenter-'));
const compiled = new Map();
async function compile(relative) {
  if (compiled.has(relative)) return compiled.get(relative);
  const target = path.join(output, relative + '.mjs');
  compiled.set(relative, target);
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
  await fs.mkdir(path.dirname(target), {recursive: true});
  await fs.writeFile(target, code);
  return target;
}
const load = async name => import(pathToFileURL(await compile('src/adaptive-v3/' + name + '.ts')));
const source = path.join(front, 'src/adaptive-v3/twin/twinFlowPresenter.ts');
assert(await fs.access(source).then(() => true, () => false), 'Runtime flow presenter replaces stale fixed narrative');
const {createTwinFlowPresenter} = await load('twin/twinFlowPresenter');
const counts = (arrived, waiting, packed, completed) => ({arrived, waiting, packed, completed, in_service: 0, in_transit: arrived - waiting - completed});
const oracle = {
  0: {A: counts(7, 3, 1, 0), B: counts(7, 3, 1, 0)},
  40: {A: counts(14, 6, 2, 1), B: counts(14, 6, 2, 1)},
  46: {A: counts(15, 7, 2, 1), B: counts(15, 7, 2, 1)},
  109: {A: counts(18, 14, 2, 2), B: counts(18, 12, 3, 2)},
  124: {A: counts(18, 15, 2, 2), B: counts(18, 8, 5, 2)},
  240: {A: counts(18, 10, 4, 3), B: counts(18, 2, 13, 7)},
  360: {A: counts(18, 4, 9, 6), B: counts(18, 0, 18, 18)},
};
const fixture = {
  source_kind: 'visual_fixture', engine_operation: false, operational_admission: false,
  duration_s: 360, comparison_horizon_s: 240, collection_clearance_s: 2,
  jobs: Array.from({length: 18}, (_, i) => ({id: 'manual-' + i, arrival_s: i, service_work_s: 7.5})),
  chapters: [{id: 'staff_ready', at_s: 109}],
  sample(variant, at) {
    assert(oracle[at], 'Narration uses a declared manual cut: ' + at);
    return {counts: structuredClone(oracle[at][variant]), outage: {from_s: 30, to_s: 150, active: at >= 30 && at < 150},
      decision: {at_s: 46, rerouted_count: at >= 46 && variant === 'B' ? 10 : 0},
      stations: [{station_id: 'PK05', available: variant === 'B' && at >= 109, status: at === 124 && variant === 'B' ? 'processing' : 'idle'},
        {station_id: 'PK06', available: variant === 'B' && at >= 109, status: at === 124 && variant === 'B' ? 'processing' : 'idle'}]};
  },
  audit() {return {activities: [{station_id: 'PK05', phase: 'packing', from_s: 112, to_s: 130},
    {station_id: 'PK06', phase: 'packing', from_s: 118, to_s: 134}]};},
};
const original = JSON.stringify(fixture);
const steps = createTwinFlowPresenter(fixture, {workers: 30, vehicles: 7});
let checks = 0;
assert.equal(steps.length, 7); assert.deepEqual(steps.map(step => step.t), [0, 40, 46, 109, 124, 240, 360]); checks++;
assert.equal(steps[0].view, 'warehouse'); assert(steps.slice(1).every(step => step.view === 'flow')); checks++;
assert.equal(steps.filter(step => step.mode === 'swipe').length, 1);
assert.equal(steps[5].mode, 'swipe'); checks++;
assert(steps[0].text.includes('персонал — 30')); assert(steps[0].text.includes('погрузчики — 7')); assert(steps[0].text.includes('18 грузов')); checks++;
assert(steps[1].text.includes('30–150')); assert(steps[1].text.includes('6')); checks++;
assert(steps[2].text.includes('10')); assert(steps[2].text.includes('по направлению')); checks++;
assert(steps[3].text.includes('109')); assert(steps[4].text.includes('постов в работе — 2')); checks++;
assert(steps[5].text.includes('A — 4')); assert(steps[5].text.includes('B — 13')); checks++;
assert(steps[6].text.includes('A — 9')); assert(steps[6].text.includes('B — 18')); assert(steps[6].text.includes('не завершена')); checks++;
assert.deepEqual(steps[0].focus, {target: [72, 1.5, 36], span: 184});
for (const step of steps.slice(1)) assert.deepEqual(step.focus, {target: [106.5, 1, 4], span: 52}); checks++;
assert(!/104|530|эффективност|выигрыш|рассчитал ИИ/.test(steps.map(step => step.text).join(' ')));
assert.deepEqual(steps.map(step => step.title), ['Склад в работе', 'Очередь у PK03', 'Подключаем резерв', 'Помощь на месте', 'Поток снова движется', 'Одинаковый момент', 'Результат перераспределения']);
assert(steps.every(step => step.text.split(/(?<=[.!?])\s+/).length === 2));
assert(steps[6].text.includes('вышло с линии A — 6'));
assert(steps[6].text.includes('помощники B вернулись'));
checks++;
steps[1].focus.target[0] = -1000;
assert.equal(steps[2].focus.target[0], 106.5);
assert.equal(createTwinFlowPresenter(fixture, {workers: 24, vehicles: 2})[0].text.includes('персонал — 24'), true);
assert.equal(JSON.stringify(fixture), original); checks++;
for (const invalid of [{workers: 0, vehicles: 2}, {workers: 1.5, vehicles: 2}, {workers: 30, vehicles: NaN}]) assert.throws(() => createTwinFlowPresenter(fixture, invalid));
assert.throws(() => createTwinFlowPresenter({...fixture, engine_operation: true}, {workers: 30, vehicles: 7})); checks++;
assert.throws(() => createTwinFlowPresenter({...fixture, chapters: []}, {workers: 30, vehicles: 7}));
const unavailable = {...fixture, sample(variant, at) {
  const frame = fixture.sample(variant, at); frame.stations[0].available = false; return frame;
}};
assert.throws(() => createTwinFlowPresenter(unavailable, {workers: 30, vehicles: 7})); checks++;
const {adaptWarehouseV3} = await load('warehouseAdapter');
const texts = {};
for (const [key, file] of Object.entries({fixture: 'v3/warehouse-fixture-v3.json', layout: 'adaptive-v3/layout-manifest.json', registry: 'v3/worker-registry-v3.json', profiles: 'v3/worker-profiles-v3.json'})) texts[key] = await fs.readFile(path.join(front, 'public/data', file), 'utf8');
const {compileTwinFlowScenario} = await load('twin/twinFlowScenario');
const scenario = compileTwinFlowScenario(await adaptWarehouseV3(texts), {staffReady_s: {PK05: 106.84666666666668, PK06: 108.84666666666668}});
const actual = createTwinFlowPresenter(scenario, {workers: 30, vehicles: 7});
assert.equal(actual[3].t, 108.84666666666668);
assert.equal(actual[5].t, scenario.comparison_horizon_s);
assert(actual[5].text.includes('A — ' + scenario.sample('A', 240).counts.packed));
assert(actual[5].text.includes('B — ' + scenario.sample('B', 240).counts.packed));
assert.equal(actual[6].t, scenario.duration_s);
assert(actual[6].text.includes('A — ' + scenario.sample('A', 360).counts.packed));
assert(actual[6].text.includes('B — ' + scenario.sample('B', 360).counts.packed));
assert(scenario.sample('B', actual[4].t).stations.filter(row => row.status === 'processing').length >= 2); checks++;
for (let index = 0; index < actual.length; index++) {
  const step = actual[index];
  assert(Number.isFinite(step.t) && step.t >= 0 && step.t <= scenario.duration_s);
  if (index) assert(step.t >= actual[index - 1].t);
  assert(step.focus.target.every(Number.isFinite));
  assert(Number.isFinite(step.focus.span) && step.focus.span >= 16 && step.focus.span <= 184);
}
checks++;
console.log(JSON.stringify({state: 'PASS', checks, actual_steps: actual, browser: 'NOT_RUN', backend_engine_runs: 0}));
