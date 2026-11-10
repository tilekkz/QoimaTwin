import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const code = ts.transpileModule(await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinScenario.ts', import.meta.url,
), 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
}).outputText;
const model = await import('data:text/javascript,' + encodeURIComponent(code));
const zone = 'PACKING_LIGHT_LINE';
const original = model.sampleAtmosphere('A', 58);
const duration = model.DEMO_DURATION_S;
const scenario = {
  source_kind: 'visual_fixture', engine_operation: false, operational_admission: false,
  duration_s: 120, chapters: [{at_s: 10, id: 'queue', label: 'Очередь'}],
  atmosphere_events: {
    A: [{at_s: 10, zone_id: zone, state: 'danger', cause: 'В очереди два груза'},
      {at_s: 20, zone_id: zone, state: 'sos', cause: 'Буфер заполнен'},
      {at_s: 22, zone_id: 'STANDARD_E', state: 'danger', cause: 'Подача ждёт', from_zone_id: zone}],
    B: [{at_s: 10, zone_id: zone, state: 'danger', cause: 'В очереди два груза'},
      {at_s: 30, zone_id: zone, state: 'control', cause: 'Очередь разобрана'}],
  },
};
const restore = model.installDemoFlowTimeline(scenario);
assert.equal(model.DEMO_DURATION_S, 120);
assert.equal(model.sampleAtmosphere('A', 9)[zone].state, 'control');
assert.equal(model.sampleAtmosphere('A', 10)[zone].state, 'danger');
assert.equal(model.sampleAtmosphere('A', 20)[zone].state, 'sos');
assert.equal(model.sampleAtmosphere('B', 30)[zone].state, 'control');
assert.equal(model.stateSegments('A', zone).at(-1).to_s, 120);
assert.equal(model.zoneHistory('A', zone, 20).length, 2);
assert.equal(model.activePulses('A', 20)[0].progress, .75);
assert(model.recoveredZones('B', 30).includes(zone));
assert.deepEqual(model.CHAPTERS, [{at_s: 10, label: 'Очередь'}]);
assert.throws(() => model.installDemoFlowTimeline({...scenario, duration_s: NaN}));
assert.equal(model.DEMO_DURATION_S, 120);
restore(); restore();
assert.equal(model.DEMO_DURATION_S, duration);
assert.deepEqual(model.sampleAtmosphere('A', 58), original);
console.log(JSON.stringify({passed: true, timeline_checks: 12, restored: true}));
