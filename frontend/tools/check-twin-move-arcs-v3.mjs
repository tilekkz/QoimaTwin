import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import ts from 'typescript';
import * as THREE from 'three';

const source = await readFile(new URL('../src/adaptive-v3/twin/twinRender.ts', import.meta.url), 'utf8');
const ast = ts.createSourceFile('twinRender.ts', source, ts.ScriptTarget.Latest, true);
const helpers = [];
function find(node) {
  if (ts.isFunctionDeclaration(node) && ['setMoves', 'clearMoveArcs'].includes(node.name?.text)) helpers.push(node.getText(ast));
  ts.forEachChild(node, find);
}
find(ast);
const owned = [], unitBox = new THREE.BoxGeometry(), unitEdges = new THREE.EdgesGeometry(unitBox);
const material = new THREE.LineBasicMaterial(), arcGroup = new THREE.Group();
let sharedDisposals = 0, arcDisposals = 0, createdArcs = 0;
for (const item of [unitBox, unitEdges, material]) item.addEventListener('dispose', () => sharedDisposals++);
const context = vm.createContext({THREE, moves: [], owned, arcGroup,
  wasGroup: new THREE.Group(), newGroup: new THREE.Group(), unitBox, unitEdges,
  wasMat: material, newFill: new THREE.MeshBasicMaterial(), newEdge: material, arcMat: material,
  place() {}, own(item) {owned.push(item); return item;}, pins: {A: [], B: []},
  layers: {A: {append() {}}, B: {append() {}}},
  document: {createElement: () => ({dataset: {}, setAttribute() {}, addEventListener() {}, remove() {}})},
});
vm.runInContext(ts.transpileModule(helpers.join('\n'), {compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
}}).outputText, context);
const pose = position => ({position, dims: [1, 1, 1], yaw: 0});
const moves = [1, 2].map(id => ({id: String(id), sku: 'SKU', a: pose([id, 0, 0]), b: pose([id, 0, 5])}));
for (let cycle = 0; cycle < 40; cycle++) {
  context.setMoves(moves, () => {});
  assert.equal(arcGroup.children.length, 2);
  for (const line of arcGroup.children) {
    createdArcs++;
    line.geometry.addEventListener('dispose', () => arcDisposals++);
  }
  context.setMoves([], () => {});
  assert.equal(arcDisposals, createdArcs, 'Replacing moves releases every outgoing curve geometry');
  assert.equal(arcGroup.children.length, 0);
}
assert.equal(sharedDisposals, 0, 'Shared box/edge/material assets survive move updates');
assert.ok(owned.length <= 2, 'Cleared curve geometry does not accumulate in session ownership');
console.log(JSON.stringify({passed: true, cycles: 40, created_arcs: createdArcs, disposed_arcs: arcDisposals, browser: false}));
