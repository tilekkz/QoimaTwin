/** Regression for the independently observed B-slot lookup failure, added after its repair. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, mkdtemp, readFile, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cache = await mkdtemp(path.join(tmpdir(), 'qoima-twin-cargo-projection-'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const pins = new Map();
async function source(relative) {
  const bytes = await readFile(path.join(frontend, relative));
  pins.set(relative, hash(bytes));
  return bytes;
}

for (const name of ['workerRegistry', 'workerProfiles', 'warehouseAdapter', 'workerRoleAssignment',
  'warehouseLayoutPlan', 'warehouseCargo', 'warehouseCargoHolders', 'twin/twinInventory',
  'twin/twinScenario', 'twin/twinSearch']) {
  const bytes = await source('src/adaptive-v3/' + name + '.ts');
  const code = ts.transpileModule(bytes.toString(), {compilerOptions: {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  }}).outputText.replace(/from (['"])(\.{1,2}\/[^'"]+)\1/g,
    (_, quote, specifier) => `from ${quote}${specifier}.mjs${quote}`);
  const output = path.join(cache, name + '.mjs');
  await mkdir(path.dirname(output), {recursive: true});
  await writeFile(output, code, {flag: 'wx'});
}
const load = name => import(pathToFileURL(path.join(cache, name + '.mjs')));
const {adaptWarehouseV3} = await load('warehouseAdapter');
const {createWarehouseCargo} = await load('warehouseCargo');
const {createDenseWarehouseLayoutPlan} = await load('warehouseLayoutPlan');
const {createTwinInventory} = await load('twin/twinInventory');
const {outboundCandidates} = await load('twin/twinScenario');
const {buildIndex, search, shortId} = await load('twin/twinSearch');
const texts = {};
for (const [key, relative] of Object.entries({fixture: 'v3/warehouse-fixture-v3.json',
  layout: 'adaptive-v3/layout-manifest.json', registry: 'v3/worker-registry-v3.json',
  profiles: 'v3/worker-profiles-v3.json'})) {
  texts[key] = (await source('public/data/' + relative)).toString();
}
const bundle = await adaptWarehouseV3(texts);
const beforeBundle = JSON.stringify(bundle);
const cargo = createWarehouseCargo(bundle), accepted = [];
for (const candidate of outboundCandidates(bundle)) for (const target of candidate.candidates) {
  const result = cargo.apply([{handling_unit_id: candidate.hu.handling_unit_id,
    destination: {kind: 'storage_slot', slot_id: target.slot_id}}]);
  if (result.ok) {accepted.push(candidate.hu.handling_unit_id); break;}
}
assert.equal(accepted.length, 5, 'The genuine source admits the five comparison moves');
const bindingsB = cargo.snapshot();

const pagePath = 'src/adaptive-v3/twin/twinPage.ts';
const page = (await source(pagePath)).toString();
const parsed = ts.createSourceFile(pagePath, page, ts.ScriptTarget.Latest, true);
const helperNames = ['activeCargo', 'cargoSlot', 'cargoAtSlot', 'inventoryCargo', 'selectionCopy',
  'indexBundle', 'rebuildSearchIndex', 'goSearch'];
const helpers = helperNames.map(name => {
  const node = parsed.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name);
  assert(node, 'Actual page helper ' + name);
  return node.getText(parsed);
}).join('\n');
// These explicit boundary stubs preserve the actual lookup/search function bodies.
const wrapper = `function makeHarness(context) {
  let {bundle, currentInventory, layoutEnabled, layoutCandidate, slottingBindingsB} = context;
  let searchIndex=[], hintMap=new Map();
  const scene={getCargoBindings:()=>[]}, zoneLabel=value=>value;
  const searchBox={dataset:{open:'false'}}, renderSearch=()=>{};
  const selected=[], setSearch=()=>{}, select=(...row)=>selected.push(row), fly=()=>{};
  const twin={offsetOf:()=>[0,0,0], setFocus:()=>{}};
  ${helpers}
  return {cargoAtSlot, inventoryCargo, selectionCopy, rebuildSearchIndex, goSearch,
    entries:()=>searchIndex.map(row=>row.e), matches:query=>search(searchIndex,query), selected,
    structural(next, plan) {layoutEnabled=true; currentInventory=next; layoutCandidate=plan;}
  };
}`;
const compiled = ts.transpileModule(wrapper, {compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None,
}}).outputText;
const makeHarness = new Function('buildIndex', 'search', 'shortId', compiled + '\nreturn makeHarness;')(buildIndex, search, shortId);
const harness = makeHarness({bundle, currentInventory: createTwinInventory(bundle, null, 'source530'),
  layoutEnabled: false, layoutCandidate: null, slottingBindingsB: bindingsB});
const cases = [];
function check(name, run) {run(); cases.push(name);}
harness.rebuildSearchIndex();

check('B destination occupancy and slot search match all five rendered relocations', () => {
  for (const id of accepted) {
    const binding = bindingsB.find(row => row.handling_unit_id === id);
    assert.notEqual(binding.destination.slot_id, binding.cargo.location.slot_id);
    assert.strictEqual(harness.inventoryCargo(id, 'B'), binding);
    assert.strictEqual(harness.cargoAtSlot(binding.destination.slot_id, 'B'), binding);
    harness.goSearch({kind: 'slot', id: binding.destination.slot_id}, 'B');
    assert.deepEqual(harness.selected.at(-1), [id, 'HU', 'B']);
  }
});
check('All five old source slots are empty and labelled free in B', () => {
  for (const id of accepted) {
    const oldSlot = bindingsB.find(row => row.handling_unit_id === id).cargo.location.slot_id;
    assert.equal(harness.cargoAtSlot(oldSlot, 'B'), undefined);
    const entry = harness.entries().find(row => row.kind === 'slot' && row.id === oldSlot);
    assert(entry.sub.endsWith('B: свободна'));
  }
});
check('A retains the original slots and immutable source cargo objects', () => {
  for (const id of accepted) {
    const sourceCargo = bundle.fixture.inputs.initial_stock.find(row => row.handling_unit_id === id);
    const binding = harness.cargoAtSlot(sourceCargo.location.slot_id, 'A');
    assert.equal(binding.handling_unit_id, id);
    assert.strictEqual(binding.cargo, sourceCargo);
    assert.equal(harness.cargoAtSlot(bindingsB.find(row => row.handling_unit_id === id).destination.slot_id, 'A'), undefined);
  }
});
check('HU search includes the five active B destination addresses', () => {
  for (const id of accepted) {
    const destination = bindingsB.find(row => row.handling_unit_id === id).destination.slot_id;
    const entry = harness.entries().find(row => row.kind === 'HU' && row.id === id);
    assert(entry.keys.includes(destination));
    assert(harness.matches(destination).some(row => row.kind === 'HU' && row.id === id));
  }
});
const plan = await createDenseWarehouseLayoutPlan(bundle, texts);
const filled = createTwinInventory(bundle, plan);
check('A B-only filled extra and its slot select the actual B copy', () => {
  harness.structural(filled, plan); harness.rebuildSearchIndex();
  const onlyB = filled.variants.B.additions.find(row =>
    !filled.variants.A.additions.some(a => a.handling_unit_id === row.handling_unit_id));
  assert(onlyB);
  assert.equal(harness.selectionCopy(onlyB.handling_unit_id, 'A'), 'B');
  assert.strictEqual(harness.inventoryCargo(onlyB.handling_unit_id, 'B'), onlyB);
  harness.goSearch({kind: 'slot', id: onlyB.destination.slot_id}, 'A');
  assert.deepEqual(harness.selected.at(-1), [onlyB.handling_unit_id, 'HU', 'B']);
});
assert.equal(JSON.stringify(bundle), beforeBundle);
for (const [relative, expected] of pins) {
  assert.equal(hash(await readFile(path.join(frontend, relative))), expected, 'Concurrent source drift ' + relative);
}
console.log(JSON.stringify({state: 'PASS', cases: cases.length, checks: cases,
  genuine_admitted_moves: accepted.length, source_HUs: bundle.fixture.inputs.initial_stock.length,
  page_sha256: pins.get(pagePath), browser: 'NOT_RUN', backend_engine_runs: 0,
  chronology: 'Portable regression added after the independently reproduced failure and product repair'}));
