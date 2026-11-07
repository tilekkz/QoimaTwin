/** Independent actual GLTFLoader vertices/apertures; no renderer/server. */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url));
const THREE = await import(pathToFileURL(path.join(ROOT, 'frontend/node_modules/three/build/three.module.js')).href);
const { GLTFLoader } = await import(pathToFileURL(path.join(ROOT, 'frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js')).href);
const read = async p => readFile(path.join(ROOT, p));
const spec = JSON.parse(await read('assets/v3/specs/environment-shell.dimensions.json'));
const source = JSON.parse(await read('assets/v3/iterations/environment-shell/P09.3/source-mesh-qa.json'));
const statsPath = 'assets/v3/blender/environment-shell.stats.json', stats = JSON.parse(await read(statsPath));
const raw = await read('frontend/public/models/v3/environment-shell.glb');
assert.equal(raw.toString('utf8', 0, 4), 'glTF'); assert.equal(raw.readUInt32LE(8), raw.length);
const doc = JSON.parse(raw.subarray(20, 20+raw.readUInt32LE(12)).toString().trim());
const gltf = await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset, raw.byteOffset+raw.byteLength), '');
gltf.scene.updateMatrixWorld(true);
const root = gltf.scene.getObjectByName('environment_shell_root'); assert(root);
const points = [], triangles = [], batches = new Map(); let normalCount = 0, loaderMeshes = 0;
root.traverse(node => {
  if (!node.isMesh) return; loaderMeshes++;
  let batch = node; while (batch && !batch.userData.source_parts_json) batch = batch.parent;
  assert(batch, node.name);
  if (!batches.has(batch.name)) batches.set(batch.name, []);
  const p = node.geometry.attributes.position, n = node.geometry.attributes.normal, indices = node.geometry.index.array, vertices = [];
  for (let i = 0; i < p.count; i++) {
    const v = new THREE.Vector3().fromBufferAttribute(p, i).applyMatrix4(node.matrixWorld);
    assert(v.toArray().every(Number.isFinite)); vertices.push(v); points.push(v);
    assert(Math.abs(new THREE.Vector3().fromBufferAttribute(n, i).length()-1) < 1e-5); normalCount++;
  }
  for (let i = 0; i < indices.length; i += 3) {
    const tri = [vertices[indices[i]], vertices[indices[i+1]], vertices[indices[i+2]]]; triangles.push(tri); batches.get(batch.name).push(tri);
  }
});
const volumes = {};
for (const [name, tris] of batches) {
  const ref = tris[0][0]; let volume = 0;
  for (const tri of tris) volume += tri[0].clone().sub(ref).dot(new THREE.Vector3().crossVectors(tri[1].clone().sub(ref), tri[2].clone().sub(ref)))/6;
  assert(volume > 0, name+' inverted/nonpositive volume'); volumes[name] = volume;
}
// Two-way actual/source vertex matching, independent of authoring conversion.
// Export can duplicate positions for normals/materials; match geometry, not count.
const cell = 1e-4, tolerance = 2e-5;
function grid(values) {
  const result = new Map();
  for (const p of values) { const key = p.toArray().map(v => Math.floor(v/cell)).join(','); if (!result.has(key)) result.set(key, []); result.get(key).push(p); }
  return result;
}
function nearest(p, bins) {
  const base = p.toArray().map(v => Math.floor(v/cell)); let best, distance = Infinity;
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
    for (const q of bins.get([base[0]+dx, base[1]+dy, base[2]+dz].join(',')) ?? []) {
      const d = p.distanceTo(q); if (d < distance) { distance = d; best = q; }
    }
  }
  assert(best && distance <= tolerance, `Geometry cloud mismatch at${p.toArray()} distance${distance}`);
  return { point: best, distance };
}
const sourcePoints = Object.values(source.components).flatMap(c => c.vertices_runtime.map(p => new THREE.Vector3(...p)));
const sourceGrid = grid(sourcePoints), actualGrid = grid(points); let maxError = 0;
for (const point of points) maxError = Math.max(maxError, nearest(point, sourceGrid).distance);
const components = {};
for (const [name, c] of Object.entries(source.components)) {
  const matched = c.vertices_runtime.map(p => { const found = nearest(new THREE.Vector3(...p), actualGrid); maxError = Math.max(maxError, found.distance); return found.point; });
  const b = new THREE.Box3().setFromPoints(matched);
  components[name] = { bounds_runtime: { min: b.min.toArray(), max: b.max.toArray() }, category: c.category, parent: c.parent };
}
function clips(poly, lo, hi) {
  for (let axis = 0; axis < 3; axis++) for (const [bound, sense] of [[lo[axis]+tolerance, 1], [hi[axis]-tolerance, -1]]) {
    const old = poly; poly = []; if (!old.length) return false;
    for (let i = 0; i < old.length; i++) { const a = old[i], b = old[(i+1)%old.length], da = sense*(a.getComponent(axis)-bound), db = sense*(b.getComponent(axis)-bound); if (da >= 0) poly.push(a); if ((da >= 0) !== (db >= 0)) poly.push(a.clone().lerp(b, da/(da-db))); }
  }
  return poly.length > 0;
}
const apertures = [];
for (const gate of spec.gates) {
  const [px, , pz] = gate.position, c = Math.cos(gate.yaw_rad), s = Math.sin(gate.yaw_rad), half = gate.clear_width_m/2, h = gate.clear_height_m;
  const local = p => new THREE.Vector3((p.x-px)*c-(p.z-pz)*s, p.y, (p.x-px)*s+(p.z-pz)*c);
  const nearby = [];
  for (const tri of triangles) { const t = tri.map(local); const b = new THREE.Box3().setFromPoints(t); if (b.max.x >= -half-.3 && b.min.x <= half+.3 && b.max.y >= -.01 && b.min.y <= h+.3 && b.max.z >= -.1 && b.min.z <= .35) nearby.push(t); }
  assert(!nearby.some(t => clips(t, [-half, 0, 0], [half, h, .25])), gate.port_id+' aperture intrusion');
  function hit(origin, direction, maxDistance) { const ray = new THREE.Ray(new THREE.Vector3(...origin), new THREE.Vector3(...direction)); let result; for (const t of nearby) { const q = ray.intersectTriangle(...t, false, new THREE.Vector3()); if (q && q.distanceTo(ray.origin) <= maxDistance && (!result || q.distanceTo(ray.origin) < result.distanceTo(ray.origin))) result = q; } return result; }
  let clear = 0;
  for (let x = 0; x <= 20; x++) for (let y = 0; y <= 24; y++) { assert(!hit([-half+.01+x*(2*half-.02)/20, .01+y*(h-.02)/24, -.1], [0, 0, 1], .45)); clear++; }
  const left = hit([0, h/2, .125], [-1, 0, 0], 2*half+1), right = hit([0, h/2, .125], [1, 0, 0], 2*half+1), top = hit([0, 1, .125], [0, 1, 0], h+1); assert(left && right && top);
  const w = right.x-left.x; assert(Math.abs(w-2*half) <= tolerance && Math.abs(top.y-h) <= tolerance);
  apertures.push({ port_id: gate.port_id, actualClearWidthM: w, actualClearHeightM: top.y, apertureTriangleIntrusions: 0, clearDepthRays: clear });
}
const box = new THREE.Box3().setFromPoints(points), identity = new THREE.Matrix4();
assert(root.matrixWorld.elements.every((v, i) => Math.abs(v-identity.elements[i]) < 1e-7));
assert.equal(triangles.length, 16412); assert.equal(batches.size, 37); assert.equal(Object.keys(components).length, 361);
const anchors = {};
root.traverse(n => { if (n.userData.anchor_id) anchors[n.name] = n.getWorldPosition(new THREE.Vector3()).toArray(); });
for (const [name, expected] of Object.entries({ anchor_floor_SW: [0,0,0], anchor_floor_SE: [144,0,0], anchor_floor_NW: [0,0,72], anchor_floor_NE: [144,0,72], anchor_ceiling_8m: [72,8,36] })) assert(anchors[name].every((v, i) => Math.abs(v-expected[i]) <= tolerance));
const result = { method: 'Actual GLTFLoader BIN geometry/TRS, two-way source/evaluated vertex-cloud matching, independently measured six apertures and triangle/open-box clipping.', glb_sha256: createHash('sha256').update(raw).digest('hex'), bytes: raw.length,
  gltf_nodes: doc.nodes.length, gltf_meshes: doc.meshes.length, loaderMeshes, material_primitives: [...batches.values()].length+2, triangles: triangles.length, finite_unit_normals: normalCount,
  all37BatchSignedVolumesPositive: true, maximumSourceGLBVertexDistanceM: maxError, matchedSourceComponents: 361, tolerance_m: tolerance,
  bounds_including_display_plinth: { min: box.min.toArray(), max: box.max.toArray() }, actualOperationalFloor: components.FLOOR__operational_support.bounds_runtime,
  actualDisplayOnlyPlinth: components.DISPLAY_ONLY__plinth.bounds_runtime, ceilingY: box.max.y, rootIdentity: true, anchors, apertures,
  khronos: 'pending root', actual_browser_views: 'pending root' };
stats.glb_numeric_verification = result;
await writeFile(path.join(ROOT, statsPath), JSON.stringify(stats, null, 2)+'\n');
await writeFile(path.join(ROOT, 'assets/v3/iterations/environment-shell/P09.3/glb-geometry-components.json'), JSON.stringify({ components, maximumSourceGLBVertexDistanceM: maxError })+'\n');
await writeFile(path.join(ROOT, 'assets/v3/iterations/environment-shell/P09.3/actual-glb-checks.json'), JSON.stringify(result, null, 2)+'\n');
console.log(JSON.stringify({ sha256: result.glb_sha256, bytes: raw.length, gltfNodes: doc.nodes.length, gltfMeshes: doc.meshes.length, loaderMeshes, triangles: triangles.length, finiteNormals: normalCount, vertexCloudMaxErrorM: maxError, sixApertures: apertures }));
