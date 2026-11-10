/* CPU component checks of the actual page functions. No browser or GPU acceptance. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'src/adaptive-v3/twin/twinPage.ts'), 'utf8');
const ast = ts.createSourceFile('twinPage.ts', source, ts.ScriptTarget.Latest, true);
const names = ['refreshInventory', 'setInventoryMode', 'inventoryCargo', 'selectionCopy', 'activeCargo', 'viewUrl', 'cargoSlot', 'cargoAtSlot'];
const functions = ast.statements.filter(n => ts.isFunctionDeclaration(n) && names.includes(n.name?.text));
assert.equal(functions.length, names.length, 'Population must be connected to the actual comparison page');
const a = {handling_unit_id: 'original', position: [1, 0, 1], cargo: {sku_id: 'SKU', location: {slot_id: 'old-slot'}}, destination: {kind: 'storage_slot', slot_id: 'old-slot'}};
const extra = {handling_unit_id: 'new-B', position: [3, 0, 4], cargo: {sku_id: 'EXTRA'}};
const relocated = {...a, position: [12, 0, 8], destination: {kind: 'storage_slot', slot_id: 'new-slot'}};
const sourceData = {variants: {A: {cargo: [a]}, B: {cargo: [a]}}};
const denseData = {variants: {A: {cargo: [a]}, B: {cargo: [a, extra]}}};
const calls = {render: 0, clear: 0, set: [], warnings: [], selection: []};
const context = vm.createContext({
  inventoryMode: 'source530', currentInventory: sourceData, phase: 'ready', layoutBusy: false,
  layoutEnabled: true, layoutCandidate: {id: 'B164'}, bundle: {id: 'source'},
  slottingBindingsB: [relocated],
  URL, location: {href: 'http://127.0.0.1/twin-v3.html'}, mode: 'side', t: 60, operationFocus: true,
  twin: {
    setInventory(data) {if (context.fail) throw Error('Rejected'); calls.set.push(data);},
    setSelected(id) {calls.selection.push(['HU', id]);},
    setSelectedActor(id) {calls.selection.push(['actor', id]);},
    setFocus(id) {calls.selection.push(['focus', id]);},
  },
  scene: {getCargoBindings: () => [a], frameState: () => null},
  createTwinInventory(bundle, plan, mode) {
    assert.equal(bundle.id, 'source'); assert.equal(plan?.id, 'B164');
    return mode === 'source530' ? sourceData : denseData;
  },
  renderInventoryControls() {calls.render++;},
  clearSelectionState() {calls.clear++;}, rebuildSearchIndex() {}, renderMoves() {}, updateLayoutControls() {},
  console: {warn(...args) {calls.warnings.push(args);}},
});
vm.runInContext(ts.transpileModule(functions.map(n => n.getText(ast)).join('\n'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText, context);
context.setInventoryMode('populated-demo-v1');
assert.equal(context.inventoryMode, 'populated-demo-v1');
assert.equal(context.currentInventory, denseData);
assert.equal(calls.clear, 1);
assert.deepEqual(calls.selection, [['HU', null], ['actor', null], ['focus', null]], 'Switching stock clears stale renderer outlines');
assert.equal(context.selectionCopy('new-B', 'A'), 'B', 'B-only cargo search must select B');
assert.equal(context.selectionCopy('original', 'A'), 'A');
assert.equal(context.inventoryCargo('new-B', 'B'), extra);
assert.equal(context.inventoryCargo('new-B', 'A'), undefined, 'No ghost cargo in A');
context.fail = true;
context.setInventoryMode('source530');
assert.equal(context.inventoryMode, 'populated-demo-v1', 'Rejected inventory restores the active mode');
assert.equal(context.currentInventory, denseData, 'Rejected inventory preserves the accepted view');
assert.equal(calls.warnings.length, 1);
context.fail = false;
context.setInventoryMode('source530');
assert.equal(context.currentInventory, sourceData);
assert.equal(context.inventoryCargo('new-B', 'B'), undefined, 'Source mode removes extras');
const applied = calls.set.length;
context.setInventoryMode('invalid');
context.phase = 'loading';
context.setInventoryMode('populated-demo-v1');
assert.equal(calls.set.length, applied, 'Invalid and premature selections cannot change the scene');
context.layoutEnabled = false;
assert.equal(context.inventoryCargo('original', 'B'), relocated, 'Legacy B selection uses accepted relocation pose and address');
assert.equal(context.inventoryCargo('original', 'A'), a, 'Legacy A keeps its original address');
assert.equal(context.cargoAtSlot('new-slot', 'B'), relocated);
assert.equal(context.cargoAtSlot('old-slot', 'B'), undefined, 'B vacated address is empty');
assert.equal(context.cargoAtSlot('old-slot', 'A'), a);
assert.equal(context.cargoSlot(relocated), 'new-slot');
assert.equal(relocated.cargo, a.cargo, 'Immutable source cargo retains its provenance');
context.phase = 'ready';
context.setInventoryMode('populated-demo-v1');
assert.equal(calls.set.length, applied, 'Legacy cargo comparison uses the common source inventory');
assert.equal(new URL(context.viewUrl()).searchParams.get('stock'), 'source', 'Shared comparison link preserves the source inventory');
console.log(JSON.stringify({passed: true, checks: 18, browser: false, component_only: true}));
