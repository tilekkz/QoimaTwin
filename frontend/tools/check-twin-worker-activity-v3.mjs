import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const code = ts.transpileModule(await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinScenario.ts', import.meta.url,
), 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
}).outputText;
const {reactionsAt, workerStatus} = await import('data:text/javascript,' + encodeURIComponent(code));
const workers = ['K01', 'K03', 'K04', 'K05'].map(actor_id =>
  ({actor_id, zone_id: 'PACKING_LIGHT_LINE'}));
const activities = [
  {actor_id: 'K01', phase: 'working', station_id: 'PK05', message: 'Упаковывает на PK05'},
  {actor_id: 'K03', phase: 'waiting', station_id: 'PK03', message: 'Ждёт освобождения PK03'},
  {actor_id: 'K05', phase: 'break', station_id: null, message: 'На перерыве'},
];
const before = structuredClone(activities);
const shown = reactionsAt('A', 58, workers, activities);
assert.equal(shown.find(row => row.actor_id === 'K01').bubble, 'work');
assert.equal(shown.find(row => row.actor_id === 'K01').text, activities[0].message);
assert.equal(shown.find(row => row.actor_id === 'K03').bubble, 'wait');
assert.equal(shown.find(row => row.actor_id === 'K04'), undefined);
assert.equal(shown.find(row => row.actor_id === 'K05'), undefined);
assert.equal(workerStatus('A', 58, workers, 'K05', activities), 'На перерыве');
assert.equal(workerStatus('A', 58, workers, 'K01', activities), 'Упаковывает на PK05');
const walking = [{...activities[0], phase: 'walking_to_help', station_id: null, message: 'Идёт к PK05'}];
assert.equal(reactionsAt('B', 58, workers, walking).find(row => row.actor_id === 'K01').bubble, 'walk');
assert.deepEqual(activities, before);
assert(reactionsAt('A', 58, workers).length > 0);
console.log(JSON.stringify({passed: true, activity_checks: 10, legacy_reactions_retained: true}));
