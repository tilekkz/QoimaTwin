/** CPU regression of the current renderer helpers, extracted without rewriting their bodies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require('typescript');
const THREE = require('three');

const sourcePath = path.resolve(__dirname, '../src/adaptive-v3/twin/twinRender.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const parsed = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true);
const extracted = {};
function declaration(name, variable = false) {
  const matches = [];
  function visit(node) {
    if ((variable ? ts.isVariableDeclaration(node) : ts.isFunctionDeclaration(node)) && node.name?.getText(parsed) === name) matches.push(node);
    ts.forEachChild(node, visit);
  }
  visit(parsed);
  assert.equal(matches.length, 1, 'One actual renderer helper named ' + name);
  const node = matches[0];
  extracted[name] = {start_line: parsed.getLineAndCharacterOfPosition(node.getStart()).line + 1, end_line: parsed.getLineAndCharacterOfPosition(node.end).line + 1};
  return variable ? 'const ' + node.getText(parsed) + ';' : node.getText(parsed);
}
const helperSource = [declaration('apply'), declaration('drawMotion'), declaration('variantHead', true)].join('\n');
const wrapper = `function makeHarness(context) {
  let {applied, layout, hu, inventory, motion, t, heads} = context;
  let version = 17;
  ${helperSource}
  return {apply, drawMotion, variantHead,
    setTime(value) {t = value;}, setMotion(value) {motion = value;},
    version() {return version;}, applied() {return applied;}
  };
}`;
const compiled = ts.transpileModule(wrapper, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None}}).outputText;
const makeHarness = new Function('THREE', compiled + '\nreturn makeHarness;')(THREE);
const cases = [];
function check(name, run) {run(); cases.push(name);}

check('same variant advances motion and inventory with static version retained', () => {
  const calls = [];
  const harness = makeHarness({applied: null, t: 0, hu: [], heads: new Map(), layout: {apply: v => calls.push(['layout', v])}, inventory: {apply: v => calls.push(['inventory', v])}, motion: {apply: (v, t) => calls.push(['motion', v, t])}});
  harness.apply('A'); harness.setTime(12.5); harness.apply('A');
  assert.deepEqual(calls, [['layout', 'A'], ['inventory', 'A'], ['motion', 'A', 0], ['inventory', 'A'], ['motion', 'A', 12.5]]);
  assert.equal(harness.version(), 17);
});
check('every A B A pass applies its inventory and motion after its layout', () => {
  const calls = [];
  const harness = makeHarness({applied: 'A', t: 32, hu: [], heads: new Map(), layout: {apply: v => calls.push(['layout', v])}, inventory: {apply: v => calls.push(['inventory', v])}, motion: {apply: (v, t) => calls.push(['motion', v, t])}});
  harness.apply('B'); harness.apply('A'); harness.apply('A');
  assert.deepEqual(calls, [['layout', 'B'], ['inventory', 'B'], ['motion', 'B', 32], ['layout', 'A'], ['inventory', 'A'], ['motion', 'A', 32], ['inventory', 'A'], ['motion', 'A', 32]]);
});
check('source cargo buffers still swap when the layout adapter is absent', () => {
  const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial(), 1);
  const row = {mesh, pos: {A: new THREE.Vector3(1, 0, 2), B: new THREE.Vector3(9, 0, 8)}, arr: {A: new Float32Array(16), B: new Float32Array(16)}, attr: {}};
  const harness = makeHarness({applied: null, t: 0, hu: [row], heads: new Map()});
  harness.apply('B'); assert(mesh.position.equals(row.pos.B)); assert.equal(mesh.instanceMatrix.array, row.arr.B);
  harness.apply('A'); assert(mesh.position.equals(row.pos.A)); assert.equal(mesh.instanceMatrix.array, row.arr.A);
  mesh.geometry.dispose(); mesh.material.dispose(); mesh.dispose();
});
check('moving head uses current variant and time without adding the static layout delta', () => {
  const calls = [];
  const harness = makeHarness({t: 20, heads: new Map([['S02', new THREE.Vector3(1, 2, 3)]]), layout: {actorDelta: () => new THREE.Vector3(100, 0, 100)}, motion: {actorPosition: (v, t, id) => {calls.push([v, t, id]); return [t, 2.3, v === 'A' ? 10 : 11];}}});
  assert.deepEqual(harness.variantHead('S02', 'B').toArray(), [20, 2.3, 11]);
  harness.setTime(45); assert.deepEqual(harness.variantHead('S02', 'A').toArray(), [45, 2.3, 10]);
  assert.deepEqual(calls, [['B', 20, 'S02'], ['A', 45, 'S02']]);
});
check('unmoved heads retain B layout offsets and immutable original points', () => {
  const original = new THREE.Vector3(1, 2, 3);
  const harness = makeHarness({t: 0, heads: new Map([['P01', original]]), layout: {actorDelta: () => new THREE.Vector3(10, 0, 20)}, motion: {actorPosition: () => undefined}});
  assert.deepEqual(harness.variantHead('P01', 'A').toArray(), [1, 2, 3]);
  assert.deepEqual(harness.variantHead('P01', 'B').toArray(), [11, 2, 23]);
  assert.deepEqual(original.toArray(), [1, 2, 3]); assert.equal(harness.variantHead('missing', 'A'), undefined);
});
check('dynamic draw selects layer one and updates world matrices before rendering', () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(), node = new THREE.Object3D();
  const background = new THREE.Color('#abcdef'); scene.background = background; scene.add(node);
  scene.updateMatrixWorld(true); scene.matrixWorldAutoUpdate = false;
  node.position.set(7, 11, 13); camera.layers.enable(3);
  const mask = camera.layers.mask, harness = makeHarness({motion: {}, heads: new Map()}), calls = [];
  const renderer = {render(actualScene, actualCamera) {
    calls.push('render'); assert.equal(actualScene, scene); assert.equal(actualCamera, camera);
    assert.equal(scene.background, null); assert.equal(camera.layers.mask, 2);
    assert.deepEqual(new THREE.Vector3().setFromMatrixPosition(node.matrixWorld).toArray(), [7, 11, 13]);
  }};
  harness.drawMotion(renderer, scene, camera);
  assert.deepEqual(calls, ['render']); assert.equal(scene.background, background); assert.equal(camera.layers.mask, mask);
});
check('dynamic draw restores camera mask and background when rendering throws', () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(), node = new THREE.Object3D();
  const background = new THREE.Color('#123456'); scene.background = background; scene.add(node);
  scene.updateMatrixWorld(true); node.position.set(3, 4, 5); camera.layers.enable(4);
  const mask = camera.layers.mask, error = Error('owned renderer failure'), harness = makeHarness({motion: {}, heads: new Map()});
  assert.throws(() => harness.drawMotion({render() {
    assert.equal(camera.layers.mask, 2); assert.equal(scene.background, null);
    assert.deepEqual(new THREE.Vector3().setFromMatrixPosition(node.matrixWorld).toArray(), [3, 4, 5]);
    throw error;
  }}, scene, camera), value => value === error);
  assert.equal(scene.background, background); assert.equal(camera.layers.mask, mask);
});
check('absent motion performs no dynamic render or camera state change', () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(), background = new THREE.Color('#777777');
  scene.background = background; camera.layers.enable(2);
  const mask = camera.layers.mask, harness = makeHarness({heads: new Map()});
  harness.drawMotion({render() {throw Error('Unexpected renderer call');}}, scene, camera);
  assert.equal(scene.background, background); assert.equal(camera.layers.mask, mask);
});
console.log(JSON.stringify({state: 'PASS', cases: cases.length, checks: cases, source: 'frontend/src/adaptive-v3/twin/twinRender.ts', source_sha256: crypto.createHash('sha256').update(source).digest('hex'), extracted, three_revision: THREE.REVISION, browser: 'NOT_RUN', chronology: 'Regression written after renderer implementation'}));
