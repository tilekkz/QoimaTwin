import * as THREE from 'three';
import {sha256} from './hash';

export function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k,v]) => JSON.stringify(k) + ':' + canonical(v)).join(',') + '}';
  return JSON.stringify(value) ?? 'null';
}
export const digest = (value: unknown): string => sha256(canonical(value));
export const bytesHash = (bytes: Uint8Array | string): string => sha256(bytes);
export function requireThat(condition: unknown, message: string): asserts condition { if (!condition) throw new Error(message); }
export function freeze<T>(value: T): T {
  if (value && typeof value === 'object') { for (const child of Object.values(value)) freeze(child); Object.freeze(value); }
  return value;
}
export function nodes(root: THREE.Object3D): THREE.Object3D[] { const result: THREE.Object3D[] = []; root.traverse(n => result.push(n)); return result; }
export function unique(root: THREE.Object3D, name: string): THREE.Object3D {
  const found = nodes(root).filter(n => n.name === name);
  requireThat(found.length === 1, 'Missing or ambiguous native node: ' + name); return found[0];
}
export function geometryJSON(root: THREE.Object3D, exclude?:THREE.Object3D): string {
  const excluded=new Set(exclude ? nodes(exclude) : []);
  return canonical(nodes(root).filter(n => (n as THREE.Mesh).isMesh && !excluded.has(n)).sort((a,b)=>a.name.localeCompare(b.name)).map(n => {
    const mesh = n as THREE.Mesh, g = mesh.geometry;
    return {name:n.name, attributes:Object.fromEntries(Object.entries(g.attributes).map(([key,a]) => [key,{size:a.itemSize,normalized:a.normalized,values:Array.from(a.array)}])),index:g.index ? Array.from(g.index.array) : null,groups:g.groups,parts:n.userData};
  }));
}
export function geometryIdentity(root:THREE.Object3D,exclude?:THREE.Object3D):string{return bytesHash(geometryJSON(root,exclude));}
export function controlsJSON(root: THREE.Object3D): string {
  const all = nodes(root);
  return canonical(all.map(n => ({name:n.name,parent:all.indexOf(n.parent!),p:n.position.toArray(),q:n.quaternion.toArray(),s:n.scale.toArray(),visible:n.visible,auto:n.matrixAutoUpdate,data:n.userData})));
}
export function controlsIdentity(root:THREE.Object3D):string{return bytesHash(controlsJSON(root));}
export type Baseline = ReturnType<typeof capture>;
export function capture(roots: readonly THREE.Object3D[]) {
  const all = [...new Set(roots.flatMap(nodes))];
  return all.map(n => ({n,parent:n.parent,index:n.parent?.children.indexOf(n) ?? -1,siblings:[...(n.parent?.children??[])],p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone(),visible:n.visible,auto:n.matrixAutoUpdate,worldAuto:n.matrixWorldAutoUpdate,matrix:n.matrix.clone(),data:structuredClone(n.userData),children:[...n.children]}));
}
/** Restore exact local state and sibling order, including externally parented actor. */
export function restore(rows: Baseline): void {
  for (const r of rows) if (r.n.parent !== r.parent) { r.n.removeFromParent(); r.parent?.add(r.n); }
  for (const r of rows) {
    r.n.position.copy(r.p); r.n.quaternion.copy(r.q); r.n.scale.copy(r.s); r.n.visible=r.visible;
    r.n.matrixAutoUpdate=r.auto; r.n.matrixWorldAutoUpdate=r.worldAuto; r.n.matrix.copy(r.matrix); r.n.userData=structuredClone(r.data);
    if (r.parent && r.index >= 0) {
      // Relative anchors compose correctly when a second fixture temporarily
      // removes a sibling from the same external parent.
      const a=r.parent.children, i=a.indexOf(r.n); a.splice(i,1);
      const next=r.siblings.slice(r.index+1).find(n=>n.parent===r.parent);
      const previous=r.siblings.slice(0,r.index).reverse().find(n=>n.parent===r.parent);
      const at=next ? a.indexOf(next) : previous ? a.indexOf(previous)+1 : Math.min(r.index,a.length);
      a.splice(at,0,r.n);
    }
  }
  // Ancestors are external host state. Updating with updateParents=true would
  // overwrite a host's edited matrices during cancellation.
  for (const r of rows) r.n.updateWorldMatrix(false,false);
}
export function liveIdentity(roots: readonly THREE.Object3D[]): string {
  return digest([...new Set(roots.flatMap(nodes))].map(n => ({id:n.uuid,parent:n.parent?.uuid,children:n.children.map(c=>c.uuid),p:n.position.toArray(),q:n.quaternion.toArray(),s:n.scale.toArray(),visible:n.visible,auto:n.matrixAutoUpdate,data:n.userData})));
}
