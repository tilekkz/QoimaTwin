// Independent W05.3.2 CPU probe. Reads frozen sources; writes only beside this file.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const output = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(output, '../../../..');
const loadJson = async p => JSON.parse((await readFile(path.join(repo, p), 'utf8')).replace(/^\uFEFF/, ''));
const T = await import(pathToFileURL(path.join(repo, 'frontend/node_modules/three/build/three.module.js')));
const { GLTFLoader } = await import(pathToFileURL(path.join(repo, 'frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js')));
const solverPath = 'frontend/tools/solve-worker-base-carry-v3.mjs';
const solver = await readFile(path.join(repo, solverPath), 'utf8');
const pose = await loadJson('frontend/public/data/v3/worker-base-carry-pose.json');
const report = await loadJson('docs/adaptive-v3/evidence/W05.3.1-checks.json');
const spec = await loadJson('assets/v3/specs/worker-base.dimensions.json');
const stats = await loadJson('assets/v3/blender/worker-base.stats.json');
async function load(id) {
  const b = await readFile(path.join(repo, `frontend/public/models/v3/${id}.glb`));
  return (await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), '')).scene;
}
const workerScene = await load('worker-base');
const worker = workerScene.getObjectByName('worker_base_root');
const cargo = await load('small-carton');
const world = new T.Group(); world.add(worker, cargo);
world.updateMatrixWorld(true);
const nativeRestMatrices = new Map();
worker.traverse(n => { if (n.isMesh) nativeRestMatrices.set(n.name, n.matrixWorld.clone()); });
for (const [name, angles] of Object.entries(pose.jointEulerXYZ)) worker.getObjectByName(name).rotation.set(...angles, 'XYZ');
cargo.position.fromArray(pose.cargo.position_m); world.updateMatrixWorld(true);

// Extract the exact validator with its real GLTF joint-limit metadata; do not rewrite it.
const predicateLines = solver.split(/\r?\n/).filter(line => /^const (finite|exactKeys)=/.test(line)).join('\n');
const validatorLine = solver.split(/\r?\n/).find(line => line.trimStart().startsWith('function validatePose('));
assert(validatorLine && predicateLines);
const names = ['upper_arm', 'forearm', 'palm_roll', 'hand'];
const validate = new Function('assert', 'worker', 'inputs', 'original', 'names', 'cargoPosition',
  `${predicateLines}\n${validatorLine}\nreturn validatePose;`)(assert, worker, pose.source_hashes,
  report.population_guard.example_original_assignment, names, pose.cargo.position_m);
const request = Object.fromEntries(['actor_id', 'worker_asset', 'worker_root', 'cargo', 'jointEulerXYZ', 'source_hashes'].map(k => [k, structuredClone(pose[k])]));
validate(request);
const validation = [];
function attempt(label, change, expected) {
  const p = structuredClone(request); change(p);
  let accepted = true, error = null;
  try { validate(p); } catch (e) { accepted = false; error = e.code ?? e.name; }
  const row = { label, accepted, expected, matches_expectation: accepted === expected, error };
  validation.push(row); return { row, request: p };
}
for (const value of [true, false, '0', NaN, Infinity, -Infinity, null, undefined])
  attempt(`primitive_${String(value)}`, p => p.jointEulerXYZ.joint__upper_arm_L[0] = value, false);
attempt('two_axes', p => p.jointEulerXYZ.joint__upper_arm_L.pop(), false);
attempt('four_axes', p => p.jointEulerXYZ.joint__upper_arm_L.push(0), false);
attempt('palm_forbidden_X', p => p.jointEulerXYZ.joint__palm_roll_L[0] = .001, false);
attempt('palm_forbidden_Z', p => p.jointEulerXYZ.joint__palm_roll_L[2] = .001, false);
attempt('extra_joint', p => p.jointEulerXYZ.joint__elbow_swivel_L = [0, 0, 0], false);
attempt('omitted_joint', p => delete p.jointEulerXYZ.joint__hand_R, false);
const sparse = attempt('deleted_axis_leaves_sparse_length3', p => delete p.jointEulerXYZ.joint__upper_arm_L[1], false);
const allSparse = attempt('three_omitted_axes_sparse_length3', p => p.jointEulerXYZ.joint__upper_arm_L = new Array(3), false);
const angles = sparse.request.jointEulerXYZ.joint__upper_arm_L;
const applied = new T.Euler(...angles, 'XYZ');
const serializedSparse = structuredClone(sparse.request);
serializedSparse.jointEulerXYZ.joint__upper_arm_L = JSON.parse(JSON.stringify(angles));
let jsonSparseRejected = false;
try { validate(serializedSparse); } catch { jsonSparseRejected = true; }

// Independent native triangle reconstruction, without solver geometry/contact helpers.
function triangles(mesh) {
  mesh.updateWorldMatrix(true, false);
  const p = mesh.geometry.attributes.position, ix = mesh.geometry.index;
  return Array.from({ length: (ix?.count ?? p.count) / 3 }, (_, i) => new T.Triangle(...[0, 1, 2].map(j =>
    new T.Vector3().fromBufferAttribute(p, ix ? ix.getX(3 * i + j) : 3 * i + j).applyMatrix4(mesh.matrixWorld))));
}
const cargoMeshes = []; cargo.traverse(n => { if (n.isMesh) cargoMeshes.push(n); });
function nearest(point, meshes) {
  let best = { distance_m: Infinity };
  for (const mesh of meshes) for (const [index, tri] of triangles(mesh).entries()) {
    const p = tri.closestPointToPoint(point, new T.Vector3()), d = p.distanceTo(point);
    if (d < best.distance_m) best = { distance_m: d, mesh: mesh.name, triangle: index, point_m: p.toArray() };
  }
  return best;
}
const contacts = pose.solved_reference_points.map(r => {
  const hand = worker.getObjectByName(`joint__hand_${r.side}`), point = hand.localToWorld(new T.Vector3(...r.local_hand_m));
  return { side: r.side, point_m: point.toArray(), horizontal_radius_m: Math.hypot(point.x, point.z), native_cargo_nearest: nearest(point, cargoMeshes) };
});
cargo.position.x += 20e-6; world.updateMatrixWorld(true);
const movedGaps = pose.solved_reference_points.map(r => nearest(worker.getObjectByName(`joint__hand_${r.side}`).localToWorld(new T.Vector3(...r.local_hand_m)), cargoMeshes).distance_m);
cargo.position.fromArray(pose.cargo.position_m); world.updateMatrixWorld(true);

const limits = Object.entries(pose.jointEulerXYZ).map(([name, angles]) => {
  const node = worker.getObjectByName(name);
  const metadata = name.includes('palm_roll') ? [[0, 0], node.userData.rotation_range_radians, [0, 0]] : JSON.parse(node.userData.limits_xyz_json);
  return { name, all_axes_finite_and_in_range: angles.length === 3 && [0, 1, 2].every(i => typeof angles[i] === 'number' && Number.isFinite(angles[i]) && angles[i] >= metadata[i][0] && angles[i] <= metadata[i][1]), dimension_spec_matches: name.includes('palm_roll') ? null : JSON.stringify(metadata) === JSON.stringify(spec.joints[name].limits_radians_xyz) };
});
const nativePatchChecks = report.native_contacts.map(c => {
  const p = c.opposed_native_pad_patch, hand = worker.getObjectByName(p.hand_mesh), box = cargo.getObjectByName(p.cargo_mesh);
  const ht = triangles(hand)[p.hand_triangle], ct = triangles(box)[p.cargo_triangle];
  const hn = ht.getNormal(new T.Vector3()), cn = ct.getNormal(new T.Vector3());
  const centre = new T.Vector3(...c.patch_centroid_example_worker_m);
  return { side: c.side, hand_mesh: hand.name, hand_triangle: p.hand_triangle, cargo_mesh: box.name, cargo_triangle: p.cargo_triangle,
    hand_triangle_area_m2: ht.getArea(), cargo_triangle_area_m2: ct.getArea(), native_normal_dot: hn.dot(cn),
    patch_point_hand_triangle_distance_m: ht.closestPointToPoint(centre, new T.Vector3()).distanceTo(centre),
    patch_point_cargo_triangle_distance_m: ct.closestPointToPoint(centre, new T.Vector3()).distanceTo(centre),
    hand_barycentric: ht.getBarycoord(ht.closestPointToPoint(centre, new T.Vector3()), new T.Vector3()).toArray(),
    cargo_barycentric: ct.getBarycoord(ct.closestPointToPoint(centre, new T.Vector3()), new T.Vector3()).toArray() };
});

// Classify the reported thumb-control witnesses using the original hand-local triangles.
// The GLB stats runtime component metadata is also recorded so this does not infer a thumb from a batch name.
const thumbWitnesses = report.controls.rejected_closed_thumb_central_HU.witnesses.map(w => {
  const mesh = worker.getObjectByName(w.mesh), hand = mesh.parent, inv = hand.matrixWorld.clone().invert();
  const t = triangles(mesh)[w.triangle];
  const toRest = nativeRestMatrices.get(mesh.name).clone().multiply(mesh.matrixWorld.clone().invert());
  const restVertices = [t.a, t.b, t.c].map(v => v.clone().applyMatrix4(toRest));
  const matchingParts = stats.components.filter(c => c.parent === hand.name && restVertices.every(v =>
    ['x', 'y', 'z'].every((k, i) => v[k] >= c.bounds_runtime.min[i] - 2e-6 && v[k] <= c.bounds_runtime.max[i] + 2e-6)));
  return { mesh: w.mesh, triangle: w.triangle, local_vertices: [t.a, t.b, t.c].map(v => v.clone().applyMatrix4(inv).toArray()),
    rest_vertices: restVertices.map(v => v.toArray()), source_component_bounds_matches: matchingParts.map(p => p.name) };
});

// Independently evaluate whole original GLB meshes at the reported moved-HU/head witness.
function solidAngle(point, tris) {
  let total = 0;
  for (const t of tris) {
    const a = t.a.clone().sub(point), b = t.b.clone().sub(point), c = t.c.clone().sub(point);
    total += 2 * Math.atan2(a.dot(new T.Vector3().crossVectors(b, c)), a.length() * b.length() * c.length() + a.dot(b) * c.length() + b.dot(c) * a.length() + c.dot(a) * b.length());
  }
  return total;
}
cargo.position.set(0, 1.2, .05); world.updateMatrixWorld(true);
const hw = report.controls.actual_HU_head_penetration.witness;
const hp = new T.Vector3(...hw.point_m), headMesh = worker.getObjectByName(hw.head_mesh), cargoMesh = cargo.getObjectByName(hw.cargo_mesh);
const headControl = { point_m: hw.point_m, whole_native_angles_rad: [solidAngle(hp, triangles(headMesh)), solidAngle(hp, triangles(cargoMesh))],
  depths_m: [nearest(hp, [headMesh]).distance_m, nearest(hp, [cargoMesh]).distance_m] };

// Exact classification expression, isolated from geometry: even an observed baseline
// pair must not waive a CHANGED nonadjacent pair. These are truth-table cases,
// not a claim that a collision was induced in the candidate's actual meshes.
const kindExpression = solver.match(/const kind=([^;]+);const row=/)?.[1];
const adjacentExpression = solver.match(/const adjacent=(new Set\(.+?\)),bodyObservations=/)?.[1];
assert(kindExpression && adjacentExpression);
const adjacent = new Function(`return ${adjacentExpression};`)();
const classify = new Function('unchanged', 'linked', 'baselineKeys', 'pairKey', 'a', 'b', `return ${kindExpression};`);
const classificationCases = [
  ['forearm_to_torso', 'joint__forearm_L', 'joint__torso'],
  ['upper_arm_to_head', 'joint__upper_arm_L', 'joint__head'],
  ['opposite_forearms', 'joint__forearm_L', 'joint__forearm_R'],
  ['opposite_upper_arms', 'joint__upper_arm_L', 'joint__upper_arm_R']
].map(([label, boneA, boneB]) => {
  const a = { name: `${boneA}_probe`, bone: boneA }, b = { name: `${boneB}_probe`, bone: boneB };
  const pairKey = (a, b) => [a.name, b.name].sort().join('|');
  const linked = a.bone === b.bone || adjacent.has([a.bone, b.bone].sort().join('|'));
  const classification = classify(false, linked, new Set([pairKey(a, b)]), pairKey, a, b);
  return { label, changed: true, baseline_pair_observed: true, linked, classification,
    blocks_material: classification === 'MATERIAL_CHANGED_NONADJACENT_OR_NEW_PAIR' };
});

const results = {
  schema_id: 'qoima.W05.3.2.independent-cpu-probe.v1',
  source: solverPath, solver_sha256: createHash('sha256').update(solver).digest('hex'),
  validation, sparse_axis: { accepted: sparse.row.accepted, all_sparse_accepted: allSparse.row.accepted, array_length: angles.length, present_indices: Object.keys(angles),
    resulting_euler_xyz: applied.toArray().slice(0, 3), original_euler_xyz: request.jointEulerXYZ.joint__upper_arm_L,
    serialized_sparse_rejected: jsonSparseRejected,
    scope: 'Extracted exact validator only; no production apply or saved JSON changed. Sparse holes cannot survive JSON serialization (they become null). Frozen generated pose uses dense finite arrays.' },
  contacts, lost_contact_after_20um: { gaps_m: movedGaps, both_over_18um: movedGaps.every(g => g > 18e-6) }, limits,
  native_patch_checks: nativePatchChecks, head_control: headControl, thumb_witness_local_vertices: thumbWitnesses,
  changed_nonadjacent_classification_truth_table: classificationCases,
  stats_runtime_component_kind: Array.isArray(stats.runtime_components) ? 'array' : typeof stats.runtime_components,
  limitations: ['No renderer or physical observation.', 'No full collision or continuous-motion certificate.', 'Nearest-distance, triangle-area and saved patch-point tests do not independently recompute total clipped contact area.', 'Validator probe isolates validation; it does not expose or invoke the production closure apply function.', 'Classification cases test extracted logic, not newly induced native-body collisions.', 'Native probes share the pinned Three library and GLTFLoader with the solver.']
};
await writeFile(path.join(output, 'native-probe-result.json'), JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify({ validation_cases: validation.length, ordinary_validation_cases_passed: validation.filter(v => v.matches_expectation).length,
  sparse_omitted_axis_counterexamples: validation.filter(v => !v.matches_expectation).map(v => v.label), contacts,
  native_patch_checks: nativePatchChecks, lost_contact: results.lost_contact_after_20um, head_control: headControl, thumb_witness_local_vertices: thumbWitnesses }));
