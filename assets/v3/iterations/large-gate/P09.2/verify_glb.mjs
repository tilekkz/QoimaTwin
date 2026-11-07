/** Actual GLTFLoader aperture and continuous aligned L05 candidate check. */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url));
const THREE = await import(pathToFileURL(path.join(ROOT, 'frontend/node_modules/three/build/three.module.js')).href);
const { GLTFLoader } = await import(pathToFileURL(path.join(ROOT, 'frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js')).href);
const read = p => readFile(path.join(ROOT, p));
const spec = JSON.parse(await read('assets/v3/specs/large-gate.dimensions.json'));
const asset = process.argv[2] ?? 'large-gate', variant = spec.variants[asset]; assert(variant);
const actualL05 = JSON.parse(await read('docs/v3/contract-proposals/large-gate-v3.json'));
const raw = await read(`frontend/public/models/v3/${asset}.glb`);
const gltf = await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength), '');
const scene = gltf.scene; scene.updateMatrixWorld(true);
const root = scene.getObjectByName(variant.root_name); assert(root);
const statsPath = `assets/v3/blender/${asset}.stats.json`, stats = JSON.parse(await read(statsPath));
const vertices = [], triangles = [], volumes = {}; let normals = 0, meshes = 0, nodes = 0;
root.traverse(node => {
  nodes++;
  if (!node.isMesh) return;
  meshes++;
  const pos = node.geometry.attributes.position, normal = node.geometry.attributes.normal, index = node.geometry.index.array, points = [];
  for (let i = 0; i < pos.count; i++) {
    const p = new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(node.matrixWorld);
    assert(p.toArray().every(Number.isFinite)); points.push(p); vertices.push(p);
    assert(Math.abs(new THREE.Vector3().fromBufferAttribute(normal, i).length() - 1) < 1e-5); normals++;
  }
  let volume = 0;
  for (let i = 0; i < index.length; i += 3) {
    const t = [points[index[i]], points[index[i + 1]], points[index[i + 2]]]; triangles.push(t);
    volume += t[0].dot(new THREE.Vector3().crossVectors(t[1], t[2])) / 6;
  }
  assert(volume > 0, node.name + ' inverted/zero signed volume'); volumes[node.name] = volume;
});
function clips(points, lo, hi) {
  let poly = points;
  for (let axis = 0; axis < 3; axis++) for (const [bound, sense] of [[lo[axis] + 1e-6, 1], [hi[axis] - 1e-6, -1]]) {
    const old = poly; poly = []; if (!old.length) return false;
    for (let i = 0; i < old.length; i++) {
      const a = old[i], b = old[(i + 1) % old.length], da = sense * (a.getComponent(axis) - bound), db = sense * (b.getComponent(axis) - bound);
      if (da >= 0) poly.push(a);
      if ((da >= 0) !== (db >= 0)) poly.push(a.clone().lerp(b, da / (da - db)));
    }
  }
  return poly.length > 0;
}
const half = variant.clear_width_m / 2;
assert(!triangles.some(t => clips(t, [-half, 0, 0], [half, 4.5, .25])));
function rayHit(origin, direction) {
  const ray = new THREE.Ray(new THREE.Vector3(...origin), new THREE.Vector3(...direction)); let best;
  for (const t of triangles) {
    const q = ray.intersectTriangle(...t, false, new THREE.Vector3());
    if (q && (!best || q.distanceTo(ray.origin) < best.distanceTo(ray.origin))) best = q;
  }
  return best;
}
const left = rayHit([0, 2.25, .125], [-1, 0, 0]), right = rayHit([0, 2.25, .125], [1, 0, 0]), top = rayHit([0, 1, .125], [0, 1, 0]);
assert(left && right && top);
const width = right.x - left.x, height = top.y;
assert(Math.abs(width - variant.clear_width_m) < 2e-6 && Math.abs(height - 4.5) < 2e-6);
let clearRays = 0;
for (let x = 0; x <= 20; x++) for (let y = 0; y <= 24; y++) {
  assert(!rayHit([-half + .01 + x * (2 * half - .02) / 20, .01 + y * 4.48 / 24, -.1], [0, 0, 1])); clearRays++;
}
const padding = actualL05.loaded_bound.horizontal_padding_each_side_m, topPadding = actualL05.loaded_bound.top_padding_m;
const sourceComponents = Object.fromEntries(['vehicle_blueprint', 'cradle_assumption', 'load_profile'].map(k => [k, actualL05[k].bounds_local_m]));
assert.deepEqual(sourceComponents, spec.L05_candidate.components, 'L05 input changed');
const rotation = new THREE.Matrix4().makeRotationY(variant.wall_mount.vehicle_yaw_relative_module), candidates = [];
let minX = Infinity, maxX = -Infinity, maxY = -Infinity;
for (const [name, bounds] of Object.entries(sourceComponents)) {
  const corners = [];
  for (const x of [bounds.min[0], bounds.max[0]]) for (const y of [bounds.min[1], bounds.max[1]]) for (const z of [bounds.min[2], bounds.max[2]]) corners.push(new THREE.Vector3(x, y, z).applyMatrix4(rotation));
  const b = new THREE.Box3().setFromPoints(corners);
  const lo = [b.min.x - padding, b.min.y, b.min.z - padding - 2], hi = [b.max.x + padding, b.max.y + topPadding, b.max.z + padding + 2];
  minX = Math.min(minX, lo[0]); maxX = Math.max(maxX, hi[0]); maxY = Math.max(maxY, hi[1]);
  const hits = triangles.filter(t => clips(t, lo, hi)).length; assert.equal(hits, 0, name + ' aligned candidate hits gate');
  candidates.push({ component: name, continuous_translation_swept_box_local: { min: lo, max: hi }, gateTriangleIntersections: hits });
}
const requiredWidth = maxX - minX, requiredHeight = maxY;
assert(Math.abs(requiredWidth - 4.7) < 1e-9 && Math.abs(requiredHeight - 2.35) < 1e-9);
const sideMargin = Math.min(minX - left.x, right.x - maxX);
const leftMargin = minX - left.x, rightMargin = right.x - maxX;
assert(Math.abs(leftMargin - variant.nominal_candidate_side_margin_m) < 2e-6 && Math.abs(rightMargin - leftMargin) < 2e-6);
// Meaningful same-algorithm negative: move the padded LONG beyond its margin.
const load = candidates.find(c => c.component === 'load_profile'), shift = leftMargin + .15;
const badLo = [...load.continuous_translation_swept_box_local.min], badHi = [...load.continuous_translation_swept_box_local.max]; badLo[0] += shift; badHi[0] += shift;
const negativeHits = triangles.filter(t => clips(t, badLo, badHi)).length; assert(negativeHits > 0);
const box = new THREE.Box3().setFromPoints(vertices), dims = box.getSize(new THREE.Vector3()).toArray();
assert(dims.every((v, i) => Math.abs(v - variant.dimensions_m[i]) < 2e-6));
const identity = new THREE.Matrix4(); assert(root.matrixWorld.elements.every((v, i) => Math.abs(v - identity.elements[i]) < 1e-7));
assert.equal(meshes, 5); assert.equal(nodes, 11); assert.equal(triangles.length, 824);
const anchors = {};
for (const [name, expected] of Object.entries(variant.anchors)) {
  const node = root.getObjectByName(name); assert(node); anchors[name] = node.getWorldPosition(new THREE.Vector3()).toArray();
  assert(anchors[name].every((v, i) => Math.abs(v - expected[i]) < 2e-6));
}
const result = { asset_id: asset, method: 'Actual GLTFLoader world triangles/normals and exact continuous translated L05 padded component AABBs, independent of Blender authoring conversion.',
  glb_sha256: createHash('sha256').update(raw).digest('hex'), bytes: raw.length, nodes, meshes, triangles: triangles.length, finite_unit_normals: normals,
  bounds_runtime: { min: box.min.toArray(), max: box.max.toArray() }, dimensions_m: dims, actual_clear_width_m: width, actual_clear_height_m: height,
  open_aperture_triangle_intrusions: 0, clear_depth_rays: clearRays, positive_signed_volumes_m3: volumes, root_identity: true, anchors,
  L05_candidate: { requiredWidth, requiredHeight, leftMargin, rightMargin, sideMargin, heightMargin: height - requiredHeight,
    physical_vehicle_yaw_relative_gate: variant.wall_mount.vehicle_yaw_relative_module, motion_root_z: asset === 'large-gate' ? [-2, 2] : [2, -2],
    continuous_swept_components: candidates, negative_lateral_shift: { shiftM: shift, detectedGateTriangleIntersections: negativeHits }, operational_admission: false,
    scope: 'Candidate aligned geometric fit only; not future forklift/support/action/turning approval.' }, khronos: 'pending root', browser_four_views: 'pending root' };
stats.glb_numeric_verification = result;
await writeFile(path.join(ROOT, statsPath), JSON.stringify(stats, null, 2) + '\n');
await writeFile(path.join(ROOT, `assets/v3/iterations/${asset}/P09.2/actual-glb-checks.json`), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ asset, sha256: result.glb_sha256, bytes: raw.length, clearWidth: width, clearHeight: height, requiredWidth, requiredHeight, leftMargin, rightMargin, negativeHits }));
