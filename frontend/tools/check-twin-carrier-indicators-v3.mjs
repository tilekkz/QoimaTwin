import assert from 'node:assert/strict';
import {mkdtemp, readFile, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';

const source = await readFile(new URL('../src/adaptive-v3/twin/twinCarrierIndicators.ts', import.meta.url), 'utf8');
const folder = await mkdtemp(path.join(tmpdir(), 'qoima-carrier-indicators-'));
const target = path.join(folder, 'indicators.mjs');
await writeFile(target, ts.transpileModule(source, {compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
}}).outputText);
const nodes = [];
const document = {createElement() {
  const node = {style: {}, dataset: {}, hidden: false, attributes: {}, removed: false,
    setAttribute(key, value) {this.attributes[key] = value;},
    remove() {this.removed = true;}};
  nodes.push(node);
  return node;
}};
const host = {ownerDocument: document, append() {}};
const {createTwinCarrierIndicators} = await import(pathToFileURL(target));
const view = createTwinCarrierIndicators(host);
const frame = {id: 'cargo-1', visible: true, payload: 'tote', position: [20, .92, 30]};
const project = point => ({x: point[0], y: point[2]});
const clip = {x: 0, y: 0, w: 100, h: 100};
view.update([frame], 3, project, clip);
assert.equal(nodes.length, 1);
assert.equal(nodes[0].hidden, false, 'Overview shows a readable symbol at the real cargo position');
assert.equal(nodes[0].style.left, '20px');
assert.equal(nodes[0].style.top, '30px');
assert.equal(nodes[0].attributes['aria-hidden'], 'true');
view.update([frame], 20, project, clip);
assert.equal(nodes[0].hidden, true, 'Close-up uses the native cargo geometry');
view.update([{...frame, payload: 'parcel', position: [40, .92, 30]}], 3, project, clip);
assert.equal(nodes.length, 1, 'A carrier changes representation without a second marker');
assert.equal(nodes[0].dataset.payload, 'parcel');
assert.equal(nodes[0].style.left, '40px');
view.update([{...frame, position: [120, .92, 30]}], 3, project, clip);
assert.equal(nodes[0].hidden, true, 'The swipe clip also clips indicators');
view.update([], 3, project, clip);
assert.equal(nodes[0].hidden, true);
assert.deepEqual(frame.position, [20, .92, 30]);
view.dispose(); view.dispose();
assert.ok(nodes.every(node => node.removed));
console.log(JSON.stringify({passed: true, checks: 6, browser: false}));
