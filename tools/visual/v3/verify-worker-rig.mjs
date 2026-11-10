/** CPU-only actual GLTFLoader FK, mesh-interior/support and absolute-reset QA.
 * Run from repo root: node tools/visual/v3/verify-worker-rig.mjs
 * Expected coordinates were extracted from independent accepted Blender poses.
 */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import * as THREE from '../../../frontend/node_modules/three/build/three.module.js';
import { GLTFLoader } from '../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';

const ROOT = fileURLToPath(new URL('../../../', import.meta.url));
const read = async p => readFile(path.join(ROOT, p));
const digest = data => createHash('sha256').update(data).digest('hex');
const specPath = 'assets/v3/specs/worker-rig-qa.json';
const specBytes = await read(specPath);
const spec = JSON.parse(specBytes);
const bytes = await read(spec.glb);
assert.equal(digest(bytes), spec.glb_sha256, 'QA spec is for a different GLB');
const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
const scene = gltf.scene;
const root = scene.getObjectByName(spec.root_name);
assert(root);
const joints = new Map(), anchors = new Map(), meshes = [];
let nodeCount = 0;
root.traverse(node => {
  nodeCount++;
  if (node.userData.pivot_id) joints.set(node.name, node);
  if (node.userData.anchor_id) anchors.set(node.name, node);
  if (node.isMesh) meshes.push(node);
});
assert.equal(joints.size, 15);
assert.equal(anchors.size, 7);
assert.equal(meshes.length, 23);
assert.equal(nodeCount, 46);
const bind = new Map([...joints].map(([name, node]) => [name, {
  position: node.position.clone(), quaternion: node.quaternion.clone(), scale: node.scale.clone()
}]));
const byPart = new Map();
for (const mesh of meshes) {
  for (const name of JSON.parse(mesh.userData.source_parts_json)) byPart.set(name, mesh);
}
assert.equal(byPart.size, 56);

function applyPose(pose) {
  for (const [name, node] of joints) {
    const value = bind.get(name);
    node.position.copy(value.position);
    node.scale.copy(value.scale);
    node.quaternion.copy(value.quaternion);
    node.quaternion.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(...pose.jointEulerXYZ[name], 'XYZ')));
  }
  joints.get('joint__pelvis').position.add(new THREE.Vector3(...pose.pelvisShift));
  scene.updateMatrixWorld(true);
}
function worldPoint(node) { return node.getWorldPosition(new THREE.Vector3()).toArray(); }
function maxError(a, b) { return Math.max(...a.map((v, i) => Math.abs(v - b[i]))); }
function snapshot() {
  const values = [];
  root.traverse(node => values.push(...node.matrixWorld.elements));
  return values;
}

// Weld only coincident geometry vertices, then split disconnected closed solids.
// A material batch may contain overlapping cuff/sleeve or head/ear components;
// interior is the union of solids, not parity across their overlapping shells.
function solids(mesh) {
  const geometry = mesh.geometry, position = geometry.attributes.position;
  const index = geometry.index.array;
  const ids = new Map(), vertexId = [], points = [];
  for (let i = 0; i < position.count; i++) {
    const p = new THREE.Vector3().fromBufferAttribute(position, i);
    const key = p.toArray().map(v => Math.round(v * 1e6)).join(',');
    if (!ids.has(key)) { ids.set(key, ids.size); points.push(p); }
    vertexId.push(ids.get(key));
  }
  const triangles = [];
  for (let i = 0; i < index.length; i += 3) {
    const tri = [vertexId[index[i]], vertexId[index[i + 1]], vertexId[index[i + 2]]];
    triangles.push(tri);
  }
  const parent = triangles.map((_, i) => i);
  const find = i => parent[i] === i ? i : (parent[i] = find(parent[i]));
  const join = (a, b) => { parent[find(a)] = find(b); };
  const adjacency = new Map();
  for (let t = 0; t < triangles.length; t++) for (let e = 0; e < 3; e++) {
    const key = [triangles[t][e], triangles[t][(e + 1) % 3]].sort((a, b) => a - b).join(',');
    if (!adjacency.has(key)) adjacency.set(key, []);
    adjacency.get(key).push(t);
  }
  // Two overlapping original solids can share an exact bevel edge. Four
  // incident triangles must not weld those shells into an artificial solid.
  for (const incident of adjacency.values()) if (incident.length === 2) join(...incident);
  const groups = new Map();
  for (const [i, tri] of triangles.entries()) {
    const id = find(i);
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(tri);
  }
  return [...groups.values()].map(group => {
    const edges = new Map();
    for (const tri of group) for (let i = 0; i < 3; i++) {
      const key = [tri[i], tri[(i + 1) % 3]].sort((a, b) => a - b).join(',');
      edges.set(key, (edges.get(key) ?? 0) + 1);
    }
    assert([...edges.values()].every(count => count === 2), `Open/nonmanifold QA solid: ${mesh.name}`);
    return group.map(tri => new THREE.Triangle(...tri.map(i => points[i].clone().applyMatrix4(mesh.matrixWorld))));
  });
}
const directions = [[1, .337, .171], [.213, 1, .451], [.319, .127, 1]].map(v => new THREE.Vector3(...v).normalize());
function marginInSolid(triangles, point) {
  let votes = 0, margin = Infinity;
  for (const triangle of triangles) margin = Math.min(margin, triangle.closestPointToPoint(point, new THREE.Vector3()).distanceTo(point));
  for (const direction of directions) {
    const ray = new THREE.Ray(point, direction), hits = [];
    for (const triangle of triangles) {
      const hit = ray.intersectTriangle(triangle.a, triangle.b, triangle.c, false, new THREE.Vector3());
      if (hit) hits.push(hit.distanceTo(point));
    }
    hits.sort((a, b) => a - b);
    const unique = hits.filter((v, i) => i === 0 || Math.abs(v - hits[i - 1]) > 1e-7);
    votes += unique.length % 2;
  }
  return votes >= 2 ? margin : -1;
}

applyPose(spec.poses[0]);
const initial = snapshot(), results = [];
for (const pose of spec.poses) {
  applyPose(pose);
  let anchorError = 0, jointError = 0;
  for (const [name, expected] of Object.entries(pose.expectedAnchors)) anchorError = Math.max(anchorError, maxError(worldPoint(anchors.get(name)), expected));
  for (const [name, expected] of Object.entries(pose.expectedJointWorld)) jointError = Math.max(jointError, maxError(worldPoint(joints.get(name)), expected));
  assert(anchorError <= pose.tolerance && jointError <= pose.tolerance, `${pose.id}: source FK mismatch`);
  const shapes = new Map();
  for (const witness of pose.jointWitnesses) for (const part of witness.sourceParts) {
    const mesh = byPart.get(part); assert(mesh, part);
    if (!shapes.has(mesh)) shapes.set(mesh, solids(mesh));
  }
  const contacts = pose.jointWitnesses.map(witness => {
    const point = new THREE.Vector3(...witness.worldPoint);
    const margins = witness.sourceParts.map(part => Math.max(...shapes.get(byPart.get(part)).map(s => marginInSolid(s, point))));
    assert(margins.every((m, i) => m >= witness.sourceSurfaceMargins[i] - pose.tolerance),
      `${pose.id}: contact lost against source witness ${witness.joint}`);
    return { joint: witness.joint, meshSolidMarginsM: margins };
  });
  const soles = {};
  for (const side of ['L', 'R']) {
    const boot = byPart.get('boot_' + side), position = boot.geometry.attributes.position;
    let minimumY = Infinity;
    for (let i = 0; i < position.count; i++) minimumY = Math.min(minimumY, new THREE.Vector3().fromBufferAttribute(position, i).applyMatrix4(boot.matrixWorld).y);
    assert(Math.abs(minimumY) < pose.tolerance, `${pose.id}: sole hover`);
    soles[side] = { actualBootMinYM: minimumY, anchor: worldPoint(anchors.get('anchor_foot_floor_' + side)) };
  }
  const once = snapshot();
  applyPose(spec.poses[(spec.poses.indexOf(pose) + 1) % spec.poses.length]);
  applyPose(pose);
  assert.equal(maxError(snapshot(), once), 0, `${pose.id}: absolute pose depends on previous pose`);
  applyPose(spec.poses[0]);
  assert.equal(maxError(snapshot(), initial), 0, `${pose.id}: reset drift`);
  results.push({ id: pose.id, maximumAnchorErrorM: anchorError, maximumJointErrorM: jointError, contacts, soles,
    absolutePoseRepeatMatrixError: 0, resetMatrixError: 0 });
}
// Repeat in a nonsequential order to catch cumulative/local-state dependence.
for (const id of [3, 1, 2, 1, 0, 3, 0]) applyPose(spec.poses[id]);
assert.equal(maxError(snapshot(), initial), 0);
const report = {
  task_id: 'P01.7', owner: 'people_packing', status: 'VERIFY', recorded_at: new Date().toISOString(),
  method: 'Actual Three GLTFLoader; absolute local Euler XYZ FK vs accepted Blender snapshot coordinates; exported triangle-solid interiors and boot vertices; exact matrix reset.',
  glb: spec.glb, glb_sha256: digest(bytes), qa_spec: specPath, qa_spec_sha256: digest(specBytes),
  runner_sha256: digest(await readFile(fileURLToPath(import.meta.url))), nodes: nodeCount, runtime_meshes: meshes.length,
  pivots: joints.size, anchors: anchors.size, source_pose_witnesses: 56, results,
  rotationConvention: 'THREE intrinsic XYZ (RxRyRz). Converted from actual source quaternions; original mathutils extrinsic XYZ (RzRyRx) inputs retained separately in QA spec.',
  actualMeshMethod: 'Geometrically welded triangles split via two-face manifold edge adjacency; overlapping closed solids remain separate. Witness interior is union of solids, with margins at least accepted source witness minus20um.',
  deterministicReset: { fullHierarchyMatrixError: 0, repeatedAbsolutePoseMatrixError: 0, scrambledPoseOrder: [3, 1, 2, 1, 0, 3, 0] },
  root_checks: { liveBrowserPoses: 'pending root', browserContactViewsAndReset: 'pending root' },
  limits: 'Four stated base FK poses only; no gait, cart grasp, driver/equipment action or workflow claim. Source rig/GLB unchanged.'
};
await writeFile(path.join(ROOT, 'docs/adaptive-v3/evidence/P01.7.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ status: report.status, poses: results.length, jointContacts: 56,
  maxAnchorErrorM: Math.max(...results.map(r => r.maximumAnchorErrorM)),
  maxJointErrorM: Math.max(...results.map(r => r.maximumJointErrorM)), resetMatrixError: 0, glb_sha256: report.glb_sha256 }));
