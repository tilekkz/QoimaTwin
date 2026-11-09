/** Actual source geometry, Three CPU scene and native samplers. No browser/server. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL, fileURLToPath} from 'node:url';
import ts from 'typescript';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const front = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cache = await fs.mkdtemp(path.join(tmpdir(), 'qoima-twin-warehouse-motion-'));
const compiled = new Map();
async function compile(relative) {
  if (compiled.has(relative)) return compiled.get(relative);
  const output = path.join(cache, relative + '.mjs');
  compiled.set(relative, output);
  let code = ts.transpileModule(await fs.readFile(path.join(front, relative), 'utf8'), {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}}).outputText;
  for (const match of [...code.matchAll(/import\s+(\w+)\s+from\s+['"]([^'"]+\.json)['"];?/g)]) {
    const json = await fs.readFile(path.resolve(front, path.dirname(relative), match[2]), 'utf8');
    code = code.replace(match[0], 'const ' + match[1] + '=' + json + ';');
  }
  for (const match of [...code.matchAll(/from ['"](\.[^'"]+)['"]/g)]) {
    const dependency = path.posix.normalize(path.posix.join(path.posix.dirname(relative), match[1] + '.ts'));
    code = code.replace(match[0], 'from ' + JSON.stringify(pathToFileURL(await compile(dependency)).href));
  }
  code = code.replace(/from ['"](three(?:\/[^'"]+)?)['"]/g, (_, id) => 'from ' + JSON.stringify(pathToFileURL(path.join(front, 'node_modules', id === 'three' ? 'three/build/three.module.js' : id)).href));
  code = code.replaceAll('import.meta.env.BASE_URL', "'/'");
  await fs.mkdir(path.dirname(output), {recursive: true});
  await fs.writeFile(output, code);
  return output;
}
const load = async name => import(pathToFileURL(await compile('src/adaptive-v3/' + name + '.ts')));
const loaded = [];
for (const name of ['warehouseAdapter', 'warehouseCargo', 'workerRoles', 'seatedDriver', 'twin/twinWarehouseMotion']) loaded.push(await load(name));
const [{adaptWarehouseV3}, {createWarehouseCargo}, {createWorkerInstance}, {bindSeatedDriver, validateSeatedDriverPose}, {createTwinWarehouseMotion}] = loaded;
const sources = {fixture: '/data/v3/warehouse-fixture-v3.json', layout: '/data/adaptive-v3/layout-manifest.json', registry: '/data/v3/worker-registry-v3.json', profiles: '/data/v3/worker-profiles-v3.json'};
const texts = Object.fromEntries(await Promise.all(Object.entries(sources).map(async ([key, name]) => [key, await fs.readFile(path.join(front, 'public' + name), 'utf8')])));
const bundle = await adaptWarehouseV3(texts);
const models = new Map();
for (const name of ['worker-base', 'forklift', 'pallet-load', 'heavy-bay', 'small-carton']) {
  const bytes = await fs.readFile(path.join(front, 'public/models/v3/' + name + '.glb'));
  const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
  models.set(name, gltf.scene);
}
const pose = (p, yaw) => new THREE.Matrix4().compose(new THREE.Vector3(...p), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw), new THREE.Vector3(1, 1, 1));
function prototype(scene, template, kind, id, position, yaw) {
  template.updateMatrixWorld(true);
  template.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return;
    const mesh = new THREE.InstancedMesh(node.geometry, node.material, 1);
    mesh.userData = {semanticKind: kind, semanticIds: [id]};
    mesh.setMatrixAt(0, pose(position, yaw).multiply(node.matrixWorld));
    scene.add(mesh);
  });
}
async function sceneFixture() {
  const scene = new THREE.Scene(), actors = new Map(), vehicles = new Map();
  const driverPose = validateSeatedDriverPose(JSON.parse(await fs.readFile(path.join(front, 'public/data/v3/seated-driver-pose.json'), 'utf8')));
  for (const [id, nodeId] of [['FL01', 'v3:service:IN_W_BULK'], ['FL02', 'v3:service:OUT_E_B2B']]) {
    const node = bundle.layout.vehicle.nodes.find(n => n.node_id === nodeId), root = models.get('forklift').clone(true);
    root.name = 'vehicle__' + id; root.position.fromArray(node.world_pos); root.rotation.y = node.yaw_rad;
    scene.add(root); vehicles.set(id, root);
  }
  for (const worker of bundle.registry.workers) {
    const instance = createWorkerInstance(models.get('worker-base'), worker.actor_id, worker.baseline_role);
    instance.root.userData.semanticKind = 'actor'; instance.root.userData.semanticId = worker.actor_id;
    actors.set(worker.actor_id, instance.root);
    if (worker.assigned_vehicle_id) bindSeatedDriver(vehicles.get(worker.assigned_vehicle_id), instance, driverPose);
    else {instance.root.position.set(70 + actors.size, 0, 1); scene.add(instance.root);}
  }
  actors.get('S02').position.fromArray(bundle.layout.walk.nodes.find(n => n.node_id === 'v3:service:OUT_S_EXPRESS').world_pos);
  const stock = createWarehouseCargo(bundle).snapshot();
  for (const [archetype, model] of [['PALLET_LOAD', 'pallet-load'], ['SMALL_CARTON', 'small-carton']]) {
    const hu = stock.find(h => h.cargo.archetype_id === archetype);
    prototype(scene, models.get(model), 'HU', hu.handling_unit_id, hu.position, hu.yaw_rad);
  }
  const module = bundle.layout.modules.find(m => m.family === 'HEAVY');
  prototype(scene, models.get('heavy-bay'), 'module', module.module_id, module.world_pos, module.yaw_rad);
  scene.updateMatrixWorld(true);
  return {scene, actors, vehicles};
}
const originalFetch = globalThis.fetch;
globalThis.fetch = async (url, options) => {
  options?.signal?.throwIfAborted();
  const name = new URL(String(url), 'http://local/').pathname;
  assert(['/data/v3/heavy-inbound-fixture.json', '/data/v3/route-policy-v3.json'].includes(name), name);
  return new Response(await fs.readFile(path.join(front, 'public' + name)), {status: 200});
};
const local = node => [node.parent?.uuid, node.position.toArray(), node.quaternion.toArray(), node.scale.toArray(), node.layers.mask];
const carrierStarts = [-128, -64, 0, 64, 128, 192];
function checkBeltCoverage(motion) {
  const conveyor = bundle.layout.data.conveyor;
  const clearance = Math.hypot(.6, .4) + conveyor.source_assumptions.payload_clearance_m;
  // Between quarter-second samples, two source-speed carriers can close by .1375m.
  const continuousMargin = conveyor.source_assumptions.speed_m_s * .25;
  for (const variant of ['A', 'B']) {
    let previous;
    for (let tick = 0; tick <= 960; tick++) {
      motion.apply(variant, tick / 4);
      const frames = motion.snapshot().belt, visible = frames.filter(frame => frame.visible);
      assert(visible.length >= 2, `${variant} has insufficient goods at ${tick / 4}s`);
      assert(visible.some(frame => frame.phase === 'travel'), `${variant} has no moving goods at ${tick / 4}s`);
      for (let i = 0; i < visible.length; i++) for (let j = i + 1; j < visible.length; j++) {
        const distance = new THREE.Vector3(...visible[i].position).distanceTo(new THREE.Vector3(...visible[j].position));
        assert(distance > clearance + continuousMargin, `Continuous carrier clearance ${variant}/${tick / 4}`);
      }
      for (const frame of visible) {
        const old = previous?.find(row => row.id === frame.id && row.visible);
        if (old) assert(new THREE.Vector3(...frame.position).distanceTo(new THREE.Vector3(...old.position)) <= .55 / 4 + 1e-8);
      }
      previous = frames;
    }
    const held = motion.snapshot(); motion.apply(variant, 240); assert.deepEqual(motion.snapshot(), held);
  }
}
function localBounds(object, parent) {
  const bounds = new THREE.Box3(), inverse = parent.matrixWorld.clone().invert();
  object.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return;
    node.geometry.computeBoundingBox();
    bounds.union(node.geometry.boundingBox.clone().applyMatrix4(inverse.clone().multiply(node.matrixWorld)));
  });
  return bounds;
}
function checkToteContents(motion, scene) {
  motion.apply('A', 0);
  const root = scene.getObjectByName('twin_visual_belt_motion');
  for (const carrier of root.children) {
    const tote = carrier.children[0], goods = tote.getObjectByName('twin_visual_tote_goods');
    assert(goods, 'Every tote contains an unscaled native SMALL_CARTON');
    assert.deepEqual(goods.scale.toArray(), [1, 1, 1]);
    const box = localBounds(goods, tote), dimensions = box.getSize(new THREE.Vector3());
    assert(dimensions.distanceTo(new THREE.Vector3(.32, .24, .24)) < 1e-6);
    assert(Math.abs(box.min.y - .012) < 1e-6);
    assert(box.min.x >= -.288 && box.max.x <= .288 && box.min.z >= -.188 && box.max.z <= .188 && box.max.y <= .3);
  }
  assert.equal(root.children.length, carrierStarts.length);
}
function sourcePath(from, to) {
  const edges = bundle.layout.data.conveyor.edges, queue = [[from, []]], seen = new Set([from]);
  for (const [node, path] of queue) {
    if (node === to) return path;
    for (const edge of edges.filter(row => row.from_node_id === node)) if (!seen.has(edge.to_node_id)) {
      seen.add(edge.to_node_id); queue.push([edge.to_node_id, [...path, edge]]);
    }
  }
  throw Error('Disconnected source test path');
}
function sourceBeltSteps(variant) {
  const station = variant === 'A' ? 'PK03' : 'PK05', steps = [];
  let at = 0;
  const append = (edge, duration, phase) => {steps.push({edge, start: at, end: at + duration, phase}); at += duration;};
  const path = (from, to) => {
    for (const edge of sourcePath(from, to)) {
      if (edge.turn_timing === 'before_edge') append(edge, .8, 'pivot');
      append(edge, edge.length_m / .55, 'travel');
      if (edge.turn_timing === 'after_edge') append(edge, .8, 'pivot');
    }
  };
  path('v3:conv:intake', 'v3:conv:' + station + ':WORK');
  append(steps.at(-1).edge, variant === 'A' ? 42 : 12, 'packing_wait');
  path('v3:conv:' + station + ':WORK', 'v3:conv:output');
  return steps;
}
function checkSourceBeltEdges(motion) {
  const source = bundle.layout.data.conveyor, nodes = new Map(source.nodes.map(node => [node.node_id, node.world_pos]));
  for (const variant of ['A', 'B']) for (const step of sourceBeltSteps(variant)) {
    for (const [index, start] of carrierStarts.entries()) {
      const middle = start + (step.start + step.end) / 2;
      if (middle < 0 || middle > 240) continue;
      motion.apply(variant, middle);
      const frame = motion.snapshot().belt[index];
      assert.equal(frame.source_edge_id, step.edge.edge_id); assert.equal(frame.phase, step.phase);
      if (step.phase === 'travel') {
        const edge = step.edge, a = nodes.get(edge.from_node_id), b = nodes.get(edge.to_node_id);
        const expected = edge.path_kind === 'arc'
          ? [edge.centre[0] + edge.radius_m * Math.cos((edge.theta_start_rad + edge.theta_end_rad) / 2), edge.centre[1], edge.centre[2] + edge.radius_m * Math.sin((edge.theta_start_rad + edge.theta_end_rad) / 2)]
          : a.map((value, axis) => (value + b[axis]) / 2);
        assert(new THREE.Vector3(...frame.position).distanceTo(new THREE.Vector3(...expected)) < 1e-8);
      }
      for (const boundary of [start + step.start, start + step.end]) {
        if (boundary <= .00001 || boundary >= 239.99999) continue;
        motion.apply(variant, boundary - .00001); const before = motion.snapshot().belt[index];
        motion.apply(variant, boundary + .00001); const after = motion.snapshot().belt[index];
        if (before.visible && after.visible) assert(new THREE.Vector3(...before.position).distanceTo(new THREE.Vector3(...after.position)) <= .55 * .00002 + 1e-8);
      }
    }
  }
}
function checkCarrierQuery(motion) {
  motion.apply('A', 90);
  const current = motion.snapshot(), poses = new Map();
  for (const root of motion.dynamicObjects()) root.traverse(node => poses.set(node, local(node)));
  const frames = motion.carrierFrames('B', 60), expected = structuredClone(frames);
  assert.equal(frames.length, carrierStarts.length);
  assert(frames.some(frame => frame.visible && frame.phase === 'packing_wait'));
  frames[0].position[0] = -1000; frames[1].visible = !frames[1].visible; frames.pop();
  assert.deepEqual(motion.carrierFrames('B', 60), expected);
  assert.deepEqual(motion.snapshot(), current);
  for (const [node, pose] of poses) assert.deepEqual(local(node), pose);
  for (const time of [-1, 241, NaN, Infinity]) assert.throws(() => motion.carrierFrames('A', time));
  assert.throws(() => motion.carrierFrames('unsupported', 10));
  assert.deepEqual(motion.snapshot(), current);
}
const fixture = await sceneFixture(), before = new Map();
fixture.vehicles.get('FL01').layers.enable(2);
fixture.actors.get('S02').layers.enable(3);
fixture.scene.traverse(node => before.set(node, local(node)));
const buffers = new Map(); fixture.scene.traverse(node => {if (node instanceof THREE.InstancedMesh) buffers.set(node, [...node.instanceMatrix.array]);});
let motion;
try {
  motion = await createTwinWarehouseMotion(fixture.scene, bundle, texts, new AbortController().signal);
  let checks = 0;
  const coverageFailures = [];
  for (const check of [() => checkBeltCoverage(motion), () => checkToteContents(motion, fixture.scene), () => checkSourceBeltEdges(motion), () => checkCarrierQuery(motion)]) {
    try {check(); checks++;} catch (error) {coverageFailures.push(error);}
  }
  if (coverageFailures.length) throw new AggregateError(coverageFailures, 'Normal main comparison goods coverage');
  assert.equal(motion.snapshot().source_kind, 'visual_fixture'); checks++;
  assert(motion.dynamicObjects().includes(fixture.vehicles.get('FL01')));
  assert(motion.dynamicObjects().includes(fixture.actors.get('S02'))); checks++;
  for (const root of motion.dynamicObjects()) root.traverse(node => assert.equal(node.layers.mask, 2)); checks++;
  motion.apply('A', 60.224481402050685 - .000001); assert.equal(motion.snapshot().heavy.attached, false);
  motion.apply('A', 60.224481402050685); assert.equal(motion.snapshot().heavy.attached, true); checks++;
  motion.apply('A', 90); const first = motion.snapshot(), position = fixture.vehicles.get('FL01').position.toArray();
  assert(first.heavy.attached); assert.equal(first.heavy.incoming_HU_id, 'v3:HU:W11:external:01'); checks++;
  assert(first.heavy.maximum_frame_position_error_m <= .000002);
  assert(first.heavy.frame_orientation_residual <= .000002);
  assert.equal(first.heavy.same_existing_driver, true); assert.equal(first.heavy.driver_local_pose_unchanged, true); checks++;
  motion.apply('B', 150); assert.notDeepEqual(fixture.vehicles.get('FL01').position.toArray(), position); checks++;
  motion.apply('A', 90); assert.deepEqual(motion.snapshot(), first); checks++;
  motion.apply('A', 240); assert.equal(motion.snapshot().heavy_visual_complete, false); assert(motion.snapshot().heavy.attached); checks++;
  motion.apply('B', 0); assert(!motion.snapshot().heavy.attached); checks++;
  const atStart = motion.actorPosition('A', 0, 'S02'), moving = motion.actorPosition('A', 20, 'S02');
  assert.notDeepEqual(atStart, moving); assert.deepEqual(motion.actorPosition('B', 20, 'S02'), moving); checks++;
  assert(moving[1] > 1.5); assert(motion.actorPosition('A', 20, 'F01')[1] > 1.5);
  assert.equal(motion.actorPosition('B', 20, 'P01'), undefined); checks++;
  const picker = fixture.actors.get('P01'); picker.position.add(new THREE.Vector3(7, 0, 12));
  const bHome = local(picker); motion.apply('B', 130); assert.deepEqual(local(picker), bHome);
  picker.position.fromArray(before.get(picker)[1]); checks++;
  const samples = Array.from({length: 241}, (_, t) => {motion.apply('A', t); return motion.snapshot().belt;});
  assert(samples.some(rows => rows.some(row => row.visible && row.payload === 'tote')));
  assert(samples.some(rows => rows.some(row => row.visible && row.payload === 'parcel')));
  assert(samples.some(rows => rows.some(row => row.phase === 'packing_wait'))); checks++;
  const stable = motion.snapshot(); for (const t of [-1, 241, NaN, Infinity]) assert.throws(() => motion.apply('A', t));
  assert.deepEqual(motion.snapshot(), stable); checks++;
  assert.throws(() => motion.apply('unsupported', 20)); assert.deepEqual(motion.snapshot(), stable); checks++;
  for (const [node, matrix] of buffers) assert.deepEqual([...node.instanceMatrix.array], matrix); checks++;
  for (const [id, node] of fixture.actors) if (!['F01', 'S02'].includes(id)) {const expected = before.get(node); assert.deepEqual(local(node), expected, id);}
  checks++;
  motion.dispose(); motion.dispose();
  for (const [node, expected] of before) assert.deepEqual(local(node), expected, node.name);
  assert(!fixture.scene.getObjectByName('twin_visual_belt_motion')); checks++;
  assert.throws(() => motion.apply('A', 0), /disposed/i); checks++;
  assert.throws(() => motion.carrierFrames('A', 0), /disposed/i);
  const aborted = new AbortController(); aborted.abort();
  await assert.rejects(() => createTwinWarehouseMotion(fixture.scene, bundle, texts, aborted.signal)); checks++;
  const mockedFetch = globalThis.fetch, duringFetch = new AbortController();
  globalThis.fetch = async (...args) => {const response = await mockedFetch(...args); duringFetch.abort(); return response;};
  await assert.rejects(() => createTwinWarehouseMotion(fixture.scene, bundle, texts, duringFetch.signal));
  globalThis.fetch = mockedFetch;
  for (const [node, expected] of before) assert.deepEqual(local(node), expected, node.name); checks++;
  const prototypeId = createWarehouseCargo(bundle).snapshot().find(h => h.cargo.archetype_id === 'SMALL_CARTON').handling_unit_id;
  const removed = fixture.scene.children.filter(node => node instanceof THREE.InstancedMesh && node.userData.semanticIds?.includes(prototypeId));
  for (const node of removed) node.removeFromParent();
  await assert.rejects(() => createTwinWarehouseMotion(fixture.scene, bundle, texts, new AbortController().signal), /parcel/i);
  assert(!fixture.scene.getObjectByName('heavy_inbound_display_fixture'));
  assert(!fixture.scene.getObjectByName('twin_visual_belt_motion'));
  for (const node of removed) fixture.scene.add(node);
  for (const [node, expected] of before) assert.deepEqual(local(node), expected, node.name); checks++;
  const retry = await createTwinWarehouseMotion(fixture.scene, bundle, texts, new AbortController().signal);
  retry.apply('B', 90); retry.dispose();
  for (const [node, expected] of before) assert.deepEqual(local(node), expected, node.name); checks++;
  console.log(JSON.stringify({state: 'PASS', checks, actual_source_models: models.size, browser: 'NOT_RUN', backend_engine_runs: 0}));
} finally {motion?.dispose(); globalThis.fetch = originalFetch;}
