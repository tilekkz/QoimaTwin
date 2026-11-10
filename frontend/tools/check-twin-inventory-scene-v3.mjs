import assert from 'node:assert/strict';
import {readFile, writeFile, mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import * as THREE from 'three';
import ts from 'typescript';

const directory = await mkdtemp(join(tmpdir(), 'qoima-inventory-scene-'));
const source = await readFile(resolve('src/adaptive-v3/twin/twinInventoryScene.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
}}).outputText.replace(/from ['"]three['"]/g, `from '${import.meta.resolve('three')}'`);
const modulePath = join(directory, 'inventory-scene.mjs');
await writeFile(modulePath, compiled);
const {createTwinInventoryScene} = await import(pathToFileURL(modulePath));
const scene = new THREE.Scene();
const geometry = new THREE.BoxGeometry(1, 1, 1);
const material = new THREE.MeshBasicMaterial();
const original = new THREE.InstancedMesh(geometry, material, 1);
original.userData = {semanticKind: 'HU', semanticIds: ['original']};
original.position.set(2, 0, 0);
original.setMatrixAt(0, new THREE.Matrix4().makeTranslation(3, .5, 0));
scene.add(original);
const sourceCargo = [{handling_unit_id: 'original', position: [5, 0, 0], yaw_rad: 0}];
const row = (id, x, prototype = 'original') => ({handling_unit_id: id,
  prototype_hu_id: prototype, position: [x, 0, 0], yaw_rad: 0,
  cargo: {dimensions_xyz_m: [1, 1, 1]}, origin: 'populated-demo'});
const inventory = {mode: 'populated-demo-v1', variants: {
  A: {additions: [row('extra-a', 10)]}, B: {additions: [row('extra-b1', 20), row('extra-b2', 30)]},
}};
const before = Array.from(original.instanceMatrix.array);
let sharedGeometryDisposed = 0;
geometry.addEventListener('dispose', () => sharedGeometryDisposed++);
const layer = createTwinInventoryScene(scene, sourceCargo);
layer.setInventory(inventory);
layer.apply('A');
const visibleExtra = () => {
  const result = [];
  scene.updateMatrixWorld(true);
  scene.traverseVisible(node => {
    if (node.userData.semanticKind !== 'demo-stock') return;
    for (let i = 0; i < node.count; i++) {
      const matrix = new THREE.Matrix4();
      node.getMatrixAt(i, matrix);
      result.push({id: node.userData.semanticIds[i],
        position: new THREE.Vector3().setFromMatrixPosition(node.matrixWorld.clone().multiply(matrix)).toArray()});
    }
  });
  return result;
};
assert.deepEqual(visibleExtra(), [{id: 'extra-a', position: [10, .5, 0]}]);
layer.apply('B');
assert.deepEqual(visibleExtra(), [
  {id: 'extra-b1', position: [20, .5, 0]}, {id: 'extra-b2', position: [30, .5, 0]},
]);
layer.apply('A');
assert.deepEqual(visibleExtra(), [{id: 'extra-a', position: [10, .5, 0]}]);
assert.deepEqual(Array.from(original.instanceMatrix.array), before);
assert.equal(layer.bounds('extra-b1', 'B').position[0], 20);
assert.equal(layer.bounds('extra-b1', 'A'), null);
assert.throws(() => layer.setInventory({variants: {
  A: {additions: [row('invalid', 0, 'unknown')]}, B: {additions: []},
}}), /prototype/i);
assert.deepEqual(visibleExtra(), [{id: 'extra-a', position: [10, .5, 0]}]);
layer.dispose(); layer.dispose();
assert.deepEqual(visibleExtra(), []);
assert.equal(sharedGeometryDisposed, 0);
assert.deepEqual(Array.from(original.instanceMatrix.array), before);
assert.equal(scene.children.length, 1);
console.log(JSON.stringify({passed: true, checks: 10, browser: false}));
