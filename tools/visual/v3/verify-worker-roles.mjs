/** CPU actual GLTFLoader + transpiled production module; no web server/GPU. */
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import ts from '../../../frontend/node_modules/typescript/lib/typescript.js';
import * as THREE from '../../../frontend/node_modules/three/build/three.module.js';
import { GLTFLoader } from '../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';

const ROOT = fileURLToPath(new URL('../../../', import.meta.url));
const read = p => readFile(path.join(ROOT, p));
const sha = value => createHash('sha256').update(value).digest('hex');
const spec = JSON.parse(await read('assets/v3/specs/worker-roles.json'));
const dimension = JSON.parse(await read('assets/v3/specs/worker-base.dimensions.json'));
const glb = await read(spec.asset); assert.equal(sha(glb), spec.asset_sha256);
const gltf = await new GLTFLoader().parseAsync(glb.buffer.slice(glb.byteOffset, glb.byteOffset + glb.byteLength), '');
const template = gltf.scene;
const sourceRoot = template.getObjectByName('worker_base_root'); assert(sourceRoot);
const work = path.join(ROOT, 'work', 'P02-role-qa');
await mkdir(work, { recursive: true });
const temporary = await mkdtemp(path.join(work, 'module-'));
const sources = {};
let fixture;
try {
  for (const name of ['workerRoles', 'workerRolesFixture']) {
    const source = await read(`frontend/src/adaptive-v3/${name}.ts`);
    sources[name] = sha(source);
    let code = ts.transpileModule(source.toString(), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
    code = code.replaceAll("from 'three'", `from '${pathToFileURL(path.join(ROOT, 'frontend/node_modules/three/build/three.module.js')).href}'`)
      .replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'", `from '${pathToFileURL(path.join(ROOT, 'frontend/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`)
      .replaceAll("from './workerRoles'", "from './workerRoles.mjs'")
      .replaceAll("from './workerRolesFixture'", "from './workerRolesFixture.mjs'");
    await writeFile(path.join(temporary, name + '.mjs'), code);
  }
  const api = await import(pathToFileURL(path.join(temporary, 'workerRoles.mjs')).href);
  for (const [role, value] of Object.entries(dimension.roles)) {
    assert.deepEqual(api.WORKER_ROLE_DEFINITIONS[role], { color: value.color, code: value.role_code, icon: value.badge });
  }
  let templateDisposals = 0;
  const sourceMeshes = new Map(), sourceMaterials = new Set();
  sourceRoot.traverse(node => {
    if (!node.isMesh) return;
    sourceMeshes.set(node.name, node);
    node.geometry.addEventListener('dispose', () => templateDisposals++);
    for (const mat of Array.isArray(node.material) ? node.material : [node.material]) sourceMaterials.add(mat);
  });
  for (const mat of sourceMaterials) mat.addEventListener('dispose', () => templateDisposals++);
  const templateSignature = () => {
    const nodes = [];
    sourceRoot.traverse(node => nodes.push([node.name, node.position.toArray(), node.quaternion.toArray(), node.scale.toArray(), node.visible]));
    return JSON.stringify({ nodes, materials: [...sourceMaterials].map(m => [m.uuid, m.color.toArray()]) });
  };
  const beforeTemplate = templateSignature();
  fixture = api.createWorkerRolesFixture(template);
  assert.equal(fixture.root.name, 'qa_worker_roles');
  assert.equal(fixture.instances.length, 5);
  const ownedTints = new Set(), badgeDigests = new Set(), roles = [];
  const instanceSignature = instance => {
    const nodes = [];
    instance.root.traverse(node => nodes.push([node.name, node.position.toArray(), node.quaternion.toArray(), node.scale.toArray(), node.visible,
      ...(node.isMesh ? [node.geometry.uuid, ...(Array.isArray(node.material) ? node.material : [node.material]).map(m => [m.uuid, m.color.toArray()])] : [])]));
    return JSON.stringify({ actorId: instance.actorId, role: instance.role, nodes });
  };
  for (const instance of fixture.instances) {
    assert.equal(instance.root.name, 'actor__' + instance.actorId);
    assert.equal(instance.root.userData.actorId, instance.actorId);
    const tints = new Set(); let pivots = 0, anchors = 0, badge;
    instance.root.traverse(node => {
      if (node.userData.pivot_id) pivots++;
      if (node.userData.anchor_id) anchors++;
      if (!node.isMesh) return;
      if (node.userData.roleBadge) { badge = node; return; }
      const source = sourceMeshes.get(node.name); assert(source);
      assert.equal(node.geometry, source.geometry, 'Body geometry must be shared, immutable');
      assert.deepEqual(node.position.toArray(), source.position.toArray());
      assert.deepEqual(node.quaternion.toArray(), source.quaternion.toArray());
      assert.deepEqual(node.scale.toArray(), source.scale.toArray());
      for (const mat of Array.isArray(node.material) ? node.material : [node.material]) {
        if (api.WORKER_ROLE_TINT_NAMES.includes(mat.name)) {
          assert(!sourceMaterials.has(mat)); tints.add(mat);
          assert.equal(mat.color.getHexString(), spec.roles[instance.role].color_srgb.slice(1).toLowerCase());
        } else assert(sourceMaterials.has(mat), 'Base materials must remain shared');
      }
      const parts = JSON.parse(node.userData.source_parts_json);
      if (parts.includes('role_badge_cart')) assert.equal(node.visible, false);
    });
    assert.equal(pivots, 15); assert.equal(anchors, 7); assert.equal(tints.size, 2); assert(badge);
    for (const mat of tints) { assert(!ownedTints.has(mat)); ownedTints.add(mat); }
    const pos = badge.geometry.attributes.position, normals = badge.geometry.attributes.normal;
    assert([...pos.array].every(Number.isFinite));
    for (let i = 0; i < normals.count; i++) assert(Math.abs(new THREE.Vector3().fromBufferAttribute(normals, i).length() - 1) < 1e-5);
    badge.geometry.computeBoundingBox(); const bounds = badge.geometry.boundingBox;
    assert(bounds.min.x >= -.045 && bounds.max.x <= .045 && bounds.min.y >= -.055 && bounds.max.y <= .055);
    assert(bounds.min.z < .006 && bounds.max.z > .006, 'Ink must embed into badge base');
    const hash = sha(Buffer.from(pos.array.buffer, pos.array.byteOffset, pos.array.byteLength));
    assert(!badgeDigests.has(hash)); badgeDigests.add(hash);
    roles.push({ actorId: instance.actorId, role: instance.role, color: spec.roles[instance.role].color_srgb,
      code: badge.userData.roleCode, icon: badge.userData.icon, ownedTintMaterials: tints.size,
      badgeGeometrySha256: hash, badgeVertices: pos.count, pivots, anchors });
  }
  assert.equal(ownedTints.size, 10);
  const target = fixture.instances[0], untouched = fixture.instances.slice(1).map(instanceSignature);
  const torso = target.root.getObjectByName('joint__torso');
  torso.rotation.x = .123;
  const originalPose = torso.quaternion.toArray();
  const identity = target.actorId;
  let retiredBadgeDisposals = 0;
  for (const role of Object.keys(spec.roles)) {
    const badge = target.root.getObjectByName('role_badge__' + identity);
    const previous = badge.geometry, changed = target.role !== role;
    let released = 0;
    const onRelease = () => released++;
    previous.addEventListener('dispose', onRelease);
    api.applyWorkerRole(target, role);
    assert.equal(released, changed ? 1 : 0, 'Role change leaked/released the wrong badge geometry');
    previous.removeEventListener('dispose', onRelease);
    retiredBadgeDisposals += released;
    assert.equal(target.actorId, identity);
    assert.deepEqual(torso.quaternion.toArray(), originalPose, 'Role change altered pose');
    assert.deepEqual(fixture.instances.slice(1).map(instanceSignature), untouched, 'Cross-instance mutation');
    assert.equal(templateSignature(), beforeTemplate, 'Template mutated');
  }
  fixture.reset();
  assert.equal(target.role, 'picker');
  assert.deepEqual(torso.quaternion.toArray(), originalPose, 'Role reset changed body pose');
  assert.deepEqual(fixture.instances.slice(1).map(instanceSignature), untouched);
  assert.throws(() => api.createWorkerInstance(template, '', 'picker'));
  assert.throws(() => api.createWorkerInstance(template, '01', 'picker'));
  assert.throws(() => api.createWorkerInstance(template, 'P01', 'unknown'));
  assert.throws(() => api.applyWorkerRole(target, 'unknown'));
  assert.throws(() => api.createWorkerInstance(new THREE.Group(), 'P01', 'picker'));
  let ownedDisposals = 0;
  for (const mat of ownedTints) mat.addEventListener('dispose', () => ownedDisposals++);
  for (const instance of fixture.instances) instance.root.traverse(node => {
    if (node.userData.roleBadge) node.geometry.addEventListener('dispose', () => ownedDisposals++);
  });
  fixture.dispose(); fixture.dispose();
  assert.equal(ownedDisposals, 15, 'Dispose exactly10tint materials+5current badge geometries once');
  assert.equal(templateDisposals, 0, 'Instance disposal released shared template resources');
  assert(fixture.instances.every(i => i.disposed)); assert.equal(fixture.root.children.length, 0);
  assert.throws(() => api.applyWorkerRole(target, 'picker'));
  assert.equal(templateSignature(), beforeTemplate);
  const result = { task_id: 'P02', owner: 'people_packing', status: 'VERIFY', recorded_at: new Date().toISOString(),
    glb_sha256: sha(glb), implementation_sha256: sources, roles, numericChecks: {
      sharedBodyGeometry: true, exactlyTwoTintClonesPerActor: true, unchangedDarkBaseMaterials: true,
      sourcePickerInkHiddenOnlyOnClones: true, fiveDistinctDimensionalBadgeGeometries: true,
      roleRoundtripActorIdentityAndPosePreserved: true, otherFourActorsAndTemplateUnchanged: true,
      invalidInputsFailExplicitly: true, idempotentOwnedResourceDisposal: true,
      retiredBadgeGeometriesDisposedOnRoleChange: retiredBadgeDisposals,
      ownedResourcesDisposed: ownedDisposals, sharedResourcesDisposed: templateDisposals,
    }, browserReview: 'pending root five-role views, badge closeups and role/reset isolation capture',
    scope: 'Representative visual QA fixture, no staffing/replay/eligibility/backend behavior.' };
  await writeFile(path.join(ROOT, 'docs/adaptive-v3/evidence/P02.numeric.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ status: result.status, roles: roles.length, ownedTints: ownedTints.size, distinctBadges: badgeDigests.size,
    ownedResourcesDisposed: ownedDisposals, sharedResourcesDisposed: templateDisposals, glb_sha256: sha(glb) }));
} finally {
  fixture?.dispose();
  // This exact task-created temp directory is under workspace/work/P02-role-qa.
  assert(path.dirname(temporary) === work && path.basename(temporary).startsWith('module-'));
  await rm(temporary, { recursive: true, force: true });
}
