import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const code = ts.transpileModule(await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinStationIndicators.ts', import.meta.url,
), 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
}).outputText;
const {stationPresentation, packingStationPositions, createTwinStationIndicators} = await import(
  'data:text/javascript,' + encodeURIComponent(code));
assert.deepEqual(stationPresentation('processing', true), {state: 'work', text: 'Работает'});
assert.deepEqual(stationPresentation('outage', true), {state: 'sos', text: 'Остановлен'});
assert.deepEqual(stationPresentation('reserved', true), {state: 'transfer', text: 'Передача'});
assert.deepEqual(stationPresentation('idle', true), {state: 'ready', text: 'Готов'});
assert.deepEqual(stationPresentation('unavailable', false), {state: 'reserve', text: 'Резерв'});
assert.deepEqual(stationPresentation('unavailable', true), {state: 'support', text: 'Ждёт помощника'});
const layout = JSON.parse(await fs.readFile(new URL(
  '../public/data/adaptive-v3/layout-manifest.json', import.meta.url), 'utf8'));
assert.deepEqual([...packingStationPositions(layout.data.conveyor.packing_stations)], [
  ['PK03', [84, 5, 5.2]], ['PK05', [106, 5, 5.2]], ['PK06', [117, 5, 5.2]],
]);
const elements = [];
const document = {createElement() {return {
  dataset: {}, style: {}, children: [], hidden: false,
  append(...children) {this.children.push(...children);},
  get lastElementChild() {return this.children.at(-1);},
  setAttribute() {}, remove() {this.removed = true;},
};}};
const indicators = createTwinStationIndicators({ownerDocument: document,
  append(element) {elements.push(element);}}, new Map([['PK05', [106, 5, 5.2]]]));
const station = {station_id: 'PK05', status: 'unavailable', staff_ready_s: 107};
const frame = {variant: 'B', at_s: 46, decision: {applied: true}, stations: [station]};
indicators.update(frame, () => ({x: 50, y: 50}), {x: 0, y: 0, w: 100, h: 100}, true);
assert.equal(elements[0].dataset.state, 'support');
indicators.update({...frame, at_s: 360}, () => ({x: 50, y: 50}),
  {x: 0, y: 0, w: 100, h: 100}, true);
assert.equal(elements[0].dataset.state, 'reserve', 'Returned staff leave a reserve post');
indicators.dispose();
assert.equal(elements[0].removed, true);
console.log(JSON.stringify({passed: true, station_state_cases: 6, source_positions: 3,
  lifecycle_cases: 3}));
