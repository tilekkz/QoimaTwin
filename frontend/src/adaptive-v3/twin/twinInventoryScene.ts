import * as THREE from 'three';
import type {BoundCargo} from '../warehouseCargo';
import type {XYZ} from '../warehouseTypes';
import type {createTwinInventory} from './twinInventory';

type Inventory = ReturnType<typeof createTwinInventory>;
type Variant = 'A' | 'B';
type Part = {
  key: string;
  mesh: THREE.InstancedMesh;
  intrinsic: THREE.Matrix4;
};
type Entry = Inventory['variants']['A']['additions'][number];

function cargoPose(position: XYZ, yaw: number): THREE.Matrix4 {
  return new THREE.Matrix4().compose(
    new THREE.Vector3(...position),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw),
    new THREE.Vector3(1, 1, 1),
  );
}

function prototypeParts(scene: THREE.Scene, cargo: readonly BoundCargo[]): Map<string, Part[]> {
  const bindings = new Map(cargo.map(row => [row.handling_unit_id, row]));
  const parts = new Map<string, Part[]>();
  scene.updateMatrixWorld(true);
  scene.traverse(node => {
    if (!(node instanceof THREE.InstancedMesh) || node.userData.semanticKind !== 'HU') return;
    const ids = node.userData.semanticIds as string[];
    ids.forEach((id, index) => {
      const source = bindings.get(id);
      if (!source) return;
      const instance = new THREE.Matrix4();
      node.getMatrixAt(index, instance);
      const intrinsic = cargoPose(source.position, source.yaw_rad).invert()
        .multiply(node.matrixWorld).multiply(instance);
      const list = parts.get(id) ?? [];
      list.push({key: node.uuid, mesh: node, intrinsic});
      parts.set(id, list);
    });
  });
  return parts;
}

function removeGroup(group: THREE.Group): void {
  group.removeFromParent();
  group.traverse(node => {if (node instanceof THREE.InstancedMesh) node.dispose();});
  group.clear();
}

function createStockGroup(rows: readonly Entry[], parts: Map<string, Part[]>): THREE.Group {
  const group = new THREE.Group();
  group.userData.candidateLayoutVisual = true;
  const batches = new Map<string, {part: Part; entries: {row: Entry; part: Part}[]}>();
  try {
    for (const row of rows) {
      const prototype = parts.get(row.prototype_hu_id);
      if (!prototype?.length) throw Error('Missing stock prototype ' + row.prototype_hu_id);
      for (const part of prototype) {
        const batch = batches.get(part.key) ?? {part, entries: []};
        batch.entries.push({row, part});
        batches.set(part.key, batch);
      }
    }
    for (const {part, entries} of batches.values()) {
      const mesh = new THREE.InstancedMesh(part.mesh.geometry, part.mesh.material, entries.length);
      mesh.castShadow = part.mesh.castShadow;
      mesh.receiveShadow = part.mesh.receiveShadow;
      mesh.userData = {semanticKind: 'demo-stock',
        semanticIds: entries.map(entry => entry.row.handling_unit_id)};
      entries.forEach(({row, part: source}, index) => mesh.setMatrixAt(index,
        cargoPose(row.position, row.yaw_rad).multiply(source.intrinsic)));
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingBox();
      mesh.computeBoundingSphere();
      group.add(mesh);
    }
    return group;
  } catch (error) {removeGroup(group); throw error;}
}

/** Capacity-fill stock shares source geometry and preserves the original inventory buffers. */
export function createTwinInventoryScene(scene: THREE.Scene, source: readonly BoundCargo[]) {
  const parts = prototypeParts(scene, source);
  let inventory: Inventory | undefined;
  let groups: Record<Variant, THREE.Group> | undefined;
  let disposed = false;
  return {
    setInventory(next: Inventory) {
      if (disposed) throw Error('Inventory display is disposed');
      const a = createStockGroup(next.variants.A.additions, parts);
      let b: THREE.Group;
      try {b = createStockGroup(next.variants.B.additions, parts);}
      catch (error) {removeGroup(a); throw error;}
      if (groups) {removeGroup(groups.A); removeGroup(groups.B);}
      groups = {A: a, B: b};
      groups.A.name = 'inventory-capacity-A'; groups.B.name = 'inventory-capacity-B';
      groups.A.visible = true; groups.B.visible = false;
      scene.add(groups.A, groups.B);
      inventory = next;
    },
    apply(variant: Variant) {
      if (!groups || disposed) return;
      groups.A.visible = variant === 'A'; groups.B.visible = variant === 'B';
    },
    bounds(id: string, variant: Variant) {
      const row = inventory?.variants[variant].additions.find(row => row.handling_unit_id === id);
      return row ? {position: row.position, yaw: row.yaw_rad, dims: row.cargo.dimensions_xyz_m} : null;
    },
    snapshot() {
      return {mode: inventory?.mode ?? null, additionsA: inventory?.variants.A.additions.length ?? 0,
        additionsB: inventory?.variants.B.additions.length ?? 0, disposed};
    },
    dispose() {
      if (disposed) return;
      if (groups) {removeGroup(groups.A); removeGroup(groups.B);}
      groups = undefined; inventory = undefined; parts.clear(); disposed = true;
    },
  };
}
